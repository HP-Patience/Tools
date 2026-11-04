"""Noninteractive task adapter; --demo never loads the Tencent/browser code."""
import argparse
import base64
import asyncio
from datetime import datetime, timedelta
import json
import re
import traceback
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlencode, urlsplit

EVENT_PREFIX = '@@WEB:'
VIP_URL = 'https://act-api.cloud.tencent.com/user/get-vip-info'
LOGIN_URL = 'https://cloud.tencent.com/login'
LOGIN_TIMEOUT_SECONDS = 600
DEMO_QR = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j1ZkAAAAASUVORK5CYII='


def emit(kind, **data):
    if kind == 'progress':
        print('[阶段] ' + data.get('phase', ''), flush=True)
    print(EVENT_PREFIX + json.dumps({'type': kind, **data}, ensure_ascii=False), flush=True)


def safe_error_detail(error):
    text = str(error)
    if '扫码等待超时' in text:
        return '扫码等待超时，请重新登录。'
    if '微信登录已取消' in text:
        return '微信登录已取消，请重新扫码登录。'
    if '二维码加载超时' in text:
        return '登录二维码加载超时，请检查网络后重试。'
    if 'Execution context was destroyed' in text or 'Cannot find context with specified id' in text:
        return '页面跳转打断了检测。'
    if type(error).__name__ == 'TargetClosedError' or 'Target page, context or browser has been closed' in text:
        return '后台浏览器或页面已关闭，本次操作已中断；请重试。'
    network = re.search(r'net::(ERR_[A-Z0-9_]+)', text)
    if network:
        return '网络访问失败：' + network.group(1)
    if "Executable doesn't exist" in text:
        return '浏览器程序不存在，请检查 Chrome/Edge 或安装 Playwright Chromium。'
    if type(error).__name__ == 'TimeoutError':
        return '页面或接口等待超时。'
    if isinstance(error, PermissionError):
        return '没有权限读取或保存登录态文件。'
    if isinstance(error, (ValueError, FileNotFoundError)):
        return '登录态文件或参数无法读取，请检查文件是否存在、格式是否正确。'
    method = re.match(r'^(BrowserType|Browser|BrowserContext|Page|Frame|Locator)\.([A-Za-z_]+):', text)
    return ('浏览器操作失败：' + method.group(1) + '.' + method.group(2)) if method else '操作失败，参见出错位置。'


async def login_ready(page, ui, tries=1, context=None, csrf=None):
    try:
        if context is not None:
            token = csrf.get('token', '') if csrf is not None else ''
            if not token:
                if not await ui._wait_csrf(page, tries=tries):
                    return False
                token = await page.evaluate('() => window.__latestCsrf || ""')
                if csrf is not None and isinstance(token, str):
                    csrf['token'] = token
            return strict_login(await query_context_login(context, token, LOGIN_URL))
        return await ui._wait_csrf(page, tries=tries) and strict_login(await query_login(page))
    except Exception as error:
        if 'Execution context was destroyed' in str(error) or 'Cannot find context with specified id' in str(error):
            print('页面正在跳转，继续等待登录检测。', flush=True)
            return False
        raise


def strict_login(response):
    if not isinstance(response, dict) or '__err' in response:
        return False
    code = response.get('code')
    if isinstance(code, bool):
        return False
    return code == 0 or (isinstance(code, str) and code.strip().upper() in {'0', 'OK', 'SUCCESS'})


def login_state(response):
    if strict_login(response):
        return 'valid'
    if not isinstance(response, dict) or '__err' in response:
        return 'unknown'
    code = response.get('code')
    if not isinstance(code, bool) and (code == 401 or (isinstance(code, str) and code.strip().upper() in {'401', 'NOT-LOGINED', 'NOT_LOGINED', 'NOTLOGINED', 'UNAUTHORIZED'})):
        return 'invalid'
    return 'unknown'


async def inspect_login(page, ui):
    try:
        if not await ui._wait_csrf(page, tries=25):
            return 'unknown'
        return login_state(await query_login(page))
    except Exception as error:
        if 'Execution context was destroyed' in str(error) or 'Cannot find context with specified id' in str(error):
            return 'unknown'
        raise


def target_datetime(session, now):
    times = ['10:00', '15:00'] if session == 'auto' else [session]
    for value in times:
        candidate = datetime.strptime(f'{now.date()} {value}', '%Y-%m-%d %H:%M')
        if candidate > now:
            return candidate
    return datetime.strptime(f'{now.date() + timedelta(days=1)} {times[0]}', '%Y-%m-%d %H:%M')


def load_core():
    import seckill as sf
    import seckill_ui as ui
    return sf, ui


async def query_login(page):
    return await page.evaluate('''async (url) => {
        try {
            const response = await fetch(url, {method: 'POST', credentials: 'include', signal: AbortSignal.timeout(10000),
                headers: {'Content-Type': 'application/json', 'x-csrf-token': window.__latestCsrf || ''}, body: '{}'});
            if (!response.ok) return {__err: 'http'};
            return await response.json();
        } catch (e) {return {__err: 'network'};}
    }''', VIP_URL)


def observe_csrf(context):
    state = {'token': ''}
    def capture(request):
        url = urlsplit(request.url)
        if url.scheme == 'https' and url.hostname == 'act-api.cloud.tencent.com':
            token = request.headers.get('x-csrf-token')
            if isinstance(token, str) and token:
                state['token'] = token
    context.on('request', capture)
    return state


async def query_context_login(context, token, referer):
    if not isinstance(token, str) or not token:
        return {'__err': 'csrf'}
    try:
        response = await context.request.post(VIP_URL, data='{}', timeout=5000, headers={
            'Content-Type':'application/json', 'Origin':'https://cloud.tencent.com',
            'Referer':referer, 'x-csrf-token':token,
        })
        try:
            return await response.json() if response.ok else {'__err':'http'}
        finally:
            await response.dispose()
    except Exception:
        return {'__err': 'network'}


async def verify_login_state(browser, ui, state, token, referer):
    # Recheck the cookie snapshot without loading another complete activity page.
    context = await browser.new_context(storage_state=state, user_agent=ui.UA)
    try:
        for attempt in range(3):
            if strict_login(await query_context_login(context, token, referer)):
                return await context.storage_state()
            if attempt < 2:
                print('复验暂未通过，稍后重试。', flush=True)
                await asyncio.sleep(.3)
        return None
    finally:
        await context.close()


async def save_state(ctx, path, state=None):
    temp = path.with_name(path.name + '.tmp')
    if state is None:
        await ctx.storage_state(path=str(temp))
    else:
        temp.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


async def publish_login_qr(page):
    emit('progress', phase='正在获取微信登录二维码')
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        for frame in page.frames:
            if urlsplit(frame.url).hostname != 'open.weixin.qq.com':
                continue
            image = frame.locator('img.qrcode:visible, img.js_qrcode_img:visible').first
            if await image.count() and await image.evaluate('(img) => img.complete && img.naturalWidth > 0'):
                png = await image.screenshot(type='png', timeout=10000)
                data_url = 'data:image/png;base64,' + base64.b64encode(png).decode('ascii')
                emit('qr', image=data_url)
                emit('progress', phase='等待微信扫码确认登录')
                return data_url
        await asyncio.sleep(.2)
    raise RuntimeError('二维码加载超时')


async def watch_scan_state(page, stop):
    last = 'waiting'
    while not stop.is_set():
        state = None
        for frame in page.frames:
            url = urlsplit(frame.url)
            if url.scheme != 'https' or url.hostname != 'open.weixin.qq.com':
                continue
            try:
                if await frame.locator('.js_wx_after_scan:visible').count():
                    state = 'scanned'
                elif await frame.locator('.js_wx_after_cancel:visible').count():
                    state = 'cancelled'
                elif await frame.locator('img.qrcode:visible, img.js_qrcode_img:visible').count():
                    state = 'waiting'
            except Exception:
                # OAuth navigation can detach the QR frame while verification continues.
                continue
        if state and state != last and not stop.is_set():
            last = state
            emit('scan', value=state)
            phase = {'scanned':'扫码成功，请在微信确认登录', 'cancelled':'扫码已取消，可刷新二维码重试', 'waiting':'等待微信扫码确认登录'}[state]
            emit('progress', phase=phase)
            if state == 'cancelled':
                return 'cancelled'
        if not stop.is_set():
            await asyncio.sleep(.15)


async def make_context(browser, sf, ui, state=None, url=None):
    kwargs = {'viewport': {'width': 1400, 'height': 900}, 'user_agent': ui.UA}
    if state:
        kwargs['storage_state'] = str(state)
    ctx = await browser.new_context(**kwargs)
    await ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    await ctx.add_init_script(sf.CSRF_HOOK_JS)
    page = await ctx.new_page()
    page.set_default_timeout(30000)
    emit('progress', phase='正在打开登录页面' if url else '正在打开活动页面')
    await page.goto(url or sf.ACTIVITY_URL, wait_until='domcontentloaded', timeout=30000)
    return ctx, page


async def run_browser_task(action, region, session, base, force_login=False, refresh_event=None):
    state_path = base / '.state.json'
    if action != 'login' and not state_path.exists():
        emit('login', value='missing')
        emit('needs_login')
        print('需要先登录，登录完成后再确认抢购。', flush=True)
        return False
    sf, ui = load_core()
    pw, browser = None, None
    try:
        emit('progress', phase='正在启动浏览器')
        pw = await sf.async_playwright().start()
        restore = state_path.exists() and not force_login
        login_url = LOGIN_URL + '?' + urlencode({'s_url': sf.ACTIVITY_URL})
        browser = await sf.launch_browser(pw, headless=True)
        ctx, page = await make_context(browser, sf, ui, state_path if restore else None, url=login_url if action == 'login' and not restore else None)
        if action == 'login' and restore:
            emit('progress', phase='正在恢复已保存的登录态')
            state = await inspect_login(page, ui)
            emit('login', value=state)
            if state == 'valid':
                await save_state(ctx, state_path)
                print('已恢复登录，无需再次扫码。', flush=True)
                return True
            if state == 'unknown':
                print('暂时无法验证登录，可能是网络或页面异常；保留登录态，不要求重新扫码。', flush=True)
                return False
            await browser.close()
            browser = None
            browser = await sf.launch_browser(pw, headless=True)
            ctx, page = await make_context(browser, sf, ui, url=login_url)
        if action == 'login':
            csrf = observe_csrf(ctx)
            await publish_login_qr(page)
            print('请扫描控制台弹窗中的微信二维码，最多等待10分钟。', flush=True)
            scan_stop = asyncio.Event()
            scan_task = asyncio.create_task(watch_scan_state(page, scan_stop))
            try:
                deadline = time.monotonic() + LOGIN_TIMEOUT_SECONDS
                while time.monotonic() < deadline:
                    if scan_task.done() and scan_task.result() == 'cancelled':
                        raise RuntimeError('微信登录已取消')
                    if not browser.is_connected():
                        print('扫码浏览器已关闭，请等待登录完成后再关闭。', flush=True)
                        return False
                    if refresh_event and refresh_event.is_set():
                        refresh_event.clear()
                        emit('qr', image=None)
                        await page.goto(login_url, wait_until='domcontentloaded', timeout=30000)
                        await publish_login_qr(page)
                    if await login_ready(page, ui, context=ctx, csrf=csrf):
                        scan_stop.set()
                        emit('progress', phase='正在确认登录')
                        snapshot = await ctx.storage_state()
                        verified = await verify_login_state(browser, ui, snapshot, csrf['token'], sf.ACTIVITY_URL)
                        valid = verified is not None
                        if valid:
                            await save_state(ctx, state_path, state=verified)
                        emit('login', value='valid' if valid else 'unknown')
                        print('登录态保存并复验通过。' if valid else '原登录态已保留，复验未通过；可稍后重试，不必立即重复扫码。', flush=True)
                        return valid
                    await asyncio.sleep(.3)
                emit('login', value='unknown')
                raise TimeoutError('扫码等待超时')
            finally:
                scan_stop.set()
                scan_task.cancel()
                await asyncio.gather(scan_task, return_exceptions=True)
        emit('progress', phase='正在校验登录与 CSRF')
        if not await ui._wait_csrf(page, tries=50):
            emit('login', value='unknown')
            print('未捕获到 CSRF token，本次任务不下单。', flush=True)
            return False
        response = await query_login(page)
        state = login_state(response)
        emit('login', value=state)
        if state != 'valid':
            if state == 'invalid':
                emit('needs_login')
                print('登录已过期，已阻止下单；请完成登录后再确认抢购。', flush=True)
            else:
                print('登录暂时无法验证，已阻止下单；请检查网络，无需立即重新登录。', flush=True)
            return False
        await save_state(ctx, state_path)
        print('登录验证通过，地域参数就绪。', flush=True)
        if action == 'connect':
            print('连通测试通过，全程未调用下单接口。', flush=True)
            return True
        source = sf.TEST_GOODS if action == 'test-order' else sf.FLASH_SALE
        goods = {**source, 'goods_param': {**source['goods_param'], 'regionId': region}}
        if action == 'grab':
            offset_ms = await sf.sync_time(page)
            now = datetime.fromtimestamp(time.time() + offset_ms / 1000)
            target = target_datetime(session, now)
            emit('progress', phase='等待目标场次', target_at=target.timestamp(), offset_ms=offset_ms)
            print(f'目标：{target:%Y-%m-%d %H:%M:%S}；北京时间请确保本机时区为 UTC+8。', flush=True)
            resynced, warmed_up = False, False
            last_minute = None
            while True:
                if not browser.is_connected():
                    print('任务浏览器已关闭。', flush=True)
                    return False
                remaining = target.timestamp() - (time.time() + offset_ms / 1000)
                if remaining <= 180 and not resynced:
                    offset_ms = await sf.sync_time(page)
                    emit('progress', phase='等待目标场次（已重新对时）', offset_ms=offset_ms)
                    resynced = True
                    continue
                if remaining * 1000 <= -sf.ADVANCE_MS:
                    break
                if remaining <= sf.WARMUP_SECONDS and not warmed_up:
                    # Existing warmup calls do-goods and may create an order; use a harmless query.
                    if not strict_login(await query_login(page)):
                        emit('login', value='unknown')
                        print('开抢前登录复验失败，已阻止下单。', flush=True)
                        return False
                    warmed_up = True
                    print('无下单预热完成。', flush=True)
                minute = int(remaining // 60)
                if minute != last_minute:
                    print(f'距离目标场次还有 {max(0, int(remaining))} 秒。', flush=True)
                    last_minute = minute
                await asyncio.sleep(.05 if remaining <= 5 else 1)
        emit('progress', phase='正在发送下单请求')
        print('执行已确认的真实下单操作；请勿重复启动。', flush=True)
        success = await sf.rapid_purchase(page, goods, duration=5) if action == 'test-order' else await sf.rapid_purchase(page, goods)
        if success:
            # Preserve confirmed order truth even if cancellation happens during cleanup.
            emit('result', state='succeeded', message='下单已确认成功，请在腾讯云控制台核实并及时付款或取消。')
        return success
    finally:
        try:
            if browser:
                try:
                    await asyncio.wait_for(browser.close(), timeout=5)
                except Exception:
                    pass
        finally:
            if pw:
                try:
                    await asyncio.wait_for(pw.stop(), timeout=5)
                except Exception:
                    pass


async def run_demo(action, region, session, refresh_event=None):
    print('模拟任务已启动，不访问腾讯云、不创建订单。', flush=True)
    emit('progress', phase='模拟：检查浏览器环境')
    await asyncio.sleep(.4)
    if action == 'login':
        emit('qr', image=DEMO_QR)
        emit('progress', phase='模拟二维码，不可扫码')
        for _ in range(50):
            if refresh_event and refresh_event.is_set():
                refresh_event.clear()
                emit('qr', image=DEMO_QR)
                emit('progress', phase='模拟二维码已刷新，不可扫码')
            await asyncio.sleep(.1)
    emit('login', value='valid')
    print('模拟：登录态校验通过。', flush=True)
    if action == 'grab':
        target = time.time() + 90
        emit('progress', phase='模拟：等待目标场次', target_at=target, offset_ms=0)
        for _ in range(90):
            await asyncio.sleep(1)
    else:
        await asyncio.sleep(.6)
    print('模拟流程完成，无真实订单。', flush=True)
    return True


async def execute(args):
    refresh_event = asyncio.Event()
    task = asyncio.create_task(run_demo(args.action, args.region, args.session, refresh_event) if args.demo else
                               run_browser_task(args.action, args.region, args.session, args.base, force_login=getattr(args, 'force_login', False), refresh_event=refresh_event))
    loop = asyncio.get_running_loop()

    def listen():
        try:
            # EOF means the owning server exited; clean our browser up too.
            for line in sys.stdin:
                if line.strip() == 'refresh':
                    loop.call_soon_threadsafe(refresh_event.set)
                    continue
                if line.strip() == 'stop':
                    break
            if not task.done():
                loop.call_soon_threadsafe(task.cancel)
        except (OSError, RuntimeError):
            pass

    threading.Thread(target=listen, daemon=True).start()
    try:
        ok = await task
        if args.demo:
            message = '模拟任务完成，未创建真实订单。' if ok else '模拟任务失败。'
        elif args.action in {'grab', 'test-order'}:
            message = '下单成功，请前往腾讯云控制台核实订单并及时付款或取消。' if ok else '未确认下单成功，请查看日志；网络异常时请在控制台核实订单。'
        else:
            if ok:
                message = '登录验证通过。'
            elif args.action == 'login' and (args.base / '.state.json').exists():
                message = '本地登录态已保留，复验未通过；可稍后重试。'
            else:
                message = '登录或连通验证失败，请检查网络或登录态。'
        emit('result', state='succeeded' if ok else 'failed', message=message)
    except asyncio.CancelledError:
        emit('result', state='stopped', message='登录已取消，原登录态保留。' if args.action == 'login' else '任务已停止；已创建的订单不会撤销。')
    except Exception as e:
        print(f'任务异常（{type(e).__name__}）：{safe_error_detail(e)}', flush=True)
        frames = traceback.extract_tb(e.__traceback__)
        if frames:
            frame = frames[-1]
            print(f'出错位置：{Path(frame.filename).name}:{frame.lineno} ({frame.name})', flush=True)
        message = '任务异常退出，购买操作的订单状态请自行核实。' if args.action in {'grab', 'test-order'} else '登录或连通检测失败：' + safe_error_detail(e)
        if args.action == 'login' and (args.base / '.state.json').exists():
            emit('login', value='unknown')
            message += ' 本地登录态已保留，可稍后重试。'
        emit('result', state='failed', message=message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--action', choices=['login', 'connect', 'grab', 'test-order'], required=True)
    parser.add_argument('--region', type=int, choices=[1, 4, 8], default=8)
    parser.add_argument('--session', choices=['auto', '10:00', '15:00'], default='auto')
    parser.add_argument('--base', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--force-login', action='store_true')
    asyncio.run(execute(parser.parse_args()))


if __name__ == '__main__':
    main()
