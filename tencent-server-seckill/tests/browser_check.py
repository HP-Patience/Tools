"""Browser regression against an isolated, explicitly simulated local server."""
import json
from pathlib import Path
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from seckill_web import TaskManager, make_server
from playwright.sync_api import sync_playwright, expect


def assert_button_styles(page):
    missing = page.locator('button:visible').evaluate_all("""buttons => buttons.filter(button => {
        const style = getComputedStyle(button);
        return parseFloat(style.borderTopWidth) < 1 || style.borderTopStyle === 'none'
            || style.borderTopColor === 'rgba(0, 0, 0, 0)' || style.boxShadow === 'none';
    }).map(button => button.id || button.textContent.trim())""")
    assert not missing, missing


def main():
    with tempfile.TemporaryDirectory() as tmp:
        manager = TaskManager(Path(tmp), demo=True)
        server = make_server(manager, port=0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, channel='chrome')
                try:
                    page = browser.new_page(viewport={'width':1440, 'height':1100}, reduced_motion='reduce')
                    errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
                    url = f'http://127.0.0.1:{server.server_port}'
                    page.goto(url)
                    page.wait_for_load_state('networkidle')
                    expect(page.locator('#connection')).to_have_attribute('aria-label', '本地服务已连接')
                    expect(page.locator('#demo-banner')).to_be_visible()
                    expect(page.locator('#task-status')).to_have_text('空闲')
                    assert manager.task is None
                    assert_button_styles(page)
                    assert page.locator('.page-footer').count() == 0
                    assert page.locator('.log-controls #console-link').count() == 1
                    assert page.locator('#console-link').evaluate("el => parseFloat(getComputedStyle(el).borderTopWidth) >= 1 && getComputedStyle(el).boxShadow !== 'none'")
                    assert page.locator('.brand-icon, .nav-symbol, .metric-title > span, .product-icon, .arrow, .cursor, .dialog-symbol').count() == 0
                    assert page.locator('html').evaluate('(el) => getComputedStyle(el).scrollBehavior') == 'auto'
                    assert page.locator('button:visible').evaluate_all("buttons => buttons.every(b => getComputedStyle(b).transitionDuration === '0s' && getComputedStyle(b).animationName === 'none')")
                    before = page.locator('#grab-btn').evaluate("el => [getComputedStyle(el).backgroundColor, getComputedStyle(el).boxShadow, getComputedStyle(el).borderColor]")
                    page.locator('#grab-btn').hover()
                    after = page.locator('#grab-btn').evaluate("el => [getComputedStyle(el).backgroundColor, getComputedStyle(el).boxShadow, getComputedStyle(el).borderColor]")
                    assert before == after
                    page.evaluate("window.originalConnectionDot = document.querySelector('#connection i')")
                    page.wait_for_timeout(1300)
                    assert page.evaluate("window.originalConnectionDot === document.querySelector('#connection i')")
                    assert page.locator('#guide, a[href="#guide"], .heading').count() == 0
                    assert page.locator('#connect-btn, #order-btn, #account-menu, #account-toggle, #login-btn, .step-number, .step-label').count() == 0
                    expect(page.locator('#relogin-btn')).to_have_text('更换账号')
                    assert '真实测试下单' not in page.locator('body').inner_text()
                    expect(page.locator('#grab-btn')).to_have_text('开始抢购')
                    for decoration in ('.eyebrow', '.nav-caption', '.nav-index', '.section-no', '.metric-code', '.terminal-top', '.readiness'):
                        assert page.locator(decoration).count() == 0, decoration
                    for text in ('CONFIGURATION', 'NEXT LAUNCH', 'PREPARE', 'Shanghai', 'LOCAL EDITION', '每一场，都准备好。', '非腾讯云官方产品', '活动与价格以官方页面为准'):
                        assert text not in page.locator('body').inner_text(), text
                    assert page.locator('#confirm-dialog .dialog-note').inner_text().startswith('停止任务不会撤销')
                    assert page.locator('.field-hint, .launch-warning, #login-detail, #schedule-pill, #sync-label').count() == 0
                    expect(page.locator('#task-detail')).not_to_be_visible()
                    expect(page.locator('#connection')).to_have_text('')
                    assert '尚未启动' not in page.locator('#countdown-label').inner_text()
                    expect(page.locator('.session-options')).to_have_attribute('title', '已结束的指定场次自动顺延至次日')
                    assert page.locator('#task-detail').evaluate('(el) => parseFloat(getComputedStyle(el).fontSize)') >= 12
                    config_requests = []
                    page.route('**/api/config', lambda route: config_requests.append(route))
                    page.get_by_role('button', name='上海', exact=True).click()
                    page.wait_for_timeout(100)
                    expect(page.locator('#grab-btn')).to_be_enabled()
                    assert page.locator('#grab-btn').evaluate('(el) => getComputedStyle(el).opacity') == '1'
                    page.get_by_role('button', name='北京', exact=True).click()
                    assert len(config_requests) == 1
                    config_requests[0].continue_()
                    page.unroute('**/api/config')
                    expect(page.locator('#region-label')).to_have_text('上海')
                    assert json.loads((Path(tmp)/'config.json').read_text(encoding='utf-8'))['region'] == 4
                    page.get_by_role('button', name='15:00', exact=True).click()
                    expect(page.locator('#target-label')).to_contain_text('15:00')
                    page.locator('#grab-btn').click()
                    expect(page.locator('#login-dialog')).to_be_visible()
                    expect(page.locator('#confirm-dialog')).not_to_be_visible()
                    page.locator('#cancel-login').click()
                    assert manager.task is None
                    page.locator('#grab-btn').click()
                    page.locator('#execute-login').click()
                    expect(page.locator('#qr-dialog')).to_be_visible(timeout=5000)
                    expect(page.locator('#qr-image')).to_be_visible(timeout=5000)
                    assert page.locator('#qr-image').evaluate('(img) => img.complete && img.naturalWidth > 0')
                    expect(page.locator('#qr-lock-note')).to_have_text('扫码后登录会自动校验，请等待二维码消失再操作')
                    expect(page.locator('#cancel-qr')).to_be_disabled()
                    expect(page.locator('#refresh-qr')).to_be_disabled()
                    expect(page.locator('#stop-btn')).to_be_disabled()
                    assert page.locator('.workspace').evaluate('(el) => el.inert')
                    assert page.locator('.sidebar').evaluate('(el) => el.inert')
                    page.keyboard.press('Escape')
                    expect(page.locator('#qr-dialog')).to_be_visible()
                    page.mouse.click(5,5)
                    expect(page.locator('#qr-dialog')).to_be_visible()

                    # The verifying phase replaces the QR with a scoped loading animation.
                    page.route('**/api/status', lambda route: route.fulfill(json={
                        **manager.status(), 'busy':True,
                        'task':{**manager.task, 'state':'running', 'phase':'等待微信扫码确认登录', 'scan_state':'scanned', 'login_confirmed':False}
                    }))
                    expect(page.locator('#qr-verifying')).to_be_visible(timeout=1500)
                    expect(page.locator('.qr-image-box')).not_to_be_visible()
                    expect(page.locator('#qr-status')).to_contain_text('请在微信确认')
                    expect(page.locator('#refresh-qr')).to_be_disabled()
                    expect(page.locator('#cancel-qr')).to_be_disabled()
                    page.emulate_media(reduced_motion='no-preference')
                    assert page.locator('.qr-verification-spinner').evaluate('(el) => getComputedStyle(el).animationName') == 'qr-verifying-spin'
                    page.emulate_media(reduced_motion='reduce')
                    assert page.locator('.qr-verification-spinner').evaluate('(el) => getComputedStyle(el).animationName') == 'none'
                    page.unroute('**/api/status')
                    # Confirmed login closes the QR before subprocess cleanup finishes.
                    page.route('**/api/status', lambda route: route.fulfill(json={
                        **manager.status(), 'login':'valid', 'busy':True,
                        'task':{**manager.task, 'state':'running', 'login_confirmed':True, 'qr_image':None}
                    }))
                    expect(page.locator('#qr-dialog')).not_to_be_visible(timeout=1500)
                    page.unroute('**/api/status')
                    expect(page.locator('#qr-dialog')).to_be_visible(timeout=1500)
                    # Simulate a terminal timeout, not a user cancellation of the locked dialog.
                    manager.stop(manager.task['id'])
                    page.route('**/api/status', lambda route: route.fulfill(json={
                        **manager.status(), 'busy':False,
                        'task':{**manager.task, 'state':'failed', 'login_confirmed':False, 'message':'扫码等待超时，请重新登录。'}
                    }))
                    expect(page.locator('#qr-dialog')).not_to_be_visible(timeout=5000)
                    expect(page.locator('#toast')).to_contain_text('超时')
                    expect(page.locator('#grab-btn')).to_be_enabled()
                    assert not page.locator('.workspace').evaluate('(el) => el.inert')
                    assert not page.locator('.sidebar').evaluate('(el) => el.inert')
                    page.unroute('**/api/status')
                    expect(page.locator('#task-status')).to_have_text('已停止', timeout=10000)
                    expect(page.locator('#qr-dialog')).not_to_be_visible()
                    assert manager.task['qr_image'] is None
                    page.locator('#grab-btn').click()
                    page.locator('#execute-login').click()
                    expect(page.locator('#qr-image')).to_be_visible(timeout=5000)
                    # A disconnected service must not leave the controller permanently inert.
                    page.route('**/api/status', lambda route: route.abort())
                    expect(page.locator('#qr-dialog')).not_to_be_visible(timeout=5000)
                    expect(page.locator('#toast')).to_contain_text('连接中断')
                    assert not page.locator('.workspace').evaluate('(el) => el.inert')
                    page.unroute('**/api/status')
                    expect(page.locator('#qr-dialog')).to_be_visible(timeout=5000)
                    assert page.locator('.workspace').evaluate('(el) => el.inert')
                    expect(page.locator('#refresh-qr')).to_be_disabled()
                    expect(page.locator('#cancel-qr')).to_be_disabled()
                    expect(page.locator('#task-status')).to_have_text('已完成', timeout=10000)
                    expect(page.locator('#qr-dialog')).not_to_be_visible()
                    assert manager.task['action'] == 'login'
                    assert manager.task['qr_image'] is None
                    assert not page.locator('.workspace').evaluate('(el) => el.inert')
                    assert not page.locator('.sidebar').evaluate('(el) => el.inert')
                    expect(page.locator('#login-status')).to_have_text('已登录')
                    assert manager.task['action'] == 'login'
                    assert manager.task['force_login'] is False
                    expect(page.locator('#login-dialog')).not_to_be_visible()
                    page.locator('#grab-btn').click()
                    expect(page.locator('#confirm-dialog')).to_be_visible()
                    assert page.locator('#confirm-dialog').evaluate('(el) => getComputedStyle(el, "::backdrop").backdropFilter') == 'none'
                    assert_button_styles(page)
                    expect(page.locator('#execute-confirm')).to_be_disabled()
                    expect(page.locator('#cancel-confirm')).to_be_focused()
                    page.keyboard.press('Escape')
                    expect(page.locator('#confirm-dialog')).not_to_be_visible()
                    assert manager.task['action'] == 'login'
                    page.locator('#grab-btn').click()
                    page.locator('#risk-check').check()
                    page.get_by_role('button', name='确认执行', exact=True).click()
                    expect(page.locator('#stop-btn')).to_be_visible()
                    expect(page.locator('[data-region="1"]')).to_be_disabled()
                    expect(page.locator('#target-label')).to_contain_text('模拟', timeout=10000)
                    expect(page.locator('#task-detail')).to_be_visible()
                    expect(page.locator('#task-detail')).to_contain_text('等待目标场次')
                    page.set_viewport_size({'width': 1366, 'height': 768})
                    assert page.evaluate('document.documentElement.scrollHeight <= window.innerHeight')
                    task_id = manager.task['id']
                    page.reload()
                    expect(page.locator('#stop-btn')).to_be_visible()
                    assert manager.task['id'] == task_id
                    expect(page.locator('[data-session="15:00"]')).to_have_attribute('aria-pressed', 'true')
                    page.get_by_role('button', name='停止当前任务', exact=False).click()
                    expect(page.locator('#task-status')).to_have_text('已停止', timeout=10000)
                    page.locator('[data-session="10:00"]').click()
                    expect(page.locator('#target-label')).to_contain_text('10:00')
                    page.wait_for_timeout(1600)
                    expect(page.locator('#target-label')).to_contain_text('10:00')
                    manager.add_log('<img src=x onerror="alert(1)">')
                    expect(page.locator('#logs')).to_contain_text('<img src=x', timeout=5000)
                    assert page.locator('#logs img').count() == 0
                    page.locator('#follow-btn').click()
                    expect(page.locator('#follow-btn')).to_have_attribute('aria-pressed', 'false')
                    page.locator('#clear-btn').click()
                    expect(page.locator('#logs')).to_contain_text('已清空本页显示')
                    page.reload()
                    expect(page.locator('#logs')).to_contain_text('<img src=x', timeout=5000)
                    page.route('**/api/status', lambda route: route.abort())
                    expect(page.locator('#connection')).to_contain_text('连接中断', timeout=5000)
                    expect(page.locator('#grab-btn')).to_be_disabled()
                    page.unroute('**/api/status')
                    expect(page.locator('#connection')).to_have_attribute('aria-label', '本地服务已连接', timeout=5000)
                    expect(page.locator('#grab-btn')).to_be_enabled()
                    with manager.lock:
                        manager.task.update(state='failed', phase='浏览器启动失败', message='请检查浏览器环境')
                    expect(page.locator('#task-detail')).to_have_text('浏览器启动失败', timeout=5000)
                    expect(page.locator('#task-detail')).to_be_visible()
                    for i in range(100):
                        manager.add_log('compact layout fixture ' + str(i))
                    expect(page.locator('#logs')).to_contain_text('compact layout fixture 99', timeout=5000)
                    for width, height in ((1440, 900), (1366, 768), (1280, 720), (1024, 768), (1024, 640)):
                        page.set_viewport_size({'width': width, 'height': height})
                        assert page.evaluate('document.documentElement.scrollHeight <= window.innerHeight'), (width, height)
                        for selector in ('#relogin-btn', '#grab-btn', '#logs'):
                            box = page.locator(selector).bounding_box()
                            assert box and box['y'] >= 0 and box['y'] + box['height'] <= height, (selector, box)
                        assert page.locator('#logs').bounding_box()['height'] >= 80, (width, height, page.locator('#logs').bounding_box())
                    assert page.locator('#logs').evaluate('(el) => el.scrollHeight > el.clientHeight')
                    for width in (1440, 768, 390, 320):
                        page.set_viewport_size({'width':width, 'height':900})
                        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), width
                    page.set_viewport_size({'width':1366, 'height':768})
                    page.locator('#relogin-btn').click()
                    expect(page.locator('#login-title')).to_have_text('更换账号')
                    expect(page.locator('#execute-login')).to_have_text('更换账号')
                    expect(page.locator('#login-description')).to_have_text('扫码登录新账号，成功后自动切换。')
                    page.locator('#execute-login').click()
                    expect(page.locator('#task-kind')).to_have_text('扫码登录', timeout=5000)
                    expect(page.locator('#task-status')).to_have_text('已完成', timeout=10000)
                    assert manager.task['force_login'] is True
                    page.locator('#grab-btn').click()
                    page.locator('#risk-check').check()
                    page.locator('#execute-confirm').click()
                    expect(page.locator('#stop-btn')).to_be_visible()
                    with manager.lock:
                        manager.login = 'invalid'
                        manager.task.update(requires_login=True, state='failed', phase='登录已过期')
                    expect(page.locator('#login-dialog')).to_be_visible(timeout=5000)
                    page.locator('#cancel-login').click()
                    page.wait_for_timeout(1300)
                    expect(page.locator('#login-dialog')).not_to_be_visible()
                    # Cleanup the simulated worker without issuing another purchase.
                    with manager.lock:
                        manager.task['state'] = 'running'
                    manager.stop(manager.task['id'])
                    expect(page.locator('#task-status')).to_have_text('已停止', timeout=10000)
                    with manager.lock:
                        manager.login = 'unknown'
                        manager.task.update(state='failed', requires_login=False, phase='网络暂不可用')
                    expect(page.locator('#task-detail')).to_have_text('网络暂不可用', timeout=5000)
                    expect(page.locator('#login-dialog')).not_to_be_visible()
                    assert not [e for e in errors if e != 'Failed to load resource: net::ERR_FAILED'], errors
                    print('PASS: QR lock/Escape/backdrop/timeout unlock/highlight/auto-close, scan transition/reduced-motion, streamlined auth, restore/explicit account switch, expiry vs network, config, confirm cancel/execute, reload recovery, stop, log escaping, clear/follow, disconnect recovery, 1440/768/390/320px, zero unexpected console errors')
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            manager.close()


if __name__ == '__main__':
    main()
