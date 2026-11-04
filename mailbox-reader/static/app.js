import './style.css';
import { findLinks } from './mail-links.js';
import { copyText } from './clipboard.js';
const $ = id => document.getElementById(id);
let token = '', source = '粘贴文本', parsedText = null, previewRows = [], previewPage = 1, page = 1, matched = 0, busy = false, searchVersion = 0, noticeTimer;
let activeProject = 1, projects = [];
let accountOrder = 'asc', selectedIds = new Set(), visibleIds = [];
let rowDrag = null, dragFrame = 0, swallowDragClick = false;
const labels = {import:'批量导入', accounts:'邮箱账号', history:'导入记录'};
const accountStatusLabels = {alive:'存活', banned:'封禁'};
const ownerOptions = [['','未设置'],['天选','天选'],['3080','3080'],['3090','3090']];
const statusLabels = {valid:'可导入', duplicate:'重复', invalid:'错误'};
function notify(message) { $('notice').textContent = message; $('notice').hidden = false; clearTimeout(noticeTimer); noticeTimer = setTimeout(() => $('notice').hidden = true, 6000); }
async function api(path, data) {
  const response = await fetch(path, data === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json','X-Session-Token':token}, body:JSON.stringify(data)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '请求失败，请重试');
  return result;
}
function guard(action) { return async (...args) => { try { await action(...args); } catch (error) { notify(error.message); } }; }
function lock(value) {
  busy = value;
  for (const id of ['preview','import','clear','sample','file','text']) $(id).disabled = value;
}
function invalidate() {
  parsedText = null; previewRows = []; $('preview-panel').hidden = true; $('import-result').hidden = true;
  $('step-preview').classList.remove('active'); $('step-done').classList.remove('active');
  $('line-count').textContent = `${$('text').value.split(/\r\n|\r|\n/).filter(x => x.trim()).length} 行文本`;
}
function element(tag, text, className) { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; }
function empty(body, message, columns) { body.replaceChildren(); const row = element('tr'); const cell = element('td', message, 'empty'); cell.colSpan = columns; row.append(cell); body.append(row); }
function date(value) { return new Date(value).toLocaleString('zh-CN', {hour12:false}); }
async function view(name) {
  document.querySelectorAll('.view').forEach(node => node.hidden = node.id !== `view-${name}`);
  document.querySelectorAll('[data-view]').forEach(node => node.classList.toggle('active', node.dataset.view === name));
  $('breadcrumb-current').textContent = labels[name];
  if (name === 'accounts') await loadAccounts();
  if (name === 'history') await loadHistory();
}
function renderPreview() {
  const body = $('preview-body'); body.replaceChildren();
  for (const row of previewRows.slice((previewPage - 1) * 50, previewPage * 50)) {
    const tr = element('tr'); tr.append(element('td', row.line), element('td', row.email || '—'));
    const cell = element('td'); cell.append(element('span', statusLabels[row.status], `tag ${row.status}`)); tr.append(cell, element('td', row.reason)); body.append(tr);
  }
  $('preview-page-label').textContent = `共 ${previewRows.length} 条 · 第 ${previewPage} / ${Math.max(1, Math.ceil(previewRows.length / 50))} 页`;
  $('preview-prev').disabled = previewPage <= 1; $('preview-next').disabled = previewPage * 50 >= previewRows.length;
}
$('preview').onclick = guard(async () => {
  if (busy) return;
  const text = $('text').value;
  if (!text.trim()) return notify('请先上传 TXT 或粘贴账号文本');
  lock(true); $('preview').textContent = '正在解析…';
  try {
    const result = await api('/api/preview', {text});
    if (!result.rows.length) return notify('未发现可解析的账号行');
    parsedText = text; previewRows = result.rows; previewPage = 1;
    for (const key of ['valid','duplicate','invalid']) $(`${key}-count`).textContent = result.counts[key];
    renderPreview(); $('preview-panel').hidden = false; $('import-result').hidden = true; $('step-preview').classList.add('active');
    $('preview-panel').scrollIntoView({behavior:'smooth', block:'start'});
  } finally { lock(false); $('import').disabled = !previewRows.some(r => r.status === 'valid'); $('preview').textContent = '解析并预览 →'; }
});
$('import').onclick = guard(async () => {
  if (busy || parsedText === null || parsedText !== $('text').value) return notify('文本已更改，请重新解析');
  lock(true); $('import').textContent = '正在导入…';
  try {
    const result = await api('/api/import', {text:parsedText, source, project_id:activeProject});
    $('text').value = ''; $('file').value = ''; source = '粘贴文本'; $('file-label').textContent = '点击选择，或拖入 TXT 文件'; invalidate();
    const panel = $('import-result'); panel.replaceChildren(element('strong', '导入处理完成'), element('div', `成功 ${result.imported} 个 · 重复跳过 ${result.duplicates} 个 · 格式错误 ${result.invalid} 行`));
    const button = element('button', '查看邮箱账号 →', 'secondary'); button.onclick = guard(() => view('accounts')); panel.append(button); panel.hidden = false; $('step-done').classList.add('active');
    await loadAccounts(); panel.scrollIntoView({behavior:'smooth', block:'center'});
  } finally { lock(false); $('import').textContent = '导入有效账号 →'; }
});
$('text').oninput = () => { source = '粘贴文本'; invalidate(); };
$('clear').onclick = () => { $('text').value = ''; $('file').value = ''; $('file-label').textContent = '点击选择，或拖入 TXT 文件'; source = '粘贴文本'; invalidate(); };
$('sample').onclick = () => { $('text').value = 'demo.one@example.com----Demo!Password$123----00000000-0000-4000-8000-000000000001----DEMO_TOKEN_NOT_VALID_!*$\ndemo.two@example.com----Demo*Password456----00000000-0000-4000-8000-000000000001----ANOTHER_DEMO_TOKEN\ndemo.one@example.com----duplicate----00000000-0000-4000-8000-000000000001----DEMO_DUPLICATE\n这是一行格式错误的示例'; source = '演示文本（虚构账号）'; invalidate(); };
async function readFile(file) {
  if (!file || busy) return;
  if (!/\.txt$/i.test(file.name)) throw new Error('请选择 .txt 文件');
  if (file.size > 5 * 1024 * 1024) throw new Error('文件不能超过 5 MiB');
  lock(true);
  try {
    const bytes = await file.arrayBuffer(); let text;
    try { text = new TextDecoder('utf-8', {fatal:true}).decode(bytes); } catch { text = new TextDecoder('gb18030', {fatal:true}).decode(bytes); }
    $('text').value = text; source = file.name; $('file-label').textContent = file.name; invalidate();
  } finally { lock(false); }
}
$('file').onchange = guard(event => readFile(event.target.files[0]));
$('dropzone').ondragover = event => { event.preventDefault(); $('dropzone').classList.add('drag'); };
$('dropzone').ondragleave = () => $('dropzone').classList.remove('drag');
$('dropzone').ondrop = guard(async event => { event.preventDefault(); $('dropzone').classList.remove('drag'); await readFile(event.dataTransfer.files[0]); });
function accountQuery() {
  return new URLSearchParams({q:$('search').value, project_id:activeProject, status:activeProject ? choiceValue('status-filter') : '', owner:activeProject ? choiceValue('owner-filter') : ''});
}
function renderSelection() {
  $('selection-count').textContent = `已选 ${selectedIds.size} 个`;
  const pageSelected = visibleIds.filter(id => selectedIds.has(id)).length;
  $('select-page').checked = visibleIds.length > 0 && pageSelected === visibleIds.length;
  $('select-page').indeterminate = pageSelected > 0 && pageSelected < visibleIds.length;
  $('select-page').disabled = visibleIds.length === 0;
  $('clear-selection').disabled = selectedIds.size === 0;
  $('select-matched').disabled = matched === 0;
  $('bulk-projects').disabled = selectedIds.size === 0;
  $('apply-bulk').disabled = !activeProject || selectedIds.size === 0 || (!choiceValue('bulk-status') && !choiceValue('bulk-owner'));
  document.querySelectorAll('#account-body input[type=checkbox]').forEach(node => {
    node.checked = selectedIds.has(Number(node.value));
    node.closest('tr').classList.toggle('selected-row', node.checked);
  });
}
function clearSelection() { stopRowDrag(); selectedIds.clear(); renderSelection(); }
function choiceValue(id) { return $(id).dataset.value; }
function setChoiceValue(id, value) {
  $(id).dataset.value=value;
  $(id).querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.value===value)));
}
function bindChoices(id, action) {
  const group=$(id);
  group.querySelectorAll('button').forEach(button => button.onclick=guard(async()=>{
    if (button.dataset.value===group.dataset.value) return;
    setChoiceValue(id,button.dataset.value);
    await action();
  }));
}
function metadataChoices(account, key, options) {
  const group=element('div',undefined,'choice-group row-choices');
  group.setAttribute('role','group');
  group.setAttribute('aria-label',`${account.email} 的${key === 'status' ? '状态' : '归属'}`);
  for(const [value,label] of options) {
    const button=element('button',label,'choice-button');
    button.type='button'; button.dataset.value=value;
    button.setAttribute('aria-pressed',String(account[key]===value));
    button.onclick=guard(async()=>{
      if (account[key]===value) return;
      group.querySelectorAll('button').forEach(node=>node.disabled=true);
      try {
        await api('/api/account/update',{id:account.id,project_id:activeProject,[key]:value});
        await loadAccounts(); notify('已保存');
      } finally { group.querySelectorAll('button').forEach(node=>node.disabled=false); }
    });
    group.append(button);
  }
  return group;
}
async function loadAccounts() {
  const version = ++searchVersion;
  await loadProjects();
  const result = await api(`/api/accounts?${accountQuery()}&page=${page}&order=${accountOrder}`);
  if (version !== searchVersion) return;
  page = result.page; matched = result.matched; $('nav-count').textContent = result.total; $('account-total').textContent = result.total;
  stopRowDrag();
  visibleIds = result.items.map(account => account.id);
  $('sequence-heading').setAttribute('aria-sort', accountOrder === 'asc' ? 'ascending' : 'descending');
  $('sort-arrow').textContent = accountOrder === 'asc' ? '↑' : '↓';
  $('sort-sequence').setAttribute('aria-label', accountOrder === 'asc' ? '序号升序，点击切换降序' : '序号降序，点击切换升序');
  const body = $('account-body'); body.replaceChildren();
  if (!result.items.length) empty(body, result.total ? '没有匹配的邮箱账号' : '还没有账号，从导入一份 TXT 开始。', 9);
  for (const account of result.items) {
    const row = element('tr'); row.dataset.accountId = account.id;
    const checkCell = element('td', undefined, 'selection-cell');
    const checkbox = element('input'); checkbox.type = 'checkbox'; checkbox.value = account.id;
    checkbox.setAttribute('aria-label', `选择 ${account.email}`);
    checkbox.onchange = () => { if (checkbox.checked) selectedIds.add(account.id); else selectedIds.delete(account.id); renderSelection(); };
    const emailCell = element('td');
    const copyEmail = element('button', account.email, 'email-copy');
    copyEmail.type = 'button'; copyEmail.title = '点击复制邮箱地址';
    copyEmail.setAttribute('aria-label', `复制邮箱 ${account.email}`);
    copyEmail.onclick = guard(async () => {
      await copyText(account.email);
      notify('邮箱地址已复制');
    });
    emailCell.append(copyEmail);
    checkCell.append(checkbox); row.append(checkCell, element('td', account.id), emailCell);
    const projectCell = element('td');
    const projectButton = element('button', account.projects.map(p=>p.name).join('、') || '设置项目', 'text-button');
    projectButton.onclick = guard(()=>openProjectMembership([account.id],account.email));
    projectCell.append(projectButton); row.append(projectCell);
    const statusCell = element('td');
    const statusControl = element('div', undefined, `account-status ${account.status}`);
    const dot = element('span', undefined, 'account-status-dot'); dot.setAttribute('aria-hidden','true');
    statusControl.append(dot, metadataChoices(account, 'status', Object.entries(accountStatusLabels))); statusCell.append(statusControl);
    const ownerCell = element('td'); ownerCell.append(metadataChoices(account, 'owner', ownerOptions));
    if (!activeProject) { statusCell.replaceChildren(element('span','进入项目后设置','muted')); ownerCell.replaceChildren(element('span','—','muted')); }
    row.append(statusCell, ownerCell, element('td', '••••••••', 'secret-mask'), element('td', date(account.created_at)));
    const cell = element('td'); const button = element('button', '查看详情 ↗', 'text-button');
    button.onclick = guard(async () => {
      button.disabled = true;
      try {
        const details = await api('/api/reveal', {id:account.id}); $('detail-content').replaceChildren();
        for (const [key,label] of [['email','邮箱地址'],['password','账号密码'],['client_id','Client ID'],['token','Token']]) {
          const field = element('div', undefined, 'detail-field'); field.append(element('label', label), element('code', details[key], 'detail-value')); $('detail-content').append(field);
        }
        $('detail').showModal();
      } finally { button.disabled = false; }
    });
    const readMail = element('button', '查看邮件', 'secondary');
    readMail.onclick = () => openMail(account);
    cell.append(readMail, button); cell.classList.add('row-actions'); row.append(cell); body.append(row);
  }
  $('page-label').textContent = `共 ${matched} 个账号 · 第 ${page} / ${Math.max(1, Math.ceil(matched / 50))} 页`;
  $('prev').disabled = page <= 1; $('next').disabled = page * 50 >= matched;
  renderSelection();
}
async function loadHistory() {
  const records = await api('/api/history'); const body = $('history-body'); body.replaceChildren();
  if (!records.length) return empty(body, '暂无导入记录', 5);
  for (const item of records) { const row = element('tr'); row.append(...[item.source,item.imported,item.duplicates,item.invalid,date(item.created_at)].map(x => element('td', x))); body.append(row); }
}
$('prev').onclick = guard(async () => { if (page > 1) page--; await loadAccounts(); });
$('next').onclick = guard(async () => { if (page * 50 < matched) page++; await loadAccounts(); });
$('preview-prev').onclick = () => { previewPage--; renderPreview(); };
$('preview-next').onclick = () => { previewPage++; renderPreview(); };
let searchTimer;
$('search').oninput = () => { clearTimeout(searchTimer); ++searchVersion; clearSelection(); page = 1; searchTimer = setTimeout(guard(loadAccounts), 180); };
$('close-detail').onclick = () => $('detail').close();
$('detail').onclose = () => $('detail-content').replaceChildren();
document.querySelectorAll('[data-view]').forEach(node => node.onclick = guard(() => view(node.dataset.view)));
$('new-import').onclick = guard(() => view('import'));
async function authenticate() {
  const session = await api('/api/session'); token = session.token;
  if (!session.auth_enabled || session.authenticated) { await view('accounts'); return; }
  const screen=$('auth-screen'); screen.hidden=false; document.querySelector('main').hidden=true; document.querySelector('.sidebar').hidden=true;
  const setup=session.setup_required;
  $('auth-title').textContent=setup ? '初始化管理员账号' : '登录邮箱工作区';
  $('auth-description').textContent=setup ? '首次使用请创建管理员账号，密码只保存在本机数据库中。' : '请输入管理员账号和密码。';
  $('auth-eyebrow').textContent=setup ? 'FIRST RUN SETUP' : 'SECURE ACCESS';
  $('auth-submit').textContent=setup ? '创建并进入' : '登录'; $('auth-confirm-wrap').hidden=!setup;
  $('auth-form').onsubmit=async event=>{ event.preventDefault(); $('auth-error').hidden=true; const password=$('auth-password').value; if(setup && password!==$('auth-confirm').value){ $('auth-error').textContent='两次密码不一致'; $('auth-error').hidden=false; return; } $('auth-submit').disabled=true; try { const result=await api(setup?'/api/auth/setup':'/api/auth/login',{username:$('auth-username').value,password}); if(result.authenticated){ screen.hidden=true; document.querySelector('main').hidden=false; document.querySelector('.sidebar').hidden=false; await view('accounts'); } } catch(error) { $('auth-error').textContent=error.message; $('auth-error').hidden=false; } finally { $('auth-submit').disabled=false; } };
  $('auth-username').focus();
}
authenticate().catch(error=>notify(error.message));

for (const id of ['status-filter','owner-filter']) bindChoices(id, async () => {
  clearTimeout(searchTimer); clearSelection(); page = 1; await loadAccounts();
});
$('reset-filters').onclick = guard(async () => {
  clearTimeout(searchTimer); clearSelection(); $('search').value = ''; setChoiceValue('status-filter', 'alive'); setChoiceValue('owner-filter', ''); page = 1; await loadAccounts();
});

$('sort-sequence').onclick = guard(async () => {
  clearTimeout(searchTimer); accountOrder = accountOrder === 'asc' ? 'desc' : 'asc'; page = 1; await loadAccounts();
});
$('select-page').onchange = () => {
  for (const id of visibleIds) { if ($('select-page').checked) selectedIds.add(id); else selectedIds.delete(id); }
  renderSelection();
};
$('clear-selection').onclick = clearSelection;
bindChoices('bulk-status', renderSelection);
bindChoices('bulk-owner', renderSelection);
$('select-matched').onclick = guard(async () => {
  const query = accountQuery().toString(), version = searchVersion;
  $('select-matched').disabled = true;
  try {
    const result = await api(`/api/accounts/ids?${query}`);
    if (query !== accountQuery().toString() || version !== searchVersion) return;
    if (result.ids.length > 100000) return notify('单次最多操作 100000 个账号，请缩小筛选范围');
    selectedIds = new Set(result.ids); renderSelection();
  } finally { $('select-matched').disabled = matched === 0; }
});
$('apply-bulk').onclick = guard(async () => {
  if (!selectedIds.size) return;
  const values = {};
  if (choiceValue('bulk-status')) values.status = choiceValue('bulk-status');
  if (choiceValue('bulk-owner')) values.owner = choiceValue('bulk-owner') === 'unassigned' ? '' : choiceValue('bulk-owner');
  if (!Object.keys(values).length) return;
  clearTimeout(searchTimer);
  const controls = [...document.querySelectorAll('#view-accounts button, #view-accounts input, #view-accounts select')].map(node => [node, node.disabled]);
  controls.forEach(([node]) => node.disabled = true);
  let result;
  try {
    result = await api('/api/accounts/bulk-update', {ids:[...selectedIds], values, project_id:activeProject});
    selectedIds.clear(); setChoiceValue('bulk-status', 'alive'); setChoiceValue('bulk-owner', '');
  } finally {
    controls.forEach(([node, disabled]) => node.disabled = disabled);
    renderSelection();
  }
  await loadAccounts();
  notify(`已批量更新 ${result.updated} 个账号`);
});

function updateDragRange() {
  if (!rowDrag) return;
  const rows = [...$('account-body').querySelectorAll('tr[data-account-id]')];
  let end = rows.findIndex(row => rowDrag.y < row.getBoundingClientRect().bottom);
  if (end < 0) end = rows.length - 1;
  if (end === rowDrag.end) return;
  rowDrag.end = end;
  selectedIds = new Set(rowDrag.baseline);
  const from = Math.min(rowDrag.start, end), to = Math.max(rowDrag.start, end);
  for (let index = from; index <= to; index++) {
    const id = Number(rows[index].dataset.accountId);
    if (rowDrag.selecting) selectedIds.add(id); else selectedIds.delete(id);
  }
  renderSelection();
}
function dragScrollFrame(time) {
  if (!rowDrag) return;
  const elapsed = Math.min(32, time - rowDrag.lastFrame || 16);
  rowDrag.lastFrame = time;
  const margin = 72;
  const speed = rowDrag.y < margin ? -Math.min(1, (margin - rowDrag.y) / margin)
    : rowDrag.y > innerHeight - margin ? Math.min(1, (rowDrag.y - innerHeight + margin) / margin) : 0;
  if (speed) window.scrollBy(0, speed * elapsed * 0.8);
  updateDragRange();
  dragFrame = requestAnimationFrame(dragScrollFrame);
}
function stopRowDrag() {
  if (!rowDrag) return;
  const pointerId = rowDrag.pointerId;
  rowDrag = null;
  cancelAnimationFrame(dragFrame);
  document.body.classList.remove('selecting-accounts');
  if ($('account-body').hasPointerCapture(pointerId)) $('account-body').releasePointerCapture(pointerId);
}
$('account-body').addEventListener('pointerdown', event => {
  if (event.pointerType !== 'mouse' || event.button !== 0) return;
  const row = event.target.closest('tr[data-account-id]');
  if (!row || event.target.closest('select,button,a,textarea') || event.target.closest('input:disabled')) return;
  if (event.target.closest('input') && event.target.type !== 'checkbox') return;
  if ($('select-page').disabled) return;
  event.preventDefault();
  swallowDragClick = false;
  rowDrag = {pointerId:event.pointerId, start:visibleIds.indexOf(Number(row.dataset.accountId)),
    end:-1, y:event.clientY, baseline:new Set(selectedIds), selecting:!selectedIds.has(Number(row.dataset.accountId)), lastFrame:0};
  $('account-body').setPointerCapture(event.pointerId);
  document.body.classList.add('selecting-accounts');
  updateDragRange();
  dragFrame = requestAnimationFrame(dragScrollFrame);
});
$('account-body').addEventListener('pointermove', event => {
  if (!rowDrag || event.pointerId !== rowDrag.pointerId) return;
  if (!(event.buttons & 1)) { stopRowDrag(); return; }
  rowDrag.y = event.clientY;
  updateDragRange();
});
$('account-body').addEventListener('pointerup', event => {
  if (!rowDrag || event.pointerId !== rowDrag.pointerId) return;
  swallowDragClick = true;
  stopRowDrag();
});
$('account-body').addEventListener('click', event => {
  if (swallowDragClick && event.detail > 0 && !event.target.closest('button,select,a')) {
    swallowDragClick = false; event.preventDefault(); event.stopPropagation();
  }
}, true);
$('account-body').addEventListener('pointercancel', stopRowDrag);
$('account-body').addEventListener('lostpointercapture', stopRowDrag);
window.addEventListener('blur', stopRowDrag);

let mailAccount = null, mailListVersion = 0, mailBodyVersion = 0;
async function openMail(account) {
  mailAccount = account;
  $('mail-account').textContent = account.email;
  $('mail-heading').textContent = '收件箱';
  $('mail-list').replaceChildren();
  $('mail-content').replaceChildren(element('div', '从左侧选择一封邮件查看正文', 'mail-empty'));
  if (!$('mail-dialog').open) $('mail-dialog').showModal();
  await fetchMailList();
}
async function fetchMailList() {
  if (!mailAccount || !$('mail-dialog').open) return;
  const account = mailAccount, version = ++mailListVersion;
  ++mailBodyVersion;
  $('refresh-mail').disabled = true;
  $('mail-status').textContent = '正在获取收件箱，请稍候…';
  $('mail-status').classList.remove('mail-error');
  $('mail-list').replaceChildren();
  $('mail-content').replaceChildren(element('div', '从左侧选择一封邮件查看正文', 'mail-empty'));
  try {
    const result = await api('/api/mail/list', {id:account.id});
    if (version !== mailListVersion || !$('mail-dialog').open) return;
    $('mail-status').textContent = `已获取 ${result.messages.length} 封邮件${result.has_more ? '，当前显示最近 25 封' : ''} · ${new Date().toLocaleTimeString('zh-CN',{hour12:false})}`;
    if (!result.messages.length) $('mail-list').append(element('div','收件箱暂无邮件','mail-empty'));
    for (const message of result.messages) {
      const button = element('button', undefined, `mail-item${message.is_read ? '' : ' unread'}`);
      button.append(element('strong',message.sender),element('span',message.subject,'mail-subject'),element('span',message.preview,'mail-preview'),element('time',message.received_at ? date(message.received_at) : '', 'mail-date'));
      button.onclick = () => fetchMailBody(account,message,button);
      $('mail-list').append(button);
    }
    if (result.messages.length) {
      await fetchMailBody(account, result.messages[0], $('mail-list').firstElementChild);
    }
  } catch (error) {
    if (version !== mailListVersion || !$('mail-dialog').open) return;
    $('mail-status').textContent = error.message; $('mail-status').classList.add('mail-error');
    $('mail-list').append(element('div','读取失败，可稍后点击刷新重试','mail-empty'));
  } finally { if (version === mailListVersion) $('refresh-mail').disabled = false; }
}
async function fetchMailBody(account,message,button) {
  const version = ++mailBodyVersion;
  document.querySelectorAll('.mail-item').forEach(node=>node.classList.toggle('active',node===button));
  $('mail-content').replaceChildren(element('div','正在读取邮件正文…','mail-empty'));
  try {
    const result = await api('/api/mail/message',{id:account.id,message_id:message.id});
    if (version !== mailBodyVersion || !$('mail-dialog').open) return;
    const heading = element('div',undefined,'mail-message-heading');
    heading.append(element('h3',result.subject),element('p',`发件人：${result.sender}${result.sender_address ? ' <'+result.sender_address+'>' : ''}`),element('p',`收件人：${result.recipients || account.email}`),element('p',result.received_at ? date(result.received_at) : ''));
    const content = renderMailBody(result.body || '（此邮件没有正文）');
    const actions = verificationActions(result.body || '');
    $('mail-content').replaceChildren(heading, ...actions, content);
  } catch(error) {
    if(version===mailBodyVersion && $('mail-dialog').open) $('mail-content').replaceChildren(element('div',error.message,'mail-empty mail-error'));
  }
}
$('refresh-mail').onclick = fetchMailList;
$('close-mail').onclick = () => $('mail-dialog').close();
$('mail-dialog').onclose = () => {
  ++mailListVersion; ++mailBodyVersion; mailAccount=null;
  $('mail-account').textContent=''; $('mail-status').textContent='';
  $('mail-list').replaceChildren(); $('mail-content').replaceChildren();
};

function externalMailLink(url, label, className) {
  const link=element('a',label,className);
  link.href=url; link.target='_blank'; link.rel='noopener noreferrer'; link.referrerPolicy='no-referrer';
  return link;
}
function renderMailBody(text) {
  const body=element('div',undefined,'mail-message-body');
  let offset=0;
  for(const link of findLinks(text)) {
    body.append(document.createTextNode(text.slice(offset,link.start)),externalMailLink(link.url,link.url,'mail-body-link'));
    offset=link.end;
  }
  body.append(document.createTextNode(text.slice(offset)));
  return body;
}
function verificationActions(text) {
  const links=[...new Set(findLinks(text).filter(link=>link.verification).map(link=>link.url))];
  if(!links.length) return [];
  const panel=element('section',undefined,'verification-actions');
  panel.append(element('h4','邮件中的验证链接'),element('p','请核对目标网站后打开；链接有效性由目标网站决定。','verification-note'));
  for(const [index,url] of links.entries()) {
    const row=element('div',undefined,'verification-row');
    const info=element('div',undefined,'verification-info');
    info.append(element('strong',`${links.length>1 ? (index+1)+'. ' : ''}${new URL(url).hostname}`),element('code',url));
    const buttons=element('div',undefined,'verification-buttons');
    const open=externalMailLink(url,'打开验证链接 ↗','primary');
    const copy=element('button','复制验证链接','secondary');
    copy.type='button';
    copy.onclick=async()=>{
      try {
        await copyText(url);
        copy.textContent='已复制 ✓'; notify('验证链接已复制');
        setTimeout(()=>copy.textContent='复制验证链接',1800);
      } catch {
        notify('复制未成功，请选中上方完整链接后按 Ctrl+C 复制');
      }
    };
    buttons.append(open,copy); row.append(info,buttons); panel.append(row);
  }
  return [panel];
}

async function loadProjects() {
  projects = await api('/api/projects');
  const group=$('project-filter'); group.replaceChildren();
  for (const project of [{id:0,name:'全部邮箱'},...projects]) {
    const button=element('button',project.name,'choice-button'); button.type='button';
    button.setAttribute('aria-pressed',String(project.id===activeProject));
    button.onclick=guard(async()=>{
      if (activeProject===project.id) return;
      activeProject=project.id; page=1; clearSelection(); await loadAccounts();
    });
    group.append(button);
  }
  $('project-context').textContent=activeProject ? '状态和归属仅作用于当前项目' : '全部账号 · 点击项目名称设置多项目归属';
  for (const id of ['status-filter','owner-filter','bulk-status','bulk-owner']) {
    $(id).querySelectorAll('button').forEach(button=>button.disabled=!activeProject);
  }
}
$('new-project').onclick=()=>{ $('project-create-dialog').showModal(); $('project-name').focus(); };
$('cancel-project-create').onclick=()=>$('project-create-dialog').close();
$('project-create-form').onsubmit=guard(async event=>{
  event.preventDefault();
  const submit=event.submitter; submit.disabled=true;
  try {
    const project=await api('/api/projects/create',{name:$('project-name').value});
    activeProject=project.id; page=1; clearSelection(); $('project-name').value='';
    $('project-create-dialog').close(); await loadAccounts();
    notify('项目已创建，可在“全部邮箱”中选择账号添加到项目');
  } finally { submit.disabled=false; }
});
async function openProjectMembership(ids,label) {
  await loadProjects();
  $('project-membership-title').textContent=label ? `${label} · 设置项目` : `为 ${ids.length} 个账号设置项目`;
  const list=$('project-membership-options'); list.replaceChildren();
  for(const project of projects) {
    const row=element('div',undefined,'project-membership-row'); row.append(element('strong',project.name));
    for(const [remove,label] of [[false,'添加到项目'],[true,'移出项目']]) {
      const button=element('button',label,'secondary'); button.type='button';
      button.onclick=guard(async()=>{
        list.querySelectorAll('button').forEach(b=>b.disabled=true);
        try {
          await api('/api/projects/assign',{ids,project_id:project.id,remove});
          clearSelection(); await loadAccounts(); notify(`${ids.length} 个账号已${remove?'移出':'添加到'} ${project.name}`);
        } finally { list.querySelectorAll('button').forEach(b=>b.disabled=false); }
      });
      row.append(button);
    }
    list.append(row);
  }
  $('project-membership-dialog').showModal();
}
$('bulk-projects').onclick=guard(()=>openProjectMembership([...selectedIds]));
$('close-project-membership').onclick=()=>$('project-membership-dialog').close();
