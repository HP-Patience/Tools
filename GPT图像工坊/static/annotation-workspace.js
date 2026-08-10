(function () {
  'use strict';

  const state = {
    canvas: null,
    options: null,
    tool: 'select',
    color: '#ef4444',
    width: 4,
    history: [],
    suppressHistory: false,
    counter: 1,
  };

  function byId(id) {
    return document.getElementById(id);
  }

  function requireFabric() {
    if (!window.fabric) {
      throw new Error('Fabric.js 未加载，请检查 /static/vendor/fabric.min.js');
    }
  }

  function createAnnotationProps(type) {
    const id = `a${state.counter++}`;
    return {
      annotationId: id,
      annotationType: type,
      note: '',
      color: state.color,
      cornerColor: state.color,
      borderColor: state.color,
      transparentCorners: false,
    };
  }

  function annotationObjects() {
    if (!state.canvas) return [];
    return state.canvas.getObjects().filter(obj => obj.annotationId);
  }

  function typeLabel(type) {
    return ({ rect: '矩形', circle: '圆形', arrow: '箭头', brush: '画笔', text: '文字' })[type] || type;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[char]);
  }

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

  function pushHistory() {
    if (!state.canvas || state.suppressHistory) return;
    state.history.push(JSON.stringify(state.canvas.toDatalessJSON(['annotationId', 'annotationType', 'note', 'color'])));
    if (state.history.length > 40) state.history.shift();
  }

  function finalizeObject(obj) {
    if (!state.canvas || !obj) return;
    state.canvas.add(obj);
    state.canvas.setActiveObject(obj);
    state.canvas.requestRenderAll();
    pushHistory();
    renderAnnotationList();
  }

  function addTextAt(pointer) {
    const props = createAnnotationProps('text');
    const text = new fabric.Textbox('注释', {
      ...props,
      left: pointer.x,
      top: pointer.y,
      width: 180,
      fontSize: 24,
      fill: state.color,
      fontFamily: 'sans-serif',
      editable: true,
    });
    finalizeObject(text);
    setTool('select');
  }

  function makeArrow(start, end) {
    const props = createAnnotationProps('arrow');
    const angle = Math.atan2(end.y - start.y, end.x - start.x);
    const headLength = Math.max(14, state.width * 4);
    const line = new fabric.Line([start.x, start.y, end.x, end.y], {
      stroke: state.color,
      strokeWidth: state.width,
      strokeLineCap: 'round',
      originX: 'center',
      originY: 'center',
    });
    const head = new fabric.Triangle({
      left: end.x,
      top: end.y,
      width: headLength,
      height: headLength,
      fill: state.color,
      angle: angle * 180 / Math.PI + 90,
      originX: 'center',
      originY: 'center',
    });
    return new fabric.Group([line, head], props);
  }

  function attachCanvasEvents() {
    const canvas = state.canvas;
    let start = null;
    let preview = null;

    canvas.on('mouse:down', (event) => {
      if (state.tool === 'select' || state.tool === 'brush') return;
      const pointer = canvas.getPointer(event.e);
      if (state.tool === 'text') {
        addTextAt(pointer);
        return;
      }
      start = pointer;
      if (state.tool === 'rect') {
        preview = new fabric.Rect({
          ...createAnnotationProps('rect'),
          left: start.x,
          top: start.y,
          width: 1,
          height: 1,
          fill: 'rgba(0,0,0,0)',
          stroke: state.color,
          strokeWidth: state.width,
        });
      }
      if (state.tool === 'circle') {
        preview = new fabric.Ellipse({
          ...createAnnotationProps('circle'),
          left: start.x,
          top: start.y,
          rx: 1,
          ry: 1,
          fill: 'rgba(0,0,0,0)',
          stroke: state.color,
          strokeWidth: state.width,
        });
      }
      if (preview) {
        canvas.add(preview);
        canvas.setActiveObject(preview);
      }
    });

    canvas.on('mouse:move', (event) => {
      if (!start || !preview) return;
      const pointer = canvas.getPointer(event.e);
      const left = Math.min(start.x, pointer.x);
      const top = Math.min(start.y, pointer.y);
      const width = Math.abs(pointer.x - start.x);
      const height = Math.abs(pointer.y - start.y);
      if (state.tool === 'rect') {
        preview.set({ left, top, width, height });
      }
      if (state.tool === 'circle') {
        preview.set({ left, top, rx: width / 2, ry: height / 2 });
      }
      canvas.requestRenderAll();
    });

    canvas.on('mouse:up', (event) => {
      if (!start) return;
      const pointer = canvas.getPointer(event.e);
      if (state.tool === 'arrow') {
        const distance = Math.hypot(pointer.x - start.x, pointer.y - start.y);
        if (distance >= 4) finalizeObject(makeArrow(start, pointer));
      } else if (preview) {
        const bounds = preview.getBoundingRect();
        if (bounds.width < 4 && bounds.height < 4) {
          canvas.remove(preview);
        } else {
          pushHistory();
          renderAnnotationList();
        }
      }
      start = null;
      preview = null;
    });

    canvas.on('path:created', (event) => {
      const props = createAnnotationProps('brush');
      event.path.set(props);
      pushHistory();
      renderAnnotationList();
    });

    canvas.on('object:modified', () => {
      pushHistory();
      renderAnnotationList();
    });

    canvas.on('selection:created', renderAnnotationList);
    canvas.on('selection:updated', renderAnnotationList);
    canvas.on('selection:cleared', renderAnnotationList);
  }

  function initCanvas(imageUrl) {
    if (state.canvas) state.canvas.dispose();
    state.history = [];
    const canvas = new fabric.Canvas('annotationCanvas', {
      preserveObjectStacking: true,
      selection: true,
    });
    state.canvas = canvas;
    fabric.Image.fromURL(imageUrl, (img) => {
      const maxW = 900;
      const maxH = 620;
      const scale = Math.min(maxW / img.width, maxH / img.height, 1);
      const width = Math.max(320, Math.round(img.width * scale));
      const height = Math.max(260, Math.round(img.height * scale));
      canvas.setWidth(width);
      canvas.setHeight(height);
      img.set({
        left: 0,
        top: 0,
        scaleX: width / img.width,
        scaleY: height / img.height,
        selectable: false,
        evented: false,
      });
      canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas));
      pushHistory();
      attachCanvasEvents();
      renderAnnotationList();
      setTool('select');
    }, { crossOrigin: 'anonymous' });
  }

  function open(options) {
    requireFabric();
    state.options = options;
    state.tool = 'select';
    state.counter = 1;
    byId('workspaceTitle').textContent = options.sourceName || 'Image Workspace';
    byId('workspacePrompt').value = options.prompt || '';
    byId('annotationModal').classList.add('open');
    byId('annotationModal').setAttribute('aria-hidden', 'false');
    initCanvas(options.imageUrl);
  }

  function close() {
    if (state.canvas) {
      state.canvas.dispose();
      state.canvas = null;
    }
    state.history = [];
    state.options = null;
    byId('annotationList').innerHTML = '';
    byId('annotationModal').classList.remove('open');
    byId('annotationModal').setAttribute('aria-hidden', 'true');
  }

  function setTool(tool) {
    state.tool = tool;
    document.querySelectorAll('[data-annotation-tool]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.annotationTool === tool);
    });
    if (!state.canvas) return;
    state.canvas.isDrawingMode = tool === 'brush';
    state.canvas.selection = tool === 'select';
    state.canvas.skipTargetFind = tool !== 'select';
    if (state.canvas.freeDrawingBrush) {
      state.canvas.freeDrawingBrush.color = state.color;
      state.canvas.freeDrawingBrush.width = state.width;
    }
    state.canvas.defaultCursor = tool === 'select' ? 'default' : 'crosshair';
  }

  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-annotation-tool]').forEach(btn => {
      btn.addEventListener('click', () => setTool(btn.dataset.annotationTool));
    });
    const color = byId('annotationColor');
    const width = byId('annotationWidth');
    if (color) color.addEventListener('input', () => {
      state.color = color.value;
      setTool(state.tool);
    });
    if (width) width.addEventListener('input', () => {
      state.width = Number(width.value);
      setTool(state.tool);
    });
    const list = byId('annotationList');
    if (list) {
      list.addEventListener('click', (event) => {
        const btn = event.target.closest('[data-select-annotation]');
        if (!btn || !state.canvas) return;
        const obj = annotationObjects().find(item => item.annotationId === btn.dataset.selectAnnotation);
        if (obj) {
          state.canvas.setActiveObject(obj);
          state.canvas.requestRenderAll();
          renderAnnotationList();
        }
      });
      list.addEventListener('input', (event) => {
        const noteInput = event.target.closest('[data-note-for]');
        if (!noteInput) return;
        const obj = annotationObjects().find(item => item.annotationId === noteInput.dataset.noteFor);
        if (obj) obj.note = noteInput.value;
      });
    }
  });

  window.AnnotationWorkspace = {
    open,
    close,
    setTool,
  };
})();
