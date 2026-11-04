'use strict';
const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="console-token"]').content;
const regions = {4: ['上海', 'CN-SHANGHAI'], 8: ['北京', 'CN-BEIJING'], 1: ['广州', 'CN-GUANGZHOU']};
const actions = {login: '扫码登录', connect: '连通测试', grab: '抢购任务', 'test-order': '测试下单'};
const states = {running: '运行中', stopping: '停止中', stopped: '已停止', succeeded: '已完成', failed: '未完成'};
const loginLabels = {
  missing: '未登录',
  saved: '已保存 · 待校验',
  valid: '已登录',
  invalid: '登录已失效',
  unknown: '验证未通过',
};
let status = null, online = false, pending = false, session = 'auto', cursor = 0;
let follow = true, toastTimer, confirmAction = null, selectedTarget = null;
let clockDelta = 0, previewSession = false;
let pollTimer, polling = false;
let forceLogin = false, requestedTaskId = null, loginOfferedFor = null;
let qrTaskId = null, qrErrorId = null;
const dateFormat = new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false});
const clockFormat = new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false});

function notify(message, error = false) {
  clearTimeout(toastTimer);
  $('toast').textContent = message;
  $('toast').classList.toggle('error', error);
  $('toast').hidden = false;
  toastTimer = setTimeout(() => { $('toast').hidden = true; }, error ? 8000 : 4500);
}
async function api(path, data) {
  const options = {cache: 'no-store', signal: AbortSignal.timeout(7000)};
  if (data !== undefined) {
    options.method = 'POST';
    options.headers = {'Content-Type': 'application/json', 'X-Console-Token': token};
    options.body = JSON.stringify(data);
  }
  const response = await fetch(path, options);
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `服务错误 (${response.status})`);
  return result;
}
function qrLocked() {
  return Boolean(online && status?.busy && status.task?.action === 'login' && !status.task.login_confirmed);
}
function updateControls() {
  const locked = qrLocked();
  document.querySelector('.workspace').inert = locked;
  document.querySelector('.sidebar').inert = locked;
  ['follow-btn', 'clear-btn'].forEach((id) => {$(id).disabled = locked;});
  $('console-link').setAttribute('aria-disabled', String(locked));
  const busy = Boolean(status?.busy), blocked = busy || !online;
  document.querySelectorAll('[data-region], [data-session]').forEach((b) => {b.disabled = blocked;});
  ['relogin-btn', 'grab-btn'].forEach((id) => {$(id).disabled = blocked;});
  $('stop-btn').hidden = !busy;
  $('stop-btn').disabled = locked || pending || !online || status?.task?.state === 'stopping';
  $('grab-btn').hidden = busy;
  $('execute-confirm').disabled = !$('risk-check').checked || pending || blocked;
  $('execute-login').disabled = pending || blocked;
  $('refresh-qr').disabled = locked || pending || !online || !status?.task?.qr_image || status.task.phase === '正在确认登录' || status.task.scan_state === 'scanned';
  $('cancel-qr').disabled = locked || pending || !online;
}
function syncSessionButtons() {
  document.querySelectorAll('[data-session]').forEach((b) => {
    const active = b.dataset.session === session;
    b.classList.toggle('selected', active);
    b.setAttribute('aria-pressed', String(active));
  });
}
function nearestTarget(nowMs, selected) {
  const offset = 8 * 3600 * 1000;
  const local = new Date(nowMs + offset);
  const base = Date.UTC(local.getUTCFullYear(), local.getUTCMonth(), local.getUTCDate()) - offset;
  const hours = selected === 'auto' ? [10, 15] : [Number(selected.slice(0, 2))];
  for (const hour of hours) {
    const candidate = base + hour * 3600 * 1000;
    if (candidate > nowMs) return candidate;
  }
  return base + (24 + hours[0]) * 3600 * 1000;
}
function setText(id, text) {
  const element = $(id);
  if (element.textContent !== text) element.textContent = text;
}
function updateClock() {
  const now = Date.now() + clockDelta;
  setText('clock', clockFormat.format(new Date(now)));
  const task = status?.task;
  const runningGrab = status?.busy && task?.action === 'grab';
  const retainedTarget = !previewSession && task?.action === 'grab' && task?.target_at;
  let target;
  if (runningGrab && !task.target_at) {
    ['hours', 'minutes', 'seconds'].forEach((id) => setText(id, '--'));
    setText('target-label', '校验与对时后确定');
    setText('countdown-label', '正在准备任务');
    return;
  }
  if (retainedTarget && (status.busy || ['succeeded', 'failed', 'stopped'].includes(task.state))) {
    target = task.target_at * 1000;
  } else {
    if (!selectedTarget) selectedTarget = nearestTarget(now, session);
    if (!status?.busy && now > selectedTarget) selectedTarget = nearestTarget(now, session);
    target = selectedTarget;
  }
  const adjustedNow = retainedTarget ? now + (task.offset_ms || 0) : now;
  const remaining = Math.max(0, Math.ceil((target - adjustedNow) / 1000));
  setText('hours', String(Math.floor(remaining / 3600)).padStart(2, '0'));
  setText('minutes', String(Math.floor((remaining % 3600) / 60)).padStart(2, '0'));
  setText('seconds', String(remaining % 60).padStart(2, '0'));
  setText('target-label', dateFormat.format(new Date(target)) + (retainedTarget && status.demo ? ' · 模拟' : ' 场'));
  setText('countdown-label', runningGrab ? '距离任务目标时间' : retainedTarget ? '上次任务目标时间' : '距离所选场次');
}
function renderStatus(data) {
  if (data.task?.id !== status?.task?.id) previewSession = false;
  status = data;
  if (data.busy && data.task) {
    session = data.task.session;
    syncSessionButtons();
  }
  clockDelta = data.server_time * 1000 - Date.now();
  $('demo-banner').hidden = !data.demo;
  const region = regions[data.region] || regions[8];
  $('region-label').textContent = region[0];
  document.querySelectorAll('[data-region]').forEach((b) => {
    const selected = Number(b.dataset.region) === data.region;
    b.classList.toggle('selected', selected);
    b.setAttribute('aria-pressed', String(selected));
  });
  const label = loginLabels[data.login] || loginLabels.unknown;
  $('login-status').textContent = label;
  $('login-dot').className = 'status-dot ' + (data.login === 'valid' ? 'valid' : data.login === 'missing' ? '' : 'warn');
  const task = data.task;
  $('task-status').textContent = task ? states[task.state] : '空闲';
  $('task-kind').textContent = task ? actions[task.action] : '';
  $('task-kind').hidden = !task;
  $('task-detail').textContent = data.config_error || task?.phase || '';
  $('task-detail').hidden = !$('task-detail').textContent;
  $('task-detail').title = task?.message || task?.phase || '';
  $('task-dot').className = 'status-dot ' + (data.busy || task?.state === 'succeeded' ? 'valid' : task?.state === 'failed' ? 'warn' : '');
  updateControls();
  updateClock();
  updateQrDialog(data);
  if (!data.busy && task?.requires_login && task.id === requestedTaskId && loginOfferedFor !== task.id) {
    loginOfferedFor = task.id;
    offerLogin(false);
  }
}
function closeQrDialog() {
  if ($('qr-dialog').open) $('qr-dialog').close();
  $('qr-image').removeAttribute('src');
  $('qr-image').hidden = true;
  $('qr-verifying').hidden = true;
  document.querySelector('.workspace').inert = false;
  document.querySelector('.sidebar').inert = false;
}

function updateQrDialog(data) {
  const task = data.task;
  if (task?.action !== 'login' || !['running','stopping'].includes(task.state) || task.login_confirmed) {
    closeQrDialog();
    if (task?.action === 'login' && ['failed','stopped'].includes(task.state) && !task.login_confirmed && task.id === qrTaskId && qrErrorId !== task.id) {
      qrErrorId = task.id;
      notify(task.message || '登录未完成，请重试。', true);
    }
    return;
  }
  qrTaskId = task.id;
  if (!$('qr-dialog').open) $('qr-dialog').showModal();
  const confirming = task.phase === '正在确认登录';
  const scanned = task.scan_state === 'scanned';
  const verifying = confirming || scanned;
  $('qr-verifying').hidden = !verifying;
  document.querySelector('.qr-image-box').hidden = verifying;
  setText('qr-title', confirming ? '确认登录' : scanned ? '扫码成功' : '微信扫码登录');
  const image = task.qr_image;
  if (image && image.startsWith('data:image/png;base64,')) {
    if ($('qr-image').getAttribute('src') !== image) $('qr-image').src = image;
    $('qr-image').hidden = false;
    $('qr-loading').hidden = true;
  } else {
    $('qr-image').hidden = true;
    $('qr-loading').hidden = false;
  }
  const message = confirming ? '正在验证登录…' : scanned ? '扫码成功，请在微信确认登录…' : task.scan_state === 'cancelled' ? '已取消，请刷新二维码重新扫码。' : task.phase || '请使用微信扫码并确认登录';
  setText('qr-status', data.demo ? '模拟：' + message : message);
}

function appendLogs(data) {
  if (!data.entries.length) return;
  $('log-empty')?.remove();
  if (data.truncated) appendLine({time: '--:--:--', level: 'warning', message: '早期日志已超出缓存，仅展示最近 1,000 条。'});
  data.entries.forEach(appendLine);
  cursor = data.last_seq;
  while ($('logs').children.length > 1000) $('logs').firstElementChild.remove();
  if (follow) $('logs').scrollTop = $('logs').scrollHeight;
}
function appendLine(entry) {
  const row = document.createElement('div');
  row.className = 'log-row ' + (['warning', 'success'].includes(entry.level) ? entry.level : 'info');
  const items = [['log-time', entry.time], ['log-message', entry.message]];
  items.forEach(([className, text]) => {
    const span = document.createElement('span');
    span.className = className;
    span.textContent = text;
    row.appendChild(span);
  });
  $('logs').appendChild(row);
}
async function poll() {
  if (polling) return;
  polling = true;
  try {
    const data = await api('/api/status');
    if (!online) {
      $('connection').classList.remove('offline');
      $('connection').replaceChildren(document.createElement('i'));
      $('connection').setAttribute('aria-label', '本地服务已连接');
      $('connection').title = '本地服务已连接';
    }
    online = true;
    if (data.last_seq < cursor) {
      cursor = 0;
      $('logs').replaceChildren();
    }
    renderStatus(data);
    appendLogs(await api(`/api/logs?after=${cursor}`));
  } catch (_) {
    if ($('connection').getAttribute('aria-label') !== '连接中断 · 正在重试') {
      $('connection').classList.add('offline');
      $('connection').replaceChildren(document.createElement('i'), document.createTextNode('连接中断 · 正在重试'));
      $('connection').setAttribute('aria-label', '连接中断 · 正在重试');
      $('connection').title = '连接中断 · 正在重试';
    }
    online = false;
    if ($('qr-dialog').open) {
      closeQrDialog();
      notify('本地服务连接中断，无法确认登录结果。恢复连接后请核实。', true);
    }
    updateControls();
  } finally {
    polling = false;
    pollTimer = setTimeout(poll, online && status?.busy && status.task.action === 'login' ? 250 : 1000);
  }
}
async function startTask(action, confirmed = false, force_login = false) {
  if (pending || status?.busy || !online) return;
  pending = true;
  updateControls();
  try {
    const task = await api('/api/tasks', {action, region: status.region, session, confirmed, force_login});
    requestedTaskId = task.id;
    renderStatus({...status, task, busy: true});
    if (action === 'login' && !polling) {
      clearTimeout(pollTimer);
      poll();
    }
    notify(action === 'login' ? '正在恢复登录；需要扫码时会在本页显示二维码。' : '任务已启动，可在日志中查看进展。');
  } catch (error) { notify(error.message, true); }
  finally {pending = false; updateControls();}
}
function showConfirmation() {
  if (pending || status?.busy || !online) return;
  if (['missing', 'invalid'].includes(status.login)) {
    offerLogin(false);
    return;
  }
  confirmAction = 'grab';
  $('confirm-dialog').returnValue = '';
  $('risk-check').checked = false;
  $('execute-confirm').disabled = true;
  $('confirm-title').textContent = '确认开始抢购？';
  $('confirm-description').textContent = status.demo ? '当前为模拟模式，不访问腾讯云，不会产生真实订单。' : '到达目标时间后，将自动调用真实下单接口。';
  $('confirm-product').textContent = '轻量 4 核 4G 3M · 38 元/年（配置值）';
  $('confirm-region').textContent = regions[status.region][0];
  $('confirm-session').textContent = session === 'auto' ? '最近一场（10:00 / 15:00）' : `${session}（已过则次日）`;
  $('confirm-dialog').showModal();
}
function offerLogin(force) {
  if (pending || status?.busy || !online) return;
  forceLogin = force;
  $('login-dialog').returnValue = '';
  $('login-title').textContent = force ? '更换账号' : '需要登录';
  $('login-description').textContent = force ? '扫码登录新账号，成功后自动切换。' : '微信扫码登录后，再确认抢购。';
  $('execute-login').textContent = force ? '更换账号' : '扫码登录';
  $('login-dialog').showModal();
}
$('login-dialog').addEventListener('close', () => {
  if ($('login-dialog').returnValue === 'login') startTask('login', false, forceLogin);
});
$('relogin-btn').addEventListener('click', () => offerLogin(true));
$('grab-btn').addEventListener('click', showConfirmation);
$('risk-check').addEventListener('change', updateControls);
$('confirm-dialog').addEventListener('close', () => {
  const action = confirmAction;
  confirmAction = null;
  if ($('confirm-dialog').returnValue === 'confirm' && $('risk-check').checked && action) startTask(action, true);
});
async function stopCurrentTask() {
  if (qrLocked()) return;
  if (!status?.task || pending || !online) return;
  pending = true; updateControls();
  try {
    const task = await api('/api/tasks/stop', {id: status.task.id});
    renderStatus({...status, task, busy: ['running', 'stopping'].includes(task.state)});
    notify(task.action === 'login' ? '正在取消登录，原登录态保留。' : '正在停止任务。此操作不会撤销已创建的订单。');
  } catch (error) {notify(error.message, true);}
  finally {pending = false; updateControls();}
}
$('stop-btn').addEventListener('click', stopCurrentTask);
$('cancel-qr').addEventListener('click', stopCurrentTask);
$('qr-dialog').addEventListener('cancel', (event) => {
  event.preventDefault();
  if (qrLocked()) return;
  if (status?.busy) stopCurrentTask();
  else closeQrDialog();
});
$('refresh-qr').addEventListener('click', async () => {
  if (qrLocked() || pending || !online || status?.task?.action !== 'login') return;
  pending = true;
  updateControls();
  try {
    await api('/api/tasks/refresh-qr', {id: status.task.id});
    status.task.qr_image = null;
    status.task.phase = '正在刷新二维码';
    updateQrDialog(status);
  } catch (error) {notify(error.message, true);}
  finally {pending = false; updateControls();}
});

document.querySelectorAll('[data-region]').forEach((button) => button.addEventListener('click', async () => {
  if (pending || status?.busy || !online) return;
  pending = true; updateControls();
  try {
    const result = await api('/api/config', {region: Number(button.dataset.region)});
    renderStatus({...status, region: result.region});
    notify(`部署地域已保存为${regions[result.region][0]}。`);
  } catch (error) {notify(error.message, true);}
  finally {pending = false; updateControls();}
}));
document.querySelectorAll('[data-session]').forEach((button) => button.addEventListener('click', () => {
  if (pending || status?.busy || !online) return;
  session = button.dataset.session;
  selectedTarget = null;
  // Completed task countdown must not mask a newly selected session.
  previewSession = true;
  syncSessionButtons(); updateClock();
}));
$('follow-btn').addEventListener('click', () => {
  if (qrLocked()) return;
  follow = !follow;
  $('follow-btn').textContent = follow ? '自动跟随' : '跟随已暂停';
  $('follow-btn').setAttribute('aria-pressed', String(follow));
  if (follow) $('logs').scrollTop = $('logs').scrollHeight;
});
$('clear-btn').addEventListener('click', () => {
  if (qrLocked()) return;
  $('logs').replaceChildren();
  appendLine({time: clockFormat.format(new Date()), level: 'info', message: '已清空本页显示；后端日志保留，刷新可恢复。'});
});
document.querySelectorAll('.nav-item').forEach((a) => a.addEventListener('click', () => {
  document.querySelectorAll('.nav-item').forEach((b) => b.classList.toggle('active', b === a));
}));
updateControls();
updateClock();
setInterval(updateClock, 1000);
poll();
