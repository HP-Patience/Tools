import json
import io
import subprocess
import sys
import os
from types import SimpleNamespace
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch, MagicMock

from seckill_web import TaskManager, make_server, validate_task


class ValidationTests(unittest.TestCase):
    def test_whitelists_and_confirmation(self):
        for bad in ({'action': 'shell'}, {'action': 'grab', 'region': 9},
                    {'action': 'grab', 'region': True}, {'action': 'grab', 'session': '12:34'},
                    {'action': 'grab'}, {'action': 'test-order', 'confirmed': 'true'}):
            with self.assertRaises(ValueError):
                validate_task(bad)
        for bad in ({'action':'login', 'force_login':'yes'}, {'action':'grab','confirmed':True,'force_login':True}):
            with self.assertRaises(ValueError):
                validate_task(bad)
        self.assertTrue(validate_task({'action':'login','force_login':True})['force_login'])
        self.assertEqual(validate_task({'action': 'connect'})['region'], 8)
        self.assertEqual(validate_task({'action': 'grab', 'confirmed': True})['action'], 'grab')


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.manager = TaskManager(Path(self.tmp.name), demo=True)

    def tearDown(self):
        self.manager.close()
        self.tmp.cleanup()

    def wait_done(self, timeout=8):
        deadline = time.monotonic() + timeout
        while self.manager.status()['busy'] and time.monotonic() < deadline:
            time.sleep(.05)
        self.assertFalse(self.manager.status()['busy'])

    def test_config_preserves_private_keys(self):
        (self.manager.base / 'config.json').write_text('{"bark_key":"private", "region":8}')
        self.manager.save_region(4)
        self.assertEqual(json.loads((self.manager.base / 'config.json').read_text())['bark_key'], 'private')
        self.assertNotIn('bark_key', json.dumps(self.manager.status()))

    def test_single_task_and_stop(self):
        first = self.manager.start({'action': 'grab', 'confirmed': True})
        with self.assertRaises(RuntimeError):
            self.manager.start({'action': 'connect'})
        with self.assertRaises(RuntimeError):
            self.manager.save_region(4)
        with self.assertRaises(RuntimeError):
            self.manager.stop('stale')
        self.manager.stop(first['id'])
        self.wait_done()
        self.assertEqual(self.manager.status()['task']['state'], 'stopped')
        self.manager.stop(first['id'])

    def test_demo_result_and_logs(self):
        self.manager.start({'action': 'connect'})
        self.wait_done()
        self.assertEqual(self.manager.status()['task']['state'], 'succeeded')
        self.assertTrue(self.manager.logs(0)['entries'])

    def test_log_bounds_and_redaction(self):
        for i in range(1200):
            self.manager.add_log('line ' + str(i))
        self.manager.add_log('x-csrf-token: secret123; cookie: abc123')
        logs = self.manager.logs(0)
        self.assertTrue(logs['truncated'])
        self.assertLessEqual(len(logs['entries']), 1000)
        self.assertNotIn('secret123', json.dumps(logs))
        self.assertNotIn('abc123', json.dumps(logs))

    def test_concurrent_starts_only_one_process(self):
        barrier = threading.Barrier(5)
        results = []
        def start():
            barrier.wait()
            try:
                results.append(self.manager.start({'action': 'grab', 'confirmed': True})['id'])
            except RuntimeError:
                results.append(None)
        threads = [threading.Thread(target=start) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(sum(value is not None for value in results), 1)

    def test_corrupt_config_not_overwritten(self):
        path = self.manager.base / 'config.json'
        path.write_text('broken')
        with self.assertRaises(ValueError):
            self.manager.save_region(4)
        self.assertEqual(path.read_text(), 'broken')
        self.assertTrue(self.manager.status()['config_error'])

    def test_eof_without_result_is_failure(self):
        proc = SimpleNamespace(stdout=io.StringIO('ordinary output\n'), stdin=io.StringIO(),
                               wait=lambda: 0)
        self.manager.task = {'id':'test', 'state':'running'}
        self.manager._read('test', proc)
        self.assertEqual(self.manager.task['state'], 'failed')

    def test_shutdown_stops_own_task(self):
        self.manager.start({'action':'grab', 'confirmed':True})
        self.manager.close()
        self.assertFalse(self.manager.status()['busy'])
        self.assertEqual(self.manager.process.poll(), 0)
        with self.assertRaises(RuntimeError):
            self.manager.start({'action':'connect'})

    def test_success_result_not_hidden_by_stop(self):
        event = '@@WEB:' + json.dumps({'type':'result', 'state':'succeeded', 'message':'order confirmed'})
        stop_event = '@@WEB:' + json.dumps({'type':'result', 'state':'stopped'})
        proc = SimpleNamespace(stdout=io.StringIO(event+'\n'+stop_event+'\n'), stdin=io.StringIO(), wait=lambda:0)
        self.manager.task = {'id':'test', 'state':'stopping'}
        self.manager._read('test', proc)
        self.assertEqual(self.manager.task['state'], 'succeeded')

    def test_forced_stop_timeout(self):
        proc = MagicMock()
        proc.wait.side_effect = subprocess.TimeoutExpired('worker', 8)
        proc.poll.return_value = None
        proc.pid = 12345
        self.manager.task = {'id':'test', 'state':'stopping'}
        with patch('seckill_web.subprocess.run') as kill:
            self.manager._escalate('test', proc)
        kill.assert_called_once()
        self.assertEqual(kill.call_args.args[0], ['taskkill','/PID','12345','/T','/F'])

    @unittest.skipUnless(os.name == 'nt', 'Windows process-tree termination')
    def test_real_unresponsive_worker_is_force_stopped(self):
        original = subprocess.Popen
        def launch(_cmd, **kwargs):
            return original([sys.executable, '-u', '-c', 'import time; print("unresponsive fixture",flush=True); time.sleep(60)'], **kwargs)
        with patch('seckill_web.subprocess.Popen', side_effect=launch):
            task = self.manager.start({'action':'grab', 'confirmed':True})
        self.manager.stop(task['id'])
        self.wait_done(timeout=16)
        self.assertEqual(self.manager.task['state'], 'stopped')
        self.assertIsNotNone(self.manager.process.poll())

    def test_scan_signal_reaches_ui_without_setting_logged_in(self):
        class Output:
            def __iter__(out):
                yield '@@WEB:' + json.dumps({'type':'scan','value':'scanned'}) + '\n'
                self.assertEqual(self.manager.task.get('scan_state'), 'scanned')
                self.assertNotEqual(self.manager.login,'valid')
                yield '@@WEB:' + json.dumps({'type':'result','state':'stopped','message':'cancel'}) + '\n'
            def close(out):
                pass
        proc=SimpleNamespace(stdout=Output(),stdin=io.StringIO(),wait=lambda:0)
        self.manager.task={'id':'test','state':'running','action':'login'}
        self.manager._read('test',proc)

    def test_login_required_event_reaches_status(self):
        events = [{'type':'login', 'value':'invalid'}, {'type':'needs_login'}, {'type':'result','state':'failed','message':'login required'}]
        output = ''.join('@@WEB:' + json.dumps(event) + '\n' for event in events)
        proc = SimpleNamespace(stdout=io.StringIO(output), stdin=io.StringIO(), wait=lambda:0)
        self.manager.task = {'id':'test', 'state':'running', 'action':'grab'}
        self.manager._read('test', proc)
        self.assertTrue(self.manager.status()['task']['requires_login'])
        self.assertEqual(self.manager.status()['login'], 'invalid')

    def test_qr_is_cleared_immediately_when_login_confirmed(self):
        class Output:
            def __iter__(out):
                yield '@@WEB:' + json.dumps({'type':'login','value':'valid'}) + '\n'
                self.assertTrue(self.manager.task.get('login_confirmed'))
                self.assertIsNone(self.manager.task.get('qr_image'))
                yield '@@WEB:' + json.dumps({'type':'result','state':'succeeded','message':'login ok'}) + '\n'
            def close(out):
                pass
        proc = SimpleNamespace(stdout=Output(),stdin=io.StringIO(),wait=lambda:0)
        self.manager.task={'id':'test','state':'running','action':'login','qr_image':'old-image'}
        self.manager._read('test',proc)
        self.assertEqual(self.manager.login,'valid')

    def test_qr_event_cleared_when_login_finishes(self):
        image = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ZkAAAAASUVORK5CYII='
        events = [{'type':'qr','image':image}, {'type':'result','state':'succeeded','message':'login ok'}]
        proc = SimpleNamespace(stdout=io.StringIO(''.join('@@WEB:'+json.dumps(e)+'\n' for e in events)), stdin=io.StringIO(), wait=lambda:0)
        self.manager.task = {'id':'test','state':'running','action':'login'}
        self.manager._read('test', proc)
        self.assertIsNone(self.manager.task.get('qr_image'))
        self.assertNotIn(image, json.dumps(self.manager.logs(0)))

    def test_refresh_qr_requires_current_login_task(self):
        self.manager.task = {'id':'test','state':'running','action':'grab'}
        with self.assertRaises(RuntimeError):
            self.manager.refresh_qr('test')
        self.manager.task.update(action='login', qr_image='old')
        self.manager.process = MagicMock()
        self.manager.process.poll.return_value = None
        with self.assertRaises(RuntimeError):
            self.manager.refresh_qr('stale')
        self.manager.refresh_qr('test')
        self.manager.process.stdin.write.assert_called_once_with('refresh\n')
        self.assertIsNone(self.manager.task['qr_image'])
        self.manager.task['state']='stopped'

    def test_failed_launch_does_not_leave_busy(self):
        with patch('seckill_web.subprocess.Popen', side_effect=OSError('boom')):
            with self.assertRaises(OSError):
                self.manager.start({'action': 'connect'})
        self.assertFalse(self.manager.status()['busy'])


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.manager = TaskManager(Path(self.tmp.name), demo=True)
        self.server = make_server(self.manager, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.manager.close()
        self.tmp.cleanup()

    def request(self, path, data=None, headers=None):
        payload = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request(self.url + path, data=payload, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=3) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_assets_only(self):
        self.assertEqual(self.request('/')[0], 200)
        for path in ('/.state.json', '/seckill.py', '/../config.json', '/web/../seckill.py'):
            self.assertEqual(self.request(path)[0], 404)

    def test_security_guards(self):
        data = {'action': 'grab', 'confirmed': True}
        for _ in range(30):
            self.assertEqual(self.request('/api/tasks', data)[0], 403)
        headers = {'X-Console-Token': self.manager.token, 'Content-Type': 'application/json', 'Origin': 'https://evil.example'}
        self.assertEqual(self.request('/api/tasks', data, headers)[0], 403)
        headers['Origin'] = self.url
        self.assertEqual(self.request('/api/tasks', {'action': 'grab'}, headers)[0], 400)
        self.assertEqual(self.request('/api/tasks/refresh-qr', {'id':'stale'}, headers)[0], 409)
        self.assertEqual(self.request('/api/status', headers={'Host': 'evil.example'})[0], 403)

    def test_status_and_config(self):
        code, body = self.request('/api/status')
        self.assertEqual(code, 200)
        self.assertNotIn('token', json.loads(body))
        headers = {'X-Console-Token': self.manager.token, 'Content-Type': 'application/json', 'Origin': self.url}
        self.assertEqual(self.request('/api/config', {'region': 1}, headers)[0], 200)
        self.assertEqual(self.request('/api/config', {'region': '8'}, headers)[0], 400)
        self.assertEqual(self.request('/api/logs?after=bad')[0], 400)


if __name__ == '__main__':
    unittest.main()
