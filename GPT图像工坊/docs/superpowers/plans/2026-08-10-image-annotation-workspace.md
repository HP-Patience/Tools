
# Image Annotation Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Fabric.js image workspace where uploaded, generated, and edited images can be previewed, annotated, saved, and sent through the existing `/api/edit` flow.

**Architecture:** Keep FastAPI and the existing single-page frontend. Add one focused frontend module, `static/annotation-workspace.js`, powered by local `static/vendor/fabric.min.js`; the current inline script in `static/index.html` remains responsible for configuration, generate/edit calls, and result rendering. The backend keeps upstream calls conservative and only adds saving/returning of the annotated PNG submitted by the workspace.

**Tech Stack:** FastAPI, Pydantic, vanilla HTML/CSS/JS, Fabric.js 5.3.0 loaded locally, PowerShell manual checks, Python `py_compile`, Node `--check`.

## Global Constraints

- Do not migrate to Next.js.
- Do not introduce a database, login system, cloud history, or project/session storage.
- Do not send upstream image parameters `size`, `quality`, `output_format`, `background`, `n`, `mask`, or structured annotation fields.
- For CPA reverse proxy compatibility, `/v1/images/edits` receives only `model`, `prompt`, and `image`.
- Multiple images continue to be implemented by backend loops; the frontend may send `n` to the local backend, but `image_gen.py` must not pass `n` upstream for `gpt-image-2`.
- Fabric.js must be saved under `static/vendor/` and referenced locally, not via CDN at runtime.
- The workspace sends a baked PNG containing visible annotations and appends annotation notes to the prompt.
- Save both the annotated image submitted to `/api/edit` and the AI edited result images under `output/`.

---

## File Structure

- Modify `app.py`: add `annotated_image` to `GenResponse`, add `_save_raw_image(raw, prefix)`, add `/api/edit` form field `save_annotated`, save and return annotated upload when requested.
- Keep `image_gen.py`: no upstream parameter expansion.
- Create `static/vendor/fabric.min.js`: local Fabric.js browser bundle.
- Create `static/annotation-workspace.js`: Fabric canvas lifecycle, drawing tools, annotations, prompt composition, PNG export, and workspace send callback.
- Modify `static/index.html`: upload preview, workspace modal, CSS, local scripts, clickable generated/edited results, `submitAnnotatedEdit()`.
- Modify `README.md`: document annotation workspace and saved files.

---

### Task 1: Backend saves annotated workspace uploads

**Files:**
- Modify: `app.py`

**Interfaces:**
- Consumes: existing `_image_format(raw: bytes) -> tuple[str, str]`, `OUTPUT_DIR`, `ImageItem`, `GenResponse`, and `/api/edit`.
- Produces: `_save_raw_image(raw: bytes, prefix: str) -> ImageItem`; `GenResponse.annotated_image: Optional[ImageItem]`; `/api/edit` form field `save_annotated: bool = Form(False)`.

- [ ] **Step 1: Update imports and response model**

In `app.py`, change `from typing import List` to:

```python
from typing import List, Optional
```

Change `GenResponse` to:

```python
class GenResponse(BaseModel):
    b64: str
    data_url: str
    images: List[ImageItem]
    model: str
    annotated_image: Optional[ImageItem] = None
```

- [ ] **Step 2: Add raw image saving helper**

Place directly after `_save_b64_images`:

```python
def _save_raw_image(raw: bytes, prefix: str) -> ImageItem:
    extension, mime_type = _image_format(raw)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{prefix}_{timestamp}.{extension}"
    output_path = OUTPUT_DIR / filename
    output_path.write_bytes(raw)
    b64 = base64.b64encode(raw).decode("ascii")
    return ImageItem(
        b64=b64,
        data_url=f"data:{mime_type};base64,{b64}",
        file_path=f"output/{filename}",
        file_url=f"/output/{filename}",
    )
```

- [ ] **Step 3: Extend `/api/edit` signature and save upload**

Change the signature to:

```python
async def edit_image(
    prompt: str = Form(...),
    model: str = Form("gpt-image-2"),
    n: int = Form(1),
    save_annotated: bool = Form(False),
    image: UploadFile = File(...),
):
```

After the 20 MB size check, add:

```python
    annotated_image = None
    if save_annotated:
        try:
            annotated_image = _save_raw_image(image_bytes, "annotated")
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            raise HTTPException(500, f"保存标注图失败: {e}")
```

- [ ] **Step 4: Include annotated image in response**

Change the `/api/edit` return block to:

```python
    return GenResponse(
        b64=first.b64,
        data_url=first.data_url,
        images=images,
        model=model,
        annotated_image=annotated_image,
    )
```

- [ ] **Step 5: Verify and commit**

Run:

```powershell
python -m py_compile app.py image_gen.py
git add app.py
git commit -m "Save annotated edit uploads"
```

Expected: syntax check exits with code 0; commit succeeds.

---

### Task 2: Add local Fabric.js and workspace shell

**Files:**
- Create: `static/vendor/fabric.min.js`
- Create: `static/annotation-workspace.js`
- Modify: `static/index.html`

**Interfaces:**
- Consumes: `/static/vendor/fabric.min.js` browser global `fabric`.
- Produces: `window.AnnotationWorkspace.open({ imageUrl, sourceName, prompt, onSend })`; `onSend` receives `{ blob, filename, prompt, notes }`.

- [ ] **Step 1: Create vendor bundle**

Run:

```powershell
New-Item -ItemType Directory -Force -Path static\vendor | Out-Null
Invoke-WebRequest -Uri "https://cdn.jsdelivr.net/npm/fabric@5.3.0/dist/fabric.min.js" -OutFile "static\vendor\fabric.min.js"
if ((Get-Item static\vendor\fabric.min.js).Length -lt 100000) { throw "fabric.min.js is too small" }
```

Expected: `static/vendor/fabric.min.js` exists and is larger than 100 KB.

- [ ] **Step 2: Create initial `static/annotation-workspace.js`**

Create this module skeleton:

```js
(function () {
  'use strict';
  const state = { canvas: null, options: null, tool: 'select', color: '#ef4444', width: 4, history: [], suppressHistory: false, counter: 1 };
  function byId(id) { return document.getElementById(id); }
  function requireFabric() { if (!window.fabric) throw new Error('Fabric.js 未加载，请检查 /static/vendor/fabric.min.js'); }
  function pushHistory() {
    if (!state.canvas || state.suppressHistory) return;
    state.history.push(JSON.stringify(state.canvas.toDatalessJSON(['annotationId', 'annotationType', 'note', 'color'])));
    if (state.history.length > 40) state.history.shift();
  }
  function initCanvas(imageUrl) {
    if (state.canvas) state.canvas.dispose();
    const canvas = new fabric.Canvas('annotationCanvas', { preserveObjectStacking: true, selection: true });
    state.canvas = canvas;
    fabric.Image.fromURL(imageUrl, (img) => {
      const maxW = 900, maxH = 620;
      const scale = Math.min(maxW / img.width, maxH / img.height, 1);
      const width = Math.max(320, Math.round(img.width * scale));
      const height = Math.max(260, Math.round(img.height * scale));
      canvas.setWidth(width); canvas.setHeight(height);
      img.set({ left: 0, top: 0, scaleX: width / img.width, scaleY: height / img.height, selectable: false, evented: false });
      canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas));
      pushHistory();
    }, { crossOrigin: 'anonymous' });
  }
  function open(options) {
    requireFabric(); state.options = options; state.tool = 'select'; state.counter = 1;
    byId('workspaceTitle').textContent = options.sourceName || 'Image Workspace';
    byId('workspacePrompt').value = options.prompt || '';
    byId('annotationModal').classList.add('open');
    byId('annotationModal').setAttribute('aria-hidden', 'false');
    initCanvas(options.imageUrl);
  }
  function close() {
    if (state.canvas) { state.canvas.dispose(); state.canvas = null; }
    state.history = []; state.options = null; byId('annotationList').innerHTML = '';
    byId('annotationModal').classList.remove('open');
    byId('annotationModal').setAttribute('aria-hidden', 'true');
  }
  function setTool(tool) {
    state.tool = tool;
    if (!state.canvas) return;
    state.canvas.isDrawingMode = tool === 'brush';
    state.canvas.selection = tool === 'select';
    if (state.canvas.freeDrawingBrush) { state.canvas.freeDrawingBrush.color = state.color; state.canvas.freeDrawingBrush.width = state.width; }
    document.querySelectorAll('[data-annotation-tool]').forEach(btn => btn.classList.toggle('active', btn.dataset.annotationTool === tool));
  }
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-annotation-tool]').forEach(btn => btn.addEventListener('click', () => setTool(btn.dataset.annotationTool)));
    const color = byId('annotationColor'), width = byId('annotationWidth');
    if (color) color.addEventListener('input', () => { state.color = color.value; setTool(state.tool); });
    if (width) width.addEventListener('input', () => { state.width = Number(width.value); setTool(state.tool); });
  });
  window.AnnotationWorkspace = { open, close, setTool };
})();
```

- [ ] **Step 3: Add scripts, upload preview, modal, and CSS to `static/index.html`**

Add before the existing inline script:

```html
<script src="/static/vendor/fabric.min.js"></script>
<script src="/static/annotation-workspace.js"></script>
```

Add after `.upload-row`:

```html
<div id="uploadPreview" class="upload-preview" style="display:none">
  <button id="uploadPreviewButton" class="upload-preview-card" type="button">
    <img id="uploadPreviewImage" alt="Uploaded image preview">
    <span data-i18n="openWorkspace">Open workspace</span>
  </button>
</div>
```

Add before the footer:

```html
<div id="annotationModal" class="annotation-modal" aria-hidden="true">
  <div class="annotation-panel" role="dialog" aria-modal="true" aria-labelledby="workspaceTitle">
    <div class="annotation-topbar"><div><div class="annotation-kicker">Image Workspace</div><h2 id="workspaceTitle">Image Workspace</h2></div><button class="secondary" type="button" onclick="AnnotationWorkspace.close()">Close</button></div>
    <div class="annotation-body"><div class="annotation-tools"><button type="button" data-annotation-tool="select">↖</button><button type="button" data-annotation-tool="rect">□</button><button type="button" data-annotation-tool="circle">○</button><button type="button" data-annotation-tool="arrow">↗</button><button type="button" data-annotation-tool="brush">✎</button><button type="button" data-annotation-tool="text">T</button><label class="annotation-color"><span>Color</span><input id="annotationColor" type="color" value="#ef4444"></label><label class="annotation-width"><span>Width</span><input id="annotationWidth" type="range" min="1" max="16" value="4"></label></div><div class="annotation-stage"><canvas id="annotationCanvas"></canvas></div><aside class="annotation-side"><label for="workspacePrompt">Prompt</label><textarea id="workspacePrompt"></textarea><h3>Annotations</h3><div id="annotationList" class="annotation-list"></div><div class="annotation-actions"><button type="button" id="annotationUndoBtn">Undo</button><button type="button" id="annotationDeleteBtn">Delete</button><button type="button" id="annotationClearBtn">Clear</button><button type="button" id="annotationSendBtn">Send Edit</button></div></aside></div>
  </div>
</div>
```

Add this modal CSS before `</style>`:

```css
.upload-preview { margin-top: 18px; }
.upload-preview-card { display: inline-flex; align-items: center; gap: 14px; background: transparent; color: var(--ink); border: 1px solid var(--rule); padding: 10px; letter-spacing: 0.08em; }
.upload-preview-card img { width: 96px; height: 96px; object-fit: cover; border: 1px solid var(--rule); background: var(--bg-deep); }
.plate-grid img { cursor: zoom-in; }
.annotation-modal { position: fixed; inset: 0; display: none; z-index: 50; background: rgba(20, 20, 19, 0.72); padding: 24px; }
.annotation-modal.open { display: block; }
.annotation-panel { width: min(1400px, 100%); height: min(880px, calc(100vh - 48px)); margin: 0 auto; background: var(--bg); border: 1px solid var(--ink); display: flex; flex-direction: column; }
.annotation-topbar { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 18px 22px; border-bottom: 1px solid var(--rule); }
.annotation-kicker { font-family: "JetBrains Mono", monospace; font-size: 10px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted); }
.annotation-topbar h2 { margin: 4px 0 0; font-size: 28px; }
.annotation-body { flex: 1; min-height: 0; display: grid; grid-template-columns: 76px minmax(420px, 1fr) 300px; }
.annotation-tools { border-right: 1px solid var(--rule); padding: 12px 10px; display: flex; flex-direction: column; gap: 9px; }
.annotation-tools button, .annotation-actions button { padding: 10px; justify-content: center; letter-spacing: 0.08em; }
.annotation-tools button.active { background: var(--accent); border-color: var(--accent); color: var(--bg); }
.annotation-color, .annotation-width { display: grid; gap: 6px; font-family: "JetBrains Mono", monospace; font-size: 9px; color: var(--muted); text-transform: uppercase; }
.annotation-stage { min-width: 0; min-height: 0; padding: 18px; overflow: auto; display: flex; align-items: center; justify-content: center; background: var(--bg-deep); }
.annotation-stage canvas { background: white; box-shadow: 0 18px 60px rgba(20, 20, 19, 0.22); }
.annotation-side { border-left: 1px solid var(--rule); padding: 16px; overflow: auto; }
.annotation-side label, .annotation-side h3 { font-family: "JetBrains Mono", monospace; font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--muted); }
#workspacePrompt { width: 100%; min-height: 110px; margin: 10px 0 18px; padding: 10px; border: 1px solid var(--rule); background: var(--bg); color: var(--ink); font: 15px/1.45 "Newsreader", serif; }
.annotation-item { border: 1px solid var(--rule); padding: 10px; margin-bottom: 10px; background: var(--bg); }
.annotation-item.selected { border-color: var(--accent); }
.annotation-item textarea { width: 100%; min-height: 58px; border: 1px solid var(--rule); padding: 8px; margin-top: 8px; background: var(--bg-deep); color: var(--ink); }
.annotation-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
#annotationSendBtn { grid-column: 1 / -1; background: var(--ink); color: var(--bg); }
```

- [ ] **Step 4: Verify and commit**

Run:

```powershell
Select-String -Path static\index.html -Pattern 'fabric.min.js','annotation-workspace.js','annotationModal','uploadPreview'
node --check static\annotation-workspace.js
git add static\vendor\fabric.min.js static\annotation-workspace.js static\index.html
git commit -m "Add annotation workspace shell"
```

Expected: patterns are found; Node syntax check passes; commit succeeds.

---
### Task 3: Implement drawing tools and annotation list

**Files:**
- Modify: `static/annotation-workspace.js`

**Interfaces:**
- Consumes: `fabric.Canvas` from Task 2.
- Produces: annotation objects with `annotationId`, `annotationType`, `note`, `color`; tools `rect`, `circle`, `arrow`, `brush`, `text`, `select`; internal helpers `annotationObjects()`, `renderAnnotationList()`, `typeLabel()`.

- [ ] **Step 1: Add object metadata and list helpers**

Add inside the module:

```js
function createAnnotationProps(type) {
  const id = `a${state.counter++}`;
  return { annotationId: id, annotationType: type, note: '', color: state.color, cornerColor: state.color, borderColor: state.color, transparentCorners: false };
}
function annotationObjects() { return state.canvas ? state.canvas.getObjects().filter(obj => obj.annotationId) : []; }
function typeLabel(type) { return ({ rect: '矩形', circle: '圆形', arrow: '箭头', brush: '画笔', text: '文字' })[type] || type; }
function escapeHtml(value) { return String(value).replace(/[&<>"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[char]); }
function renderAnnotationList() {
  const list = byId('annotationList');
  if (!list || !state.canvas) return;
  const active = state.canvas.getActiveObject();
  const objects = annotationObjects();
  list.innerHTML = objects.length ? objects.map((obj, index) => `
    <div class="annotation-item ${active === obj ? 'selected' : ''}" data-annotation-id="${obj.annotationId}">
      <button type="button" class="secondary" data-select-annotation="${obj.annotationId}">${index + 1}. ${typeLabel(obj.annotationType)}</button>
      <textarea data-note-for="${obj.annotationId}" placeholder="写给 AI 的说明">${escapeHtml(obj.note || '')}</textarea>
    </div>`).join('') : '<p class="upload-help">还没有标注。</p>';
}
```

- [ ] **Step 2: Add shape creation helpers**

Add:

```js
function finalizeObject(obj) {
  if (!state.canvas || !obj) return;
  state.canvas.add(obj);
  state.canvas.setActiveObject(obj);
  state.canvas.requestRenderAll();
  pushHistory();
  renderAnnotationList();
}
function addTextAt(pointer) {
  const text = new fabric.Textbox('注释', { ...createAnnotationProps('text'), left: pointer.x, top: pointer.y, width: 180, fontSize: 24, fill: state.color, fontFamily: 'sans-serif', editable: true });
  finalizeObject(text);
  setTool('select');
}
function makeArrow(start, end) {
  const props = createAnnotationProps('arrow');
  const angle = Math.atan2(end.y - start.y, end.x - start.x);
  const headLength = Math.max(14, state.width * 4);
  const line = new fabric.Line([start.x, start.y, end.x, end.y], { stroke: state.color, strokeWidth: state.width, strokeLineCap: 'round', originX: 'center', originY: 'center' });
  const head = new fabric.Triangle({ left: end.x, top: end.y, width: headLength, height: headLength, fill: state.color, angle: angle * 180 / Math.PI + 90, originX: 'center', originY: 'center' });
  return new fabric.Group([line, head], props);
}
```

- [ ] **Step 3: Attach canvas mouse events**

Add `attachCanvasEvents()`:

```js
function attachCanvasEvents() {
  const canvas = state.canvas;
  let start = null;
  let preview = null;
  canvas.on('mouse:down', (event) => {
    if (state.tool === 'select' || state.tool === 'brush') return;
    const pointer = canvas.getPointer(event.e);
    if (state.tool === 'text') { addTextAt(pointer); return; }
    start = pointer;
    if (state.tool === 'rect') preview = new fabric.Rect({ ...createAnnotationProps('rect'), left: start.x, top: start.y, width: 1, height: 1, fill: 'rgba(0,0,0,0)', stroke: state.color, strokeWidth: state.width });
    if (state.tool === 'circle') preview = new fabric.Ellipse({ ...createAnnotationProps('circle'), left: start.x, top: start.y, rx: 1, ry: 1, fill: 'rgba(0,0,0,0)', stroke: state.color, strokeWidth: state.width });
    if (preview) { canvas.add(preview); canvas.setActiveObject(preview); }
  });
  canvas.on('mouse:move', (event) => {
    if (!start || !preview) return;
    const pointer = canvas.getPointer(event.e);
    const left = Math.min(start.x, pointer.x), top = Math.min(start.y, pointer.y);
    const width = Math.abs(pointer.x - start.x), height = Math.abs(pointer.y - start.y);
    if (state.tool === 'rect') preview.set({ left, top, width, height });
    if (state.tool === 'circle') preview.set({ left, top, rx: width / 2, ry: height / 2 });
    canvas.requestRenderAll();
  });
  canvas.on('mouse:up', (event) => {
    if (!start) return;
    const pointer = canvas.getPointer(event.e);
    if (state.tool === 'arrow') finalizeObject(makeArrow(start, pointer));
    else if (preview) { pushHistory(); renderAnnotationList(); }
    start = null; preview = null;
  });
  canvas.on('path:created', (event) => { event.path.set(createAnnotationProps('brush')); pushHistory(); renderAnnotationList(); });
  canvas.on('object:modified', () => { pushHistory(); renderAnnotationList(); });
  canvas.on('selection:created', renderAnnotationList);
  canvas.on('selection:updated', renderAnnotationList);
  canvas.on('selection:cleared', renderAnnotationList);
}
```

In the `fabric.Image.fromURL` callback inside `initCanvas`, after `pushHistory();`, add:

```js
attachCanvasEvents();
renderAnnotationList();
setTool('select');
```

- [ ] **Step 4: Wire list selection and note edits**

Inside the `DOMContentLoaded` listener, add:

```js
const list = byId('annotationList');
if (list) {
  list.addEventListener('click', (event) => {
    const btn = event.target.closest('[data-select-annotation]');
    if (!btn || !state.canvas) return;
    const obj = annotationObjects().find(item => item.annotationId === btn.dataset.selectAnnotation);
    if (obj) { state.canvas.setActiveObject(obj); state.canvas.requestRenderAll(); renderAnnotationList(); }
  });
  list.addEventListener('input', (event) => {
    const input = event.target.closest('[data-note-for]');
    if (!input) return;
    const obj = annotationObjects().find(item => item.annotationId === input.dataset.noteFor);
    if (obj) obj.note = input.value;
  });
}
```

- [ ] **Step 5: Browser smoke test and commit**

Run:

```powershell
node --check static\annotation-workspace.js
python app.py
```

Open `http://127.0.0.1:8000`, choose an image, open the workspace, create rectangle, circle, arrow, brush stroke, and text; verify the annotation list updates and notes can be typed.

Then run:

```powershell
git add static\annotation-workspace.js
git commit -m "Implement annotation drawing tools"
```

Expected: Node syntax check passes; manual smoke test passes; commit succeeds.

---

### Task 4: Export annotated PNG and integrate with `/api/edit`

**Files:**
- Modify: `static/annotation-workspace.js`
- Modify: `static/index.html`

**Interfaces:**
- Consumes: `/api/edit` form fields `prompt`, `model`, `n`, `save_annotated`, `image`.
- Produces: `AnnotationWorkspace.send()`, `submitAnnotatedEdit(payload)`, `openWorkspaceFromImage(imageUrl, sourceName)`, `renderImageGrid(images, altPrefix)`.

- [ ] **Step 1: Add prompt composition and PNG export**

Add to `static/annotation-workspace.js`:

```js
function collectNotes() {
  return annotationObjects().map((obj, index) => ({ id: obj.annotationId, type: obj.annotationType, color: obj.color || state.color, note: (obj.note || '').trim(), label: `${index + 1}. ${typeLabel(obj.annotationType)}` }));
}
function composePrompt() {
  const basePrompt = byId('workspacePrompt').value.trim();
  const lines = collectNotes().map((item, index) => `${index + 1}. ${item.color} ${typeLabel(item.type)}：${item.note || '请重点参考此处标注区域。'}`);
  return lines.length ? `${basePrompt}\n\n标注说明：\n${lines.join('\n')}` : basePrompt;
}
function dataUrlToBlob(dataUrl) {
  const [header, payload] = dataUrl.split(',');
  const mime = header.match(/data:([^;]+)/)[1];
  const binary = atob(payload);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}
function exportPngBlob() {
  if (!state.canvas) throw new Error('画布还没有准备好');
  state.canvas.discardActiveObject();
  state.canvas.requestRenderAll();
  return dataUrlToBlob(state.canvas.toDataURL({ format: 'png', multiplier: 1 }));
}
```

- [ ] **Step 2: Add workspace action methods**

Add:

```js
function undo() {
  if (!state.canvas || state.history.length < 2) return;
  state.history.pop();
  const previous = state.history[state.history.length - 1];
  state.suppressHistory = true;
  state.canvas.loadFromJSON(previous, () => { state.suppressHistory = false; state.canvas.renderAll(); renderAnnotationList(); });
}
function deleteSelected() {
  const active = state.canvas && state.canvas.getActiveObject();
  if (!active) return;
  state.canvas.remove(active); state.canvas.discardActiveObject(); pushHistory(); renderAnnotationList();
}
function clearAnnotations() {
  if (!state.canvas) return;
  annotationObjects().forEach(obj => state.canvas.remove(obj));
  state.canvas.discardActiveObject(); pushHistory(); renderAnnotationList();
}
async function send() {
  if (!state.options || typeof state.options.onSend !== 'function') return;
  const button = byId('annotationSendBtn');
  button.disabled = true; button.textContent = 'Sending…';
  try {
    await state.options.onSend({ blob: exportPngBlob(), filename: `annotated_${Date.now()}.png`, prompt: composePrompt(), notes: collectNotes() });
    close();
  } finally {
    button.disabled = false; button.textContent = 'Send Edit';
  }
}
```

Expose them:

```js
window.AnnotationWorkspace = { open, close, setTool, undo, deleteSelected, clearAnnotations, send };
```

Wire buttons in `DOMContentLoaded`:

```js
const undoBtn = byId('annotationUndoBtn'), deleteBtn = byId('annotationDeleteBtn'), clearBtn = byId('annotationClearBtn'), sendBtn = byId('annotationSendBtn');
if (undoBtn) undoBtn.addEventListener('click', undo);
if (deleteBtn) deleteBtn.addEventListener('click', deleteSelected);
if (clearBtn) clearBtn.addEventListener('click', clearAnnotations);
if (sendBtn) sendBtn.addEventListener('click', send);
document.addEventListener('keydown', (event) => { if (event.key === 'Escape' && byId('annotationModal')?.classList.contains('open')) close(); });
```

- [ ] **Step 3: Add open and upload-preview helpers to inline script**

In `static/index.html`, before `function generate()`, add:

```js
let uploadedImageObjectUrl = null;
function currentPrompt() { return document.getElementById('prompt').value.trim(); }
function openWorkspaceFromImage(imageUrl, sourceName) {
  if (!currentPrompt()) { flashEmpty(); return; }
  AnnotationWorkspace.open({ imageUrl, sourceName, prompt: currentPrompt(), onSend: submitAnnotatedEdit });
}
function renderImageGrid(images, altPrefix) {
  const html = images.map((image, index) => {
    const src = image.file_url || image.data_url;
    const safeAlt = `${altPrefix} ${index + 1}`;
    return `<img src="${src}" alt="${safeAlt}" title="Click to annotate" data-workspace-src="${src}" data-workspace-name="${safeAlt}">`;
  }).join('');
  setTimeout(() => document.querySelectorAll('[data-workspace-src]').forEach(img => { img.onclick = () => openWorkspaceFromImage(img.dataset.workspaceSrc, img.dataset.workspaceName); }), 0);
  return `<div class="plate-grid ${images.length === 1 ? 'single' : ''}">${html}</div>`;
}
```

Before `applyLanguage();`, add:

```js
document.getElementById('editImageFile').addEventListener('change', () => {
  const input = document.getElementById('editImageFile');
  const file = input.files && input.files[0];
  const preview = document.getElementById('uploadPreview');
  const image = document.getElementById('uploadPreviewImage');
  const button = document.getElementById('uploadPreviewButton');
  if (uploadedImageObjectUrl) URL.revokeObjectURL(uploadedImageObjectUrl);
  uploadedImageObjectUrl = null;
  if (!file) { preview.style.display = 'none'; image.removeAttribute('src'); return; }
  uploadedImageObjectUrl = URL.createObjectURL(file);
  image.src = uploadedImageObjectUrl;
  preview.style.display = 'block';
  button.onclick = () => openWorkspaceFromImage(uploadedImageObjectUrl, file.name || 'Uploaded image');
});
```

- [ ] **Step 4: Replace result rendering and add annotated submit helper**

In both `generate()` and `editImage()`, replace the inline `plate-grid` template with:

```js
result.innerHTML = renderImageGrid(images, 'plate');
```

Use `'edited plate'` in `editImage()`.

Add before `function editImage()`:

```js
async function submitAnnotatedEdit(payload) {
  const model = document.getElementById('model').value;
  const n = Number(document.getElementById('count').value);
  const btn = document.getElementById('editBtn');
  const generateBtn = document.getElementById('btn');
  const result = document.getElementById('result');
  const cap = document.getElementById('caption');
  btn.disabled = true; generateBtn.disabled = true; cap.style.display = 'none';
  result.innerHTML = `<div class="loading"><div class="loading-label" id="loadingLabel"></div><div class="loading-bar"></div></div>`;
  const lbl = n > 1 ? t('generatingPlates', n) : t('editing');
  document.getElementById('loadingLabel').innerHTML = [...lbl].map(c => c === ' ' ? '<span>&nbsp;</span>' : `<span>${c}</span>`).join('');
  const form = new FormData();
  form.append('prompt', payload.prompt); form.append('model', model); form.append('n', String(n)); form.append('save_annotated', 'true'); form.append('image', payload.blob, payload.filename);
  const t0 = Date.now();
  try {
    const response = await fetch('/api/edit', { method: 'POST', body: form });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || t('failed'));
    const images = Array.isArray(data.images) && data.images.length ? data.images : [{ data_url: data.data_url }];
    result.innerHTML = renderImageGrid(images, 'edited plate');
    const sec = ((Date.now() - t0) / 1000).toFixed(1);
    const plateLabel = images.length === 1 ? t('plateSingle') : t('plateMulti', images.length);
    document.getElementById('cap-left').textContent = `${plateLabel} · ${data.model} · annotated edit`;
    const saved = images.every(image => image.file_path) ? t('savedToOutput') : '';
    const annotated = data.annotated_image && data.annotated_image.file_path ? ' · annotated saved' : '';
    document.getElementById('cap-right').textContent = `${t('engraved', sec)}${saved}${annotated}`;
    cap.style.display = 'flex';
  } catch (error) {
    result.innerHTML = `<div class="error">${error.message}</div>`;
    throw error;
  } finally {
    btn.disabled = false; generateBtn.disabled = false;
  }
}
```

- [ ] **Step 5: Verify and commit integration**

Run:

```powershell
node --check static\annotation-workspace.js
python -m py_compile app.py image_gen.py
git add static\annotation-workspace.js static\index.html
git commit -m "Wire annotation workspace editing flow"
```

Manual check: choose a local image, type a prompt, open workspace, draw a rectangle, add a note, click Send Edit. If upstream is configured, verify `output/annotated_*.png` and `output/edited_*.png` exist. If upstream is unavailable, verify DevTools Network shows `save_annotated=true`, `image` type `image/png`, and `prompt` contains `标注说明：`.

---
### Task 5: Polish, compatibility checks, and documentation

**Files:**
- Modify: `static/index.html`
- Modify: `static/annotation-workspace.js`
- Modify: `README.md`

**Interfaces:**
- Consumes: completed workspace flow from Tasks 1-4.
- Produces: documented workflow and verification that unsupported upstream parameters were not reintroduced.

- [ ] **Step 1: Add missing translation keys used by new markup**

In `static/index.html`, add `openWorkspace: 'Open workspace'` to `translations.en` and `openWorkspace: '打开工作台'` to `translations.zh`.

- [ ] **Step 2: Improve error display in workspace send**

In `static/annotation-workspace.js`, change `send()` catch handling so the workspace button restores itself and the existing result area shows the thrown error through `submitAnnotatedEdit()`. Keep this exact behavior: do not close the modal when `onSend()` throws; close only after it resolves successfully.

Use this `send()` shape:

```js
async function send() {
  if (!state.options || typeof state.options.onSend !== 'function') return;
  const button = byId('annotationSendBtn');
  button.disabled = true;
  button.textContent = 'Sending…';
  try {
    await state.options.onSend({ blob: exportPngBlob(), filename: `annotated_${Date.now()}.png`, prompt: composePrompt(), notes: collectNotes() });
    close();
  } finally {
    button.disabled = false;
    button.textContent = 'Send Edit';
  }
}
```

- [ ] **Step 3: Add README section**

Append after the existing “图片编辑” section:

```markdown
## 图片标注工作台

选择本地图片后，页面会立即显示预览。点击预览、生成结果图或编辑结果图，可以打开图片工作台。在工作台里可以用矩形、圆形、箭头、画笔和文字对图片进行标注，并在右侧为每个标注填写说明。

点击工作台里的发送编辑时，前端会把标注直接合成为一张 PNG，并把标注说明追加到 Prompt 后提交给本地 `/api/edit`。后端仍然只向上游图片编辑接口发送 `model`、`prompt` 和 `image`，以兼容 ChatGPT 账号反向代理类上游。发送给上游的标注 PNG 会保存为 `output/annotated_*.png`，AI 返回结果会保存为 `output/edited_*.png`。
```

- [ ] **Step 4: Verify unsupported parameters are absent from request-building code**

Run:

```powershell
Select-String -Path app.py,image_gen.py,static\index.html,static\annotation-workspace.js -Pattern 'quality','output_format','background','mask','tools[0].n','"size"',"'size'"
```

Expected: no matches in request payload-building code. Matches in design docs or README are acceptable only when they explicitly say those fields are unsupported and not sent.

- [ ] **Step 5: Run syntax checks**

Run:

```powershell
python -m py_compile app.py image_gen.py
node --check static\annotation-workspace.js
```

Expected: both commands exit with code 0.

- [ ] **Step 6: Run full manual acceptance test**

With the app running at `http://127.0.0.1:8000`, verify:

1. Select a local PNG/JPEG/WEBP image; preview appears.
2. Click preview; workspace opens.
3. Draw rectangle, circle, arrow, brush stroke, and text.
4. Move and resize at least one annotation.
5. Add notes in the annotation list.
6. Delete one annotation.
7. Use undo once.
8. Use clear once, then draw a new annotation.
9. Click Send Edit; on success, `output/annotated_*.png` and `output/edited_*.png` exist.
10. Click an edited result; workspace opens again with that result as the base image.
11. Generate a text-only image; click the generated image; workspace opens with that generated image as the base image.
12. Set Count to 2 for an annotated edit; backend returns two edited images via local loop without upstream `n` error.

- [ ] **Step 7: Commit final polish**

Run:

```powershell
git add static\index.html static\annotation-workspace.js README.md
git commit -m "Document and polish annotation workspace"
```

Expected: commit succeeds.

- [ ] **Step 8: Final status report**

Run:

```powershell
git status --short
git log --oneline -5
```

Expected: no unintended tracked changes; recent commits show backend, shell, tools, integration, and polish commits.

---

## Self-Review Notes

- Spec coverage: Tasks cover annotated PNG saving, local Fabric.js, upload preview, generated/edited image click-to-open, rectangle/circle/arrow/brush/text annotations, notes, undo/delete/clear, baked PNG export, prompt note appending, and conservative upstream calls.
- Scope check: The plan stays inside the existing FastAPI + static frontend architecture and does not add Next.js, database, auth, masks, or session history.
- Type consistency: The frontend handoff object is consistently `{ blob, filename, prompt, notes }`; the backend response field is consistently `annotated_image`.
- Test coverage: Backend syntax checks, Node syntax checks, network form-data inspection, output-file inspection, and full browser acceptance checklist are included.

