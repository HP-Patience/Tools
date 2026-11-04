import asyncio
from datetime import datetime
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
from types import SimpleNamespace
from playwright.async_api import Error as PlaywrightError

from web_worker import strict_login, target_datetime, run_browser_task, execute, safe_error_detail, login_state, publish_login_qr, make_context, query_context_login, verify_login_state, observe_csrf, watch_scan_state


class WorkerTests(unittest.TestCase):
    def test_login_fail_closed(self):
        for response in ({}, {'code': -1}, {'code': True}, {'code': 'ERROR'},
                         {'code': 'NOT-LOGINED'}, {'code': 400}, {'code': 'unexpected'},
                         {'code': 0, '__err': 'offline'}):
            self.assertFalse(strict_login(response), response)
        for response in ({'code': 0}, {'code': '0'}, {'code': 'SUCCESS'}):
            self.assertTrue(strict_login(response), response)

    def test_error_diagnostic_does_not_echo_secrets(self):
        detail = safe_error_detail(PlaywrightError('Page.goto: net::ERR_CONNECTION_RESET https://example.com/?token=private-token Cookie: private-cookie'))
        self.assertIn('ERR_CONNECTION_RESET', detail)
        self.assertNotIn('private-token', detail)
        self.assertNotIn('private-cookie', detail)
        detail = safe_error_detail(PlaywrightError('Page.evaluate: unrecognized token=secret Cookie: session-secret'))
        self.assertIn('Page.evaluate', detail)
        self.assertNotIn('secret', detail)

    def test_login_state_distinguishes_expiry_and_network(self):
        self.assertEqual(login_state({'code':0}), 'valid')
        self.assertEqual(login_state({'code':'NOT-LOGINED'}), 'invalid')
        self.assertEqual(login_state({'code':401}), 'invalid')
        for response in ({'__err':'network'}, {'code':500}, {'code':-1}, {'code':403}, None):
            self.assertEqual(login_state(response), 'unknown')

    def test_target_rollover(self):
        now = datetime(2026, 10, 11, 16, 0)
        self.assertEqual(target_datetime('10:00', now), datetime(2026, 10, 12, 10, 0))
        self.assertEqual(target_datetime('auto', now), datetime(2026, 10, 12, 10, 0))
        self.assertEqual(target_datetime('auto', datetime(2026, 10, 11, 11)), datetime(2026, 10, 11, 15))

    def test_missing_state_never_loads_browser(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('web_worker.load_core', side_effect=AssertionError('must not import browser')):
                result = asyncio.run(run_browser_task('grab', 8, 'auto', Path(tmp)))
                self.assertFalse(result)


class AsyncWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.qr_patch = patch('web_worker.publish_login_qr', new=AsyncMock(return_value='data:image/png;base64,test'))
        self.publish_qr = self.qr_patch.start()
        self.addCleanup(self.qr_patch.stop)
        self.scan_patch = patch('web_worker.watch_scan_state', new=AsyncMock())
        self.scan_patch.start()
        self.addCleanup(self.scan_patch.stop)

    def context(self, response, csrf=True):
        tmp = tempfile.TemporaryDirectory()
        base = Path(tmp.name)
        (base / '.state.json').write_text('{}')
        page = MagicMock()
        page.goto = AsyncMock()
        page.evaluate = AsyncMock(side_effect=lambda script,*args: 'test-csrf' if '() => window.__latestCsrf ||' in script else response)
        ctx = MagicMock()
        ctx.add_init_script = AsyncMock()
        ctx.new_page = AsyncMock(return_value=page)
        async def write_state(**kwargs):
            state = {'cookies':[], 'origins':[]}
            if 'path' in kwargs:
                Path(kwargs['path']).write_text('{}')
            return state
        ctx.storage_state = AsyncMock(side_effect=write_state)
        ctx.close = AsyncMock()
        reply = MagicMock()
        reply.ok = True
        reply.dispose = AsyncMock()
        reply.json = AsyncMock(return_value=response)
        ctx.request.post = AsyncMock(return_value=reply)
        browser = MagicMock()
        browser.new_context = AsyncMock(return_value=ctx)
        browser.close = AsyncMock()
        browser.is_connected.return_value = True
        pw = MagicMock()
        pw.stop = AsyncMock()
        pw_factory = MagicMock()
        pw_factory.start = AsyncMock(return_value=pw)
        sf = MagicMock()
        sf.async_playwright.return_value = pw_factory
        sf.launch_browser = AsyncMock(return_value=browser)
        sf.rapid_purchase = AsyncMock(return_value=True)
        sf.FLASH_SALE = sf.TEST_GOODS = {'name': 'Test', 'goods_param': {}}
        sf.sync_time = AsyncMock(return_value=0)
        sf.ADVANCE_MS = -3000
        sf.WARMUP_SECONDS = 10
        ui = MagicMock()
        ui._wait_csrf = AsyncMock(return_value=csrf)
        return tmp, base, sf, ui, browser, pw, page

    async def test_login_navigation_does_not_abort_login(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        ui._wait_csrf.side_effect = [PlaywrightError('Page.evaluate: Execution context was destroyed, most likely because of a navigation'), True, True]
        try:
            with patch('web_worker.load_core', return_value=(sf,ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()):
                self.assertTrue(await run_browser_task('login', 4, 'auto', base, force_login=True))
            sf.rapid_purchase.assert_not_called()
            ctx = browser.new_context.return_value
            ctx.close.assert_awaited_once()
        finally:
            tmp.cleanup()

    async def test_lightweight_verification_retries_transient_failure(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        bad = MagicMock()
        bad.ok = False
        bad.dispose = AsyncMock()
        good = browser.new_context.return_value.request.post.return_value
        browser.new_context.return_value.request.post.side_effect = [good, bad, good]
        try:
            with patch('web_worker.load_core', return_value=(sf,ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()):
                self.assertTrue(await run_browser_task('login', 4, 'auto', base, force_login=True))
            self.assertTrue((base / '.state.json').exists())
            sf.rapid_purchase.assert_not_called()
        finally:
            tmp.cleanup()

    async def test_login_verification_failure_preserves_saved_state(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        bad = MagicMock()
        bad.ok = False
        bad.dispose = AsyncMock()
        good = browser.new_context.return_value.request.post.return_value
        browser.new_context.return_value.request.post.side_effect = [good, bad, bad, bad]
        original = (base / '.state.json').read_bytes()
        args = SimpleNamespace(action='login', demo=False, region=4, session='auto', base=base, force_login=True)
        try:
            with patch('web_worker.load_core', return_value=(sf,ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()), patch('web_worker.threading.Thread'), patch('web_worker.emit') as events:
                await execute(args)
            result = [call.kwargs for call in events.call_args_list if call.args == ('result',)][-1]
            self.assertEqual(result['state'], 'failed')
            self.assertIn('已保留', result['message'])
            self.assertNotIn('重新扫码', result['message'])
            self.assertTrue((base / '.state.json').exists())
            self.assertEqual(ui._wait_csrf.await_count, 1)
            self.assertEqual((base / '.state.json').read_bytes(), original)
            sf.rapid_purchase.assert_not_called()
        finally:
            tmp.cleanup()

    async def test_login_failure_does_not_report_order_risk(self):
        args = SimpleNamespace(action='login', demo=False, region=4, session='auto', base=Path('.'))
        with patch('web_worker.run_browser_task', new=AsyncMock(side_effect=PlaywrightError('Page.goto: net::ERR_CONNECTION_RESET'))), patch('web_worker.threading.Thread'), patch('web_worker.emit') as events, patch('builtins.print') as output:
            await execute(args)
        result = [call.kwargs for call in events.call_args_list if call.args == ('result',)][-1]
        self.assertEqual(result['state'], 'failed')
        self.assertNotIn('订单', result['message'])
        self.assertIn('ERR_CONNECTION_RESET', str(output.call_args_list))

    async def test_lightweight_saved_state_validation_never_loads_activity(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        snapshot = {'cookies':[], 'origins':[]}
        try:
            with patch('web_worker.asyncio.sleep', new=AsyncMock()):
                result = await verify_login_state(browser, ui, snapshot, 'test-csrf', sf.ACTIVITY_URL)
            self.assertEqual(result, snapshot)
            browser.new_context.assert_awaited_once_with(storage_state=snapshot, user_agent=ui.UA)
            browser.new_context.return_value.new_page.assert_not_called()
            browser.new_context.return_value.close.assert_awaited_once()
            headers = browser.new_context.return_value.request.post.call_args.kwargs['headers']
            self.assertEqual(headers['x-csrf-token'], 'test-csrf')
        finally:
            tmp.cleanup()

    async def test_captured_csrf_survives_navigation_without_dom_detection(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        ctx = browser.new_context.return_value
        try:
            cache = observe_csrf(ctx)
            listener = ctx.on.call_args.args[1]
            listener(SimpleNamespace(url='https://act-api.cloud.tencent.com/user/get-vip-info', headers={'x-csrf-token':'real-token'}))
            with patch('web_worker.emit') as events:
                self.assertTrue(await __import__('web_worker').login_ready(page,ui,context=ctx,csrf=cache))
            ui._wait_csrf.assert_not_called()
            page.evaluate.assert_not_called()
            self.assertNotIn('real-token', str(events.call_args_list))
            listener(SimpleNamespace(url='https://untrusted.example/', headers={'x-csrf-token':'foreign-token'}))
            self.assertEqual(cache['token'], 'real-token')
        finally:
            tmp.cleanup()

    async def test_lightweight_query_fails_closed_without_csrf(self):
        ctx = MagicMock()
        self.assertEqual(await query_context_login(ctx,'', 'https://cloud.tencent.com/login'), {'__err':'csrf'})
        ctx.request.post.assert_not_called()

    async def test_scan_timeout_is_explicit_and_preserves_login_state(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        original = (base / '.state.json').read_bytes()
        try:
            with patch('web_worker.load_core', return_value=(sf,ui)), patch('web_worker.LOGIN_TIMEOUT_SECONDS', 0, create=True):
                with self.assertRaisesRegex(TimeoutError, '扫码等待超时'):
                    await run_browser_task('login',4,'auto',base,force_login=True)
            self.assertEqual((base / '.state.json').read_bytes(),original)
            sf.rapid_purchase.assert_not_called()
            browser.close.assert_awaited_once()
        finally:
            tmp.cleanup()

    async def test_phone_rejection_ends_login_instead_of_hanging(self):
        import asyncio
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        def done_scan(coroutine):
            coroutine.close()
            future = asyncio.get_running_loop().create_future()
            future.set_result('cancelled')
            return future
        try:
            with patch('web_worker.load_core', return_value=(sf,ui)), patch('web_worker.asyncio.create_task', side_effect=done_scan):
                with self.assertRaisesRegex(RuntimeError,'微信登录已取消'):
                    await run_browser_task('login',4,'auto',base,force_login=True)
            sf.rapid_purchase.assert_not_called()
            browser.close.assert_awaited_once()
        finally:
            tmp.cleanup()

    async def test_context_does_not_sleep_after_dom_ready(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        try:
            with patch('web_worker.asyncio.sleep', new=AsyncMock()) as sleep:
                await make_context(browser, sf, ui, url='https://cloud.tencent.com/login')
            sleep.assert_not_awaited()
        finally:
            tmp.cleanup()

    async def test_successful_login_has_no_fixed_delays(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        try:
            with patch('web_worker.load_core', return_value=(sf,ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()) as sleep:
                self.assertTrue(await run_browser_task('login', 4, 'auto', base, force_login=True))
            sleep.assert_not_awaited()
            self.assertEqual(ui._wait_csrf.await_count, 1)
            sf.rapid_purchase.assert_not_called()
        finally:
            tmp.cleanup()

    async def test_pending_login_checks_again_within_half_second(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        ui._wait_csrf.side_effect = [False, True, True]
        try:
            with patch('web_worker.load_core', return_value=(sf,ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()) as sleep:
                self.assertTrue(await run_browser_task('login', 4, 'auto', base, force_login=True))
            self.assertTrue(sleep.await_args_list)
            self.assertTrue(all(call.args[0] <= .5 for call in sleep.await_args_list))
        finally:
            tmp.cleanup()

    async def test_new_login_is_headless_and_publishes_qr(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        try:
            with patch('web_worker.load_core', return_value=(sf,ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()):
                self.assertTrue(await run_browser_task('login', 4, 'auto', base, force_login=True))
            sf.launch_browser.assert_awaited_once_with(pw, headless=True)
            self.publish_qr.assert_awaited_once_with(page)
            self.assertIn('/login?s_url=', str(page.goto.call_args_list[0]))
            sf.rapid_purchase.assert_not_called()
        finally:
            tmp.cleanup()

    async def test_login_reuses_valid_saved_state_without_scan(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        try:
            with patch('web_worker.load_core', return_value=(sf,ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()):
                self.assertTrue(await run_browser_task('login', 4, 'auto', base))
            sf.launch_browser.assert_awaited_once_with(pw, headless=True)
            self.publish_qr.assert_not_called()
            self.assertEqual(browser.new_context.call_args.kwargs['storage_state'], str(base / '.state.json'))
            sf.rapid_purchase.assert_not_called()
        finally:
            tmp.cleanup()

    async def test_login_only_scans_when_saved_state_expired(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        page.evaluate.side_effect = lambda script,*args: 'test-csrf' if '() => window.__latestCsrf ||' in script else {'code':'NOT-LOGINED'}
        try:
            with patch('web_worker.load_core', return_value=(sf,ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()):
                self.assertTrue(await run_browser_task('login', 4, 'auto', base))
            self.assertEqual([call.kwargs['headless'] for call in sf.launch_browser.call_args_list], [True, True])
            self.assertNotIn('storage_state', browser.new_context.call_args_list[1].kwargs)
            sf.rapid_purchase.assert_not_called()
        finally:
            tmp.cleanup()

    async def test_network_failure_does_not_open_scan_or_request_login(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'__err':'network'})
        try:
            with patch('web_worker.load_core', return_value=(sf,ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()), patch('web_worker.emit') as events:
                self.assertFalse(await run_browser_task('login', 4, 'auto', base))
            sf.launch_browser.assert_awaited_once_with(pw, headless=True)
            self.assertFalse(any(call.args == ('needs_login',) for call in events.call_args_list))
            self.assertTrue((base / '.state.json').exists())
            sf.rapid_purchase.assert_not_called()
        finally:
            tmp.cleanup()

    async def test_expired_purchase_requests_login_without_buying(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':'NOT-LOGINED'})
        try:
            with patch('web_worker.load_core', return_value=(sf,ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()), patch('web_worker.emit') as events:
                self.assertFalse(await run_browser_task('grab', 4, 'auto', base))
            self.assertTrue(any(call.args == ('needs_login',) for call in events.call_args_list))
            sf.rapid_purchase.assert_not_called()
        finally:
            tmp.cleanup()

    async def test_connect_never_purchases(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code': 0})
        try:
            with patch('web_worker.load_core', return_value=(sf, ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()):
                self.assertTrue(await run_browser_task('connect', 8, 'auto', base))
            sf.rapid_purchase.assert_not_called()
            browser.close.assert_awaited_once()
            pw.stop.assert_awaited_once()
        finally:
            tmp.cleanup()

    async def test_invalid_login_and_missing_csrf_never_purchase(self):
        for response, csrf in (({'code': 'NOT-LOGINED'}, True), ({'code': 0}, False), ({'code': 400}, True), (None, True)):
            tmp, base, sf, ui, browser, pw, page = self.context(response, csrf)
            try:
                with patch('web_worker.load_core', return_value=(sf, ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()):
                    self.assertFalse(await run_browser_task('test-order', 8, 'auto', base))
                sf.rapid_purchase.assert_not_called()
                browser.close.assert_awaited_once()
                pw.stop.assert_awaited_once()
            finally:
                tmp.cleanup()

    async def test_test_order_passes_selected_region_and_actual_result(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code': 0})
        try:
            with patch('web_worker.load_core', return_value=(sf, ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()):
                self.assertTrue(await run_browser_task('test-order', 4, 'auto', base))
            args = sf.rapid_purchase.call_args
            self.assertEqual(args.args[1]['goods_param']['regionId'], 4)
            self.assertEqual(args.kwargs['duration'], 5)
            self.assertEqual(sf.TEST_GOODS['goods_param'], {})
        finally:
            tmp.cleanup()

    async def test_browser_launch_failure_cleans_playwright(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        sf.launch_browser.side_effect = OSError('browser unavailable')
        try:
            with patch('web_worker.load_core', return_value=(sf, ui)):
                with self.assertRaises(OSError):
                    await run_browser_task('connect', 8, 'auto', base)
            pw.stop.assert_awaited_once()
            sf.rapid_purchase.assert_not_called()
        finally:
            tmp.cleanup()

    async def test_confirmed_order_and_driver_cleanup_survive_cancel(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code':0})
        browser.close.side_effect = asyncio.CancelledError()
        try:
            with patch('web_worker.load_core', return_value=(sf,ui)), patch('web_worker.asyncio.sleep', new=AsyncMock()), patch('web_worker.emit') as emit:
                with self.assertRaises(asyncio.CancelledError):
                    await run_browser_task('test-order', 8, 'auto', base)
            self.assertTrue(any(call.args == ('result',) and call.kwargs.get('state') == 'succeeded' for call in emit.call_args_list))
            pw.stop.assert_awaited_once()
        finally:
            tmp.cleanup()

    async def test_cancellation_cleans_browser(self):
        tmp, base, sf, ui, browser, pw, page = self.context({'code': 0})
        page.goto.side_effect = asyncio.CancelledError()
        try:
            with patch('web_worker.load_core', return_value=(sf, ui)):
                with self.assertRaises(asyncio.CancelledError):
                    await run_browser_task('connect', 8, 'auto', base)
            browser.close.assert_awaited_once()
            pw.stop.assert_awaited_once()
        finally:
            tmp.cleanup()


class QrExtractionTests(unittest.IsolatedAsyncioTestCase):
    async def test_qr_image_is_captured_and_emitted_without_source_url(self):
        image = MagicMock()
        image.count = AsyncMock(return_value=1)
        image.evaluate = AsyncMock(return_value=True)
        image.screenshot = AsyncMock(return_value=b'\x89PNG\r\n\x1a\nfixture')
        frame = MagicMock()
        frame.url = 'https://open.weixin.qq.com/connect/qrconnect?state=private-state'
        frame.locator.return_value.first = image
        page = MagicMock()
        page.frames = [frame]
        with patch('web_worker.emit') as events:
            await publish_login_qr(page)
        qr = [call.kwargs for call in events.call_args_list if call.args == ('qr',)][-1]
        self.assertTrue(qr['image'].startswith('data:image/png;base64,'))
        self.assertNotIn('private-state', str(events.call_args_list))


class ScanWatcherTests(unittest.IsolatedAsyncioTestCase):
    async def test_scan_signal_does_not_wait_for_login_verification(self):
        import asyncio
        stop = asyncio.Event()
        seen = asyncio.Event()
        release_auth = asyncio.Event()
        frame = MagicMock()
        frame.url = 'https://open.weixin.qq.com/connect/qrconnect'
        def locator(selector):
            element = MagicMock()
            element.count = AsyncMock(return_value=1 if 'after_scan' in selector else 0)
            return element
        frame.locator.side_effect = locator
        page = MagicMock()
        page.frames = [frame]
        ctx = MagicMock()
        reply = MagicMock()
        reply.ok = True
        reply.json = AsyncMock(return_value={'code':0})
        reply.dispose = AsyncMock()
        async def auth(*args, **kwargs):
            await release_auth.wait()
            return reply
        ctx.request.post = AsyncMock(side_effect=auth)
        def capture(kind, **data):
            if kind == 'scan' and data.get('value') == 'scanned':
                seen.set()
        with patch('web_worker.emit', side_effect=capture):
            watcher = asyncio.create_task(watch_scan_state(page, stop))
            login = asyncio.create_task(__import__('web_worker').login_ready(page, MagicMock(), context=ctx, csrf={'token':'test-csrf'}))
            try:
                await asyncio.wait_for(seen.wait(),timeout=.5)
                self.assertFalse(login.done())
                release_auth.set()
                self.assertTrue(await login)
            finally:
                stop.set()
                watcher.cancel()
                login.cancel()
                await asyncio.gather(watcher,login,return_exceptions=True)

    async def test_cancel_returns_to_qr_without_claiming_login(self):
        import asyncio
        stop = asyncio.Event()
        frame = MagicMock()
        frame.url = 'https://open.weixin.qq.com/connect/qrconnect'
        frame.locator.side_effect = lambda selector: SimpleNamespace(count=AsyncMock(return_value=1 if 'after_cancel' in selector else 0))
        page = MagicMock()
        page.frames = [frame]
        def capture(kind, **data):
            if kind == 'scan':
                stop.set()
        with patch('web_worker.emit', side_effect=capture) as events:
            await watch_scan_state(page,stop)
        self.assertTrue(any(call.args == ('scan',) and call.kwargs.get('value') == 'cancelled' for call in events.call_args_list))
        self.assertFalse(any(call.args == ('login',) for call in events.call_args_list))


if __name__ == '__main__':
    unittest.main()
