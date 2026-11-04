"""Loopback-only web console. Run: python seckill_web.py --open"""
import argparse
import base64
from collections import deque
from datetime import datetime
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit
import uuid
import webbrowser

BASE = Path(__file__).resolve().parent
REGIONS = {4: '上海', 8: '北京', 1: '广州'}
ACTIONS = {'login', 'connect', 'grab', 'test-order'}
BUSY = {'running', 'stopping'}
EVENT_PREFIX = '@@WEB:'


def validate_region(region):
    if type(region) is not int or region not in REGIONS:
        raise ValueError('请选择上海、北京或广州。')
    return region


def validate_task(data):
    if not isinstance(data, dict) or data.get('action') not in ACTIONS:
        raise ValueError('无效任务类型。')
    region = validate_region(data.get('region', 8))
    session = data.get('session', 'auto')
    if session not in {'auto', '10:00', '15:00'}:
        raise ValueError('无效场次。')
    if data['action'] in {'grab', 'test-order'} and data.get('confirmed') is not True:
        raise ValueError('真实下单操作必须明确确认。')
    force_login = data.get('force_login', False)
    if type(force_login) is not bool or (force_login and data['action'] != 'login'):
        raise ValueError('仅登录操作允许更换账号。')
    return {'action': data['action'], 'region': region, 'session': session, 'force_login': force_login}


class TaskManager:
    def __init__(self, base=BASE, demo=False):
        self.base, self.demo = Path(base), demo
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.entries = deque(maxlen=1000)
        self.seq = 0
        self.task = None
        self.process = None
        self.reader = None
        self.closed = False
        self.login = 'saved' if (self.base / '.state.json').exists() else 'missing'
        self.add_log('本地控制台已就绪。尚未执行任何任务。', 'info')
        if demo:
            self.add_log('模拟模式：所有任务为本地模拟，不访问腾讯云。', 'warning')

    def _config(self):
        path = self.base / 'config.json'
        if not path.exists():
            return {'region': 8}
        try:
            data = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (ValueError, OSError) as e:
            raise ValueError('config.json 无法读取，请检查文件；不会覆盖原配置。') from e

    def save_region(self, region):
        region = validate_region(region)
        with self.lock:
            if self.task and self.task['state'] in BUSY:
                raise RuntimeError('任务运行中，暂不能修改配置。')
            cfg = self._config()
            cfg['region'] = region
            dest = self.base / 'config.json'
            temp = self.base / 'config.json.tmp'
            temp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(temp, dest)
        return {'region': region}

    def add_log(self, text, level='info'):
        text = re.sub(r'\x1b\[[0-9;]*m', '', str(text))
        text = re.sub(r'(?i)((?:x-csrf-token|cookie|authorization|bark_key)\s*[=:]\s*)[^;\r\n]+', r'\1[已隐藏]', text)
        with self.lock:
            self.seq += 1
            self.entries.append({'seq': self.seq, 'time': datetime.now().strftime('%H:%M:%S'),
                                 'message': text[:2000], 'level': level})

    def status(self):
        with self.lock:
            error = None
            try:
                region = self._config().get('region', 8)
                if type(region) is not int or region not in REGIONS:
                    region = 8
            except ValueError as e:
                region, error = 8, str(e)
            return {'task': dict(self.task) if self.task else None,
                    'busy': bool(self.task and self.task['state'] in BUSY),
                    'region': region, 'login': self.login, 'demo': self.demo,
                    'server_time': time.time(), 'last_seq': self.seq, 'config_error': error}

    def logs(self, after):
        with self.lock:
            return {'entries': [dict(e) for e in self.entries if e['seq'] > after],
                    'truncated': bool(self.entries and after < self.entries[0]['seq'] - 1),
                    'last_seq': self.seq}

    def start(self, data):
        options = validate_task(data)
        with self.lock:
            if self.closed:
                raise RuntimeError('服务正在关闭。')
            if self.task and self.task['state'] in BUSY:
                raise RuntimeError('已有任务运行中，请先停止。')
            task_id = uuid.uuid4().hex
            cmd = [sys.executable, '-u', str(BASE / 'web_worker.py'), '--action', options['action'],
                   '--region', str(options['region']), '--session', options['session'], '--base', str(self.base)]
            if options['force_login']:
                cmd.append('--force-login')
            if self.demo:
                cmd.append('--demo')
            env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            self.task = {'id': task_id, **options, 'state': 'running', 'phase': '正在准备',
                         'target_at': None, 'offset_ms': 0, 'message': '', 'login_confirmed': False, 'started_at': time.time()}
            try:
                proc = subprocess.Popen(cmd, cwd=str(BASE), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                                        env=env, creationflags=flags)
            except OSError:
                self.task.update(state='failed', message='无法启动 Python 任务进程。')
                raise
            self.process = proc
            self.add_log('任务已启动：' + options['action'] + ' / ' + REGIONS[options['region']])
            self.reader = threading.Thread(target=self._read, args=(task_id, proc), daemon=True)
            self.reader.start()
            return dict(self.task)

    def _read(self, task_id, proc):
        outcome = None
        try:
            for line in proc.stdout:
                line = line.rstrip()
                if not line:
                    continue
                event = None
                if line.startswith(EVENT_PREFIX):
                    try:
                        event = json.loads(line[len(EVENT_PREFIX):])
                    except ValueError:
                        pass
                with self.lock:
                    if not self.task or self.task['id'] != task_id:
                        continue
                    if isinstance(event, dict):
                        kind = event.get('type')
                        if kind == 'result' and event.get('state') in {'succeeded', 'failed', 'stopped'}:
                            if not outcome or outcome['state'] != 'succeeded':
                                outcome = event
                        elif kind == 'login' and event.get('value') in {'valid', 'invalid', 'unknown', 'missing'}:
                            self.login = event['value']
                            if self.task['action'] == 'login' and self.login == 'valid':
                                self.task.update(login_confirmed=True, qr_image=None)
                        elif kind == 'scan' and self.task['action'] == 'login' and self.task['state'] == 'running' and not self.task.get('login_confirmed'):
                            if event.get('value') in {'waiting','scanned','cancelled'}:
                                self.task['scan_state'] = event['value']
                        elif kind == 'qr' and self.task['action'] == 'login' and self.task['state'] == 'running':
                            self.task['scan_state'] = 'waiting'
                            image = event.get('image')
                            if image is None:
                                self.task['qr_image'] = None
                            elif isinstance(image, str) and image.startswith('data:image/png;base64,') and len(image) < 300000:
                                try:
                                    if base64.b64decode(image.split(',',1)[1], validate=True).startswith(b'\x89PNG\r\n\x1a\n'):
                                        self.task['qr_image'] = image
                                except ValueError:
                                    pass
                        elif kind == 'needs_login':
                            self.task['requires_login'] = True
                        elif kind == 'progress':
                            for key in ('phase', 'target_at', 'offset_ms'):
                                if key in event:
                                    self.task[key] = event[key]
                        continue
                    self.add_log(line)
            code = proc.wait()
            with self.lock:
                if self.task and self.task['id'] == task_id:
                    if outcome and outcome['state'] == 'succeeded':
                        state, message = 'succeeded', outcome.get('message', '')
                    elif self.task['state'] == 'stopping':
                        state, message = 'stopped', ('登录已取消，原登录态保留。' if self.task['action'] == 'login' else '任务已停止；已创建的订单不会撤销。')
                    elif outcome:
                        state, message = outcome['state'], outcome.get('message', '')
                    else:
                        state, message = 'failed', f'进程退出（{code}），未收到明确结果；订单状态请自行核实。'
                    self.task.update(state=state, message=message, phase=message, ended_at=time.time(), qr_image=None, scan_state=None)
                    self.add_log(message, 'success' if state == 'succeeded' else 'warning')
        finally:
            proc.stdout.close()
            if proc.stdin:
                proc.stdin.close()

    def refresh_qr(self, task_id):
        with self.lock:
            if not self.task or self.task['id'] != task_id or self.task['state'] != 'running' or self.task['action'] != 'login':
                raise RuntimeError('仅能刷新当前登录任务的二维码。')
            if not self.process or self.process.poll() is not None:
                raise RuntimeError('登录任务已结束。')
            self.process.stdin.write('refresh\n')
            self.process.stdin.flush()
            self.task.update(qr_image=None, scan_state='waiting', phase='正在刷新二维码')
            return {'id': task_id}

    def stop(self, task_id):
        with self.lock:
            if not self.task or self.task['id'] != task_id:
                raise RuntimeError('任务编号已失效，请刷新后重试。')
            if self.task['state'] not in BUSY:
                return dict(self.task)
            if self.task['state'] == 'stopping':
                return dict(self.task)
            self.task.update(state='stopping', phase='正在关闭任务浏览器…', qr_image=None, scan_state=None)
            proc = self.process
            self.add_log('正在取消登录并关闭后台浏览器。' if self.task['action'] == 'login' else '正在停止任务；已提交的订单无法通过此操作撤销。', 'warning')
            try:
                proc.stdin.write('stop\n')
                proc.stdin.flush()
            except (BrokenPipeError, OSError, ValueError):
                pass
            threading.Thread(target=self._escalate, args=(task_id, proc), daemon=True).start()
            return dict(self.task)

    def _escalate(self, task_id, proc):
        try:
            proc.wait(timeout=8)
            return
        except subprocess.TimeoutExpired:
            pass
        with self.lock:
            if not self.task or self.task['id'] != task_id or proc.poll() is not None:
                return
            self.add_log('任务关闭超时，终止本次任务进程树。', 'warning')
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
            else:
                proc.kill()

    def close(self):
        with self.lock:
            self.closed = True
            task = dict(self.task) if self.task else None
        if task and task['state'] in BUSY:
            self.stop(task['id'])
        reader = self.reader
        if reader and reader is not threading.current_thread():
            reader.join(timeout=15)


def make_server(manager, port=8765):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *_):
            pass

        def send_body(self, code, body, content_type='application/json; charset=utf-8'):
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def reply(self, code, data):
            self.send_body(code, json.dumps(data, ensure_ascii=False).encode('utf-8'))

        def allowed_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}

        def do_GET(self):
            if not self.allowed_host():
                return self.reply(403, {'error': '仅支持本机访问。'})
            url = urlsplit(self.path)
            if url.path == '/api/status':
                return self.reply(200, manager.status())
            if url.path == '/api/logs':
                try:
                    after = int(parse_qs(url.query).get('after', ['0'])[0])
                    if after < 0:
                        raise ValueError()
                except ValueError:
                    return self.reply(400, {'error': '无效日志序号。'})
                return self.reply(200, manager.logs(after))
            assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                      '/styles.css': ('styles.css', 'text/css; charset=utf-8'),
                      '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                      '/favicon.svg': ('favicon.svg', 'image/svg+xml')}
            if url.path not in assets:
                return self.reply(404, {'error': '资源不存在。'})
            name, mime = assets[url.path]
            path = BASE / 'web' / name
            if not path.exists():
                return self.reply(404, {'error': '页面文件不存在。'})
            body = path.read_bytes()
            if name == 'index.html':
                body = body.replace(b'__CONSOLE_TOKEN__', manager.token.encode())
            self.send_body(200, body, mime)

        def do_POST(self):
            # Drain the bounded body before rejecting; unread data can reset the TCP reply.
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0 or length > 4096:
                    raise ValueError('请求大小无效。')
                payload = self.rfile.read(length)
            except ValueError as e:
                return self.reply(400, {'error': str(e) or '请求大小无效。'})
            except TimeoutError:
                return self.reply(408, {'error': '请求读取超时。'})
            origin = self.headers.get('Origin')
            allowed_origins = {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}
            token = self.headers.get('X-Console-Token', '')
            if not self.allowed_host() or origin not in allowed_origins or not hmac.compare_digest(token, manager.token):
                return self.reply(403, {'error': '安全校验失败，请重新打开本地页面。'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.reply(415, {'error': '需要 JSON 请求。'})
            try:
                data = json.loads(payload)
                if not isinstance(data, dict):
                    raise ValueError('请求必须为对象。')
                path = urlsplit(self.path).path
                if path == '/api/config':
                    result = manager.save_region(data.get('region'))
                elif path == '/api/tasks':
                    result = manager.start(data)
                elif path == '/api/tasks/refresh-qr':
                    result = manager.refresh_qr(data.get('id'))
                elif path == '/api/tasks/stop':
                    result = manager.stop(data.get('id'))
                else:
                    return self.reply(404, {'error': '接口不存在。'})
                self.reply(200, result)
            except (ValueError, TypeError) as e:
                self.reply(400, {'error': str(e) or '参数无效。'})
            except RuntimeError as e:
                self.reply(409, {'error': str(e)})
            except OSError:
                self.reply(500, {'error': '文件保存或任务启动失败，请检查权限与 Python 环境。'})

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description='腾讯云抢购本地 Web 控制台')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--open', action='store_true', help='自动打开浏览器')
    parser.add_argument('--demo', action='store_true', help='纯模拟任务，不访问腾讯云')
    parser.add_argument('--base', type=Path, default=BASE, help=argparse.SUPPRESS)
    args = parser.parse_args()
    manager = TaskManager(args.base, demo=args.demo)
    try:
        server = make_server(manager, args.port)
    except OSError as e:
        print(f'无法启动本地服务（端口 {args.port}）：{e}', file=sys.stderr)
        return 1
    url = f'http://127.0.0.1:{server.server_port}'
    print(f'本地控制台：{url}', flush=True)
    print('模拟模式（不会下单）' if args.demo else '真实模式：仅确认后才启动任务。按 Ctrl+C 关闭服务。', flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n正在清理本次任务…', flush=True)
    finally:
        manager.close()
        server.server_close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
