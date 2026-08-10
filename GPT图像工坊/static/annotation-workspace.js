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

  function pushHistory() {
    if (!state.canvas || state.suppressHistory) return;
    state.history.push(JSON.stringify(state.canvas.toDatalessJSON(['annotationId', 'annotationType', 'note', 'color'])));
    if (state.history.length > 40) state.history.shift();
  }

  function initCanvas(imageUrl) {
    if (state.canvas) state.canvas.dispose();
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
    if (!state.canvas) return;
    state.canvas.isDrawingMode = tool === 'brush';
    state.canvas.selection = tool === 'select';
    if (state.canvas.freeDrawingBrush) {
      state.canvas.freeDrawingBrush.color = state.color;
      state.canvas.freeDrawingBrush.width = state.width;
    }
    document.querySelectorAll('[data-annotation-tool]').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.annotationTool === tool);
    });
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
  });

  window.AnnotationWorkspace = {
    open,
    close,
    setTool,
  };
})();
