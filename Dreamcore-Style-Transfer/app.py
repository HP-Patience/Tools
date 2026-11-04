# -*- coding: utf-8 -*-
"""
Dreamcore Style Transfer — 桌面级 GUI 应用
零额外依赖，纯 Tkinter + Pillow
"""
import sys, os, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── 先切终端编码（win32） ────────────────────────────
if sys.platform == 'win32':
    os.system('chcp 65001 > nul 2>&1')
    try: sys.stdout.reconfigure(encoding='utf-8')
    except: pass

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

from core.image_processor import process_image, list_styles, ImageProcessor

# ═══════════════════════════════════════════════════════
# 配色方案 — 暗色主题
# ═══════════════════════════════════════════════════════
BG_DARK   = "#1a1a2e"
BG_PANEL  = "#16213e"
BG_CARD   = "#0f3460"
ACCENT    = "#e94560"
TEXT_WHITE = "#eeeeee"
TEXT_GRAY  = "#a0a0b0"
GREEN_OK   = "#00d2a0"
YELLOW     = "#ffd369"
INTENSITY_COLORS = {"mild": "#4ecca3", "standard": "#ffd369", "extreme": "#e94560"}

STYLE_DATA = [
    ("🌀", "经典梦核", "dreamcore",          "过曝+柔光+褪色+胶片颗粒"),
    ("👁️", "怪核",     "weirdcore",          "高对比+色散+故障+彩色噪点"),
    ("🚪", "阈限空间", "liminal_space",       "去饱和+冷色调+空旷+暗角"),
    ("💔", "伤核",     "traumacore",         "粉色高光+褪色+柔焦+重暗角"),
    ("🟨", "后室",     "backrooms",           "黄色荧光+VHS扫描线+噪点"),
    ("🌈", "童年核",   "kidcore",             "极高饱和+提亮+Vibrance"),
    ("🏊", "池核",     "poolcore",            "水下蓝+偏青+蓝色高光染色"),
    ("💾", "网核",     "webcore",             "像素化+CRT扫描线+故障"),
    ("🌀", "催眠核",   "hypnocore",           "漩涡扭曲+径向模糊+迷幻"),
    ("📺", "中式梦核", "chinese_dreamcore",    "暖黄褪色+CCD颗粒+扫描线"),
]

INTENSITY_OPTIONS = [
    ("轻度",   "mild",    "若有若无的风格暗示"),
    ("标准",   "standard", "标准风格效果（推荐）"),
    ("极致",   "extreme", "极致渲染（参数 ×1.5）"),
]


# ═══════════════════════════════════════════════════════
# 主应用类
# ═══════════════════════════════════════════════════════
class DreamcoreApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Dreamcore Style Transfer v2.0 — 梦核风格图像处理器")
        self.root.geometry("1100x720")
        self.root.minsize(900, 600)
        self.root.configure(bg=BG_DARK)

        # ── 状态 ──────────────────────────────────
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.selected_style = tk.StringVar(value="dreamcore")
        self.selected_intensity = tk.StringVar(value="standard")
        self.processing = False
        self.preview_img = None   # Pillow Image
        self.result_img = None    # 处理结果
        self.view_mode = "before"  # before / after

        # ── 构建界面 ──────────────────────────────
        self._build_header()
        self._build_body()
        self._build_footer()

        # 绑定快捷键
        root.bind('<Control-o>', lambda e: self._browse_file())
        root.bind('<Control-Return>', lambda e: self._start_process())
        root.bind('<Escape>', lambda e: self._toggle_view())

    # ═══════════════════════════════════════════════════
    # 顶部 Header
    # ═══════════════════════════════════════════════════
    def _build_header(self):
        header = tk.Frame(self.root, bg=BG_PANEL, height=60)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        inner = tk.Frame(header, bg=BG_PANEL)
        inner.pack(expand=True, fill="both", padx=24, pady=6)

        tk.Label(inner, text="🎨  Dreamcore Style Transfer",
                 font=("Segoe UI", 18, "bold"), fg=TEXT_WHITE, bg=BG_PANEL)\
            .pack(side="left")

        tk.Label(inner, text='10 种「核」风格  |  纯像素级渲染  |  零 GPU 依赖',
                 font=("Segoe UI", 10), fg=TEXT_GRAY, bg=BG_PANEL)\
            .pack(side="left", padx=20, pady=(5, 0))

    # ═══════════════════════════════════════════════════
    # 主体 — 左图右控
    # ═══════════════════════════════════════════════════
    def _build_body(self):
        body = tk.Frame(self.root, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=16, pady=(10, 0))

        # ── 左：图片区域 ──────────────────────────
        self._build_image_panel(body)

        # ── 右：控制面板 ──────────────────────────
        self._build_control_panel(body)

        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

    # ═══════════════════════════════════════════════════
    # 图片面板
    # ═══════════════════════════════════════════════════
    def _build_image_panel(self, parent):
        panel = tk.Frame(parent, bg=BG_PANEL, bd=0)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # ── 标题栏 ────────────────────────────────
        title = tk.Frame(panel, bg=BG_PANEL)
        title.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(title, text="📷 图片预览", font=("Segoe UI", 12, "bold"),
                 fg=TEXT_WHITE, bg=BG_PANEL).pack(side="left")
        self.lbl_view_mode = tk.Label(title, text="原图", font=("Segoe UI", 9),
                                       fg=YELLOW, bg=BG_PANEL)
        self.lbl_view_mode.pack(side="right")

        # ── 画布 ──────────────────────────────────
        canvas_frame = tk.Frame(panel, bg=BG_PANEL)
        canvas_frame.pack(fill="both", expand=True, padx=16, pady=10)

        self.canvas = tk.Canvas(canvas_frame, bg="#0d1117",
                                highlightthickness=1, highlightbackground="#30363d")
        self.canvas.pack(fill="both", expand=True)

        # 占位提示
        self.canvas_text = self.canvas.create_text(
            200, 150, text="拖入图片或点击下方按钮\n\n支持 JPG / PNG / WEBP / BMP",
            font=("Segoe UI", 12), fill="#484f58", justify="center")

        # ── 底部按钮栏 ────────────────────────────
        btn_bar = tk.Frame(panel, bg=BG_PANEL)
        btn_bar.pack(fill="x", padx=16, pady=(0, 12))

        self._btn(btn_bar, "📂 选择图片", self._browse_file,
                  BG_CARD, TEXT_WHITE).pack(side="left", padx=(0, 8))

        self.btn_toggle = self._btn(btn_bar, "🔄 查看结果", self._toggle_view,
                                     "#30363d", TEXT_GRAY)
        self.btn_toggle.pack(side="left")
        self.btn_toggle.config(state="disabled")

        tk.Label(btn_bar, text="Ctrl+O 打开  |  Esc 切换视图",
                 font=("Segoe UI", 8), fg=TEXT_GRAY, bg=BG_PANEL)\
            .pack(side="right")

        # 绑定 resize
        self.canvas.bind("<Configure>", self._redraw_preview)

    # ═══════════════════════════════════════════════════
    # 控制面板
    # ═══════════════════════════════════════════════════
    def _build_control_panel(self, parent):
        panel = tk.Frame(parent, bg=BG_PANEL)
        panel.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # ── 滚动容器 ──────────────────────────────
        canvas = tk.Canvas(panel, bg=BG_PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG_PANEL)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 鼠标滚轮
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        inner = tk.Frame(scroll_frame, bg=BG_PANEL)
        inner.pack(fill="x", padx=14, pady=14)

        # ── 风格选择 ──────────────────────────────
        tk.Label(inner, text="🎨 选择风格", font=("Segoe UI", 12, "bold"),
                 fg=TEXT_WHITE, bg=BG_PANEL).pack(anchor="w")

        style_container = tk.Frame(inner, bg=BG_PANEL)
        style_container.pack(fill="x", pady=(8, 0))

        for i, (emoji, name, sid, desc) in enumerate(STYLE_DATA):
            self._make_style_card(style_container, emoji, name, sid, desc, i)

        # ── 强度选择 ──────────────────────────────
        tk.Label(inner, text="🔥 风格强度", font=("Segoe UI", 12, "bold"),
                 fg=TEXT_WHITE, bg=BG_PANEL).pack(anchor="w", pady=(20, 0))

        intensity_frame = tk.Frame(inner, bg=BG_PANEL)
        intensity_frame.pack(fill="x", pady=(8, 0))

        for label, val, hint in INTENSITY_OPTIONS:
            self._make_intensity_btn(intensity_frame, label, val, hint)

        # ── 处理按钮 ──────────────────────────────
        self.btn_process = tk.Button(inner, text="⚡ 开始处理 (Ctrl+Enter)",
                                     font=("Segoe UI", 13, "bold"),
                                     fg=TEXT_WHITE, bg=ACCENT,
                                     activebackground="#ff6b81", activeforeground=TEXT_WHITE,
                                     bd=0, padx=20, pady=12, cursor="hand2",
                                     command=self._start_process)
        self.btn_process.pack(fill="x", pady=(20, 5))

        self.btn_process.bind("<Enter>", lambda e:
            self.btn_process.configure(bg="#ff6b81"))
        self.btn_process.bind("<Leave>", lambda e:
            self.btn_process.configure(bg=ACCENT if not self.processing else "#555"))

        # ── 进度 ──────────────────────────────────
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(inner, variable=self.progress_var,
                                             maximum=100, mode="determinate")
        self.progress_bar.pack(fill="x", pady=(0, 2))
        self._set_progress_visible(False)

        self.lbl_status = tk.Label(inner, text="",
                                   font=("Segoe UI", 9), fg=GREEN_OK, bg=BG_PANEL)
        self.lbl_status.pack(anchor="w")

    # ═══════════════════════════════════════════════════
    # 底部信息栏
    # ═══════════════════════════════════════════════════
    def _build_footer(self):
        footer = tk.Frame(self.root, bg=BG_DARK, height=28)
        footer.pack(fill="x", side="bottom", padx=16, pady=(0, 8))

        self.lbl_input_info = tk.Label(footer, text="未选择图片",
                                       font=("Segoe UI", 9), fg=TEXT_GRAY, bg=BG_DARK)
        self.lbl_input_info.pack(side="left")

        self.lbl_output_info = tk.Label(footer, text="",
                                        font=("Segoe UI", 9), fg=GREEN_OK, bg=BG_DARK)
        self.lbl_output_info.pack(side="right")

    # ═══════════════════════════════════════════════════
    # 风格卡片（可点击单选）
    # ═══════════════════════════════════════════════════
    def _make_style_card(self, parent, emoji, name, sid, desc, index):
        """创建可点击的 style 卡片"""
        is_selected = (sid == self.selected_style.get())

        card = tk.Frame(parent, bg=BG_CARD if is_selected else "#1e2a3a",
                        bd=0, cursor="hand2", padx=2, pady=2)
        card.pack(fill="x", pady=2)

        inner = tk.Frame(card, bg=card["bg"])
        inner.pack(fill="x", padx=(8, 4), pady=5)

        tk.Label(inner, text=f"{emoji}  {name}",
                 font=("Segoe UI", 11, "bold"),
                 fg=TEXT_WHITE if is_selected else TEXT_GRAY,
                 bg=inner["bg"]).pack(anchor="w")

        tk.Label(inner, text=desc,
                 font=("Segoe UI", 8),
                 fg=TEXT_GRAY, bg=inner["bg"]).pack(anchor="w")

        # 绑定点击
        for w in (card, inner, *inner.winfo_children()):
            w.bind("<Button-1>", lambda e, s=sid: self._select_style(s))
            w.bind("<Enter>", lambda e, c=card: c.configure(bg=BG_CARD))
            w.bind("<Leave>", lambda e, c=card: c.configure(
                bg=BG_CARD if self.selected_style.get() == sid else "#1e2a3a"))

        # 保存引用用于刷新高亮
        card._style_id = sid
        if not hasattr(self, '_style_cards'):
            self._style_cards = []
        self._style_cards.append(card)

    def _select_style(self, sid):
        self.selected_style.set(sid)
        for card in self._style_cards:
            is_sel = (card._style_id == sid)
            card.configure(bg=BG_CARD if is_sel else "#1e2a3a")
            for child in card.winfo_children():
                child.configure(bg=BG_CARD if is_sel else "#1e2a3a")
                for gchild in child.winfo_children():
                    gchild.configure(
                        fg=TEXT_WHITE if is_sel else TEXT_GRAY,
                        bg=BG_CARD if is_sel else "#1e2a3a")

    # ═══════════════════════════════════════════════════
    # 强度按钮
    # ═══════════════════════════════════════════════════
    def _make_intensity_btn(self, parent, label, val, hint):
        is_sel = (val == self.selected_intensity.get())
        color = INTENSITY_COLORS[val]

        frame = tk.Frame(parent, bg=color if is_sel else "#1e2a3a",
                         bd=0, cursor="hand2")
        frame.pack(side="left", fill="x", expand=True, padx=3)

        font_spec = ("Segoe UI", 9, "bold") if is_sel else ("Segoe UI", 9)
        tk.Label(frame, text=f"{label}\n{hint}",
                 font=font_spec,
                 fg=BG_DARK if is_sel else TEXT_GRAY,
                 bg=frame["bg"], justify="center", pady=8)\
            .pack(fill="x")

        frame.bind("<Button-1>", lambda e, v=val: self._select_intensity(v))
        frame.winfo_children()[0].bind("<Button-1>",
            lambda e, v=val: self._select_intensity(v))

        if not hasattr(self, '_intensity_frames'):
            self._intensity_frames = []
        self._intensity_frames.append((frame, val, color))

    def _select_intensity(self, val):
        self.selected_intensity.set(val)
        for frame, v, color in self._intensity_frames:
            is_sel = (v == val)
            frame.configure(bg=color if is_sel else "#1e2a3a")
            lbl = frame.winfo_children()[0]
            font2 = ("Segoe UI", 9, "bold") if is_sel else ("Segoe UI", 9)
            lbl.configure(fg=BG_DARK if is_sel else TEXT_GRAY, font=font2)

    # ═══════════════════════════════════════════════════
    # 图片加载与预览
    # ═══════════════════════════════════════════════════
    def _browse_file(self):
        path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.webp *.bmp *.gif"),
                       ("所有文件", "*.*")])
        if path:
            self._load_image(path)

    def _load_image(self, path):
        try:
            self.preview_img = Image.open(path).convert("RGB")
            self.input_path.set(path)
            self.result_img = None
            self.view_mode = "before"
            self.lbl_view_mode.config(text="原图")
            self.btn_toggle.config(state="disabled")
            self.lbl_output_info.config(text="")

            self.lbl_input_info.config(
                text=f"📷 {os.path.basename(path)}  |  "
                     f"{self.preview_img.width}×{self.preview_img.height}  |  "
                     f"{os.path.getsize(path)/1024:.1f} KB")

            self._redraw_preview()
        except Exception as e:
            messagebox.showerror("加载失败", f"无法打开图片：\n{e}")

    def _redraw_preview(self, event=None):
        """在 canvas 上绘制当前预览图片"""
        self.canvas.delete("all")

        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 50: w = 500
        if h < 50: h = 350

        img = self.result_img if (self.view_mode == "after" and self.result_img) \
              else self.preview_img

        if img is None:
            self.canvas_text = self.canvas.create_text(
                w // 2, h // 2,
                text="拖入图片或点击下方按钮\n\n支持 JPG / PNG / WEBP / BMP",
                font=("Segoe UI", 12), fill="#484f58", justify="center")
            return

        # 等比例缩放
        iw, ih = img.size
        ratio = min((w - 20) / iw, (h - 20) / ih, 1.0)
        nw, nh = int(iw * ratio), int(ih * ratio)

        resized = img.resize((nw, nh), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(resized)
        self.canvas.create_image(w // 2, h // 2,
                                 image=self._tk_img, anchor="center")

    def _toggle_view(self, event=None):
        if self.result_img is None:
            return
        self.view_mode = "after" if self.view_mode == "before" else "before"
        self.lbl_view_mode.config(
            text="处理结果" if self.view_mode == "after" else "原图")
        self.lbl_view_mode.config(
            fg=GREEN_OK if self.view_mode == "after" else YELLOW)
        self._redraw_preview()

    # ═══════════════════════════════════════════════════
    # 处理逻辑
    # ═══════════════════════════════════════════════════
    def _start_process(self):
        if self.processing:
            return
        if self.preview_img is None:
            messagebox.showwarning("提示", "请先选择一张图片")
            return

        self.processing = True
        self.btn_process.config(text="⏳ 处理中...", bg="#555", state="disabled")
        self._set_progress_visible(True)
        self.progress_var.set(0)
        self.lbl_status.config(text="初始化...", fg=YELLOW)

        # 启动后台线程处理
        t = threading.Thread(target=self._process_thread, daemon=True)
        t.start()

        # 启动动画轮询
        self._poll_progress(t)

    def _process_thread(self):
        """后台线程：执行图像处理"""
        stages = [
            (10, "色彩分级..."),
            (30, "曝光调整..."),
            (50, "颗粒噪点..."),
            (70, "柔光 Bloom..."),
            (90, "扭曲特效..."),
        ]

        # 用进度模拟各阶段（实际处理很快，所以加点延迟让 GUI 可见）
        for pct, msg in stages:
            self._stage = pct
            self._stage_msg = msg
            time.sleep(0.15)

        # 实际处理
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            out_dir = os.path.join(base_dir, 'output')
            os.makedirs(out_dir, exist_ok=True)

            base_name = os.path.splitext(os.path.basename(self.input_path.get()))[0]
            out_path = os.path.join(
                out_dir,
                f"{base_name}_{self.selected_style.get()}_"
                f"{self.selected_intensity.get()}.jpg")

            process_image(
                self.input_path.get(),
                self.selected_style.get(),
                self.selected_intensity.get(),
                out_path
            )

            self._result_path = out_path
            self._success = True
        except Exception as e:
            self._error = str(e)
            self._success = False

    def _poll_progress(self, thread):
        """轮询处理进度"""
        if thread.is_alive():
            stage = getattr(self, '_stage', 0)
            msg = getattr(self, '_stage_msg', '处理中...')
            self.progress_var.set(stage)
            self.lbl_status.config(text=msg, fg=YELLOW)
            self.root.after(80, lambda: self._poll_progress(thread))
        else:
            self._on_process_done()

    def _on_process_done(self):
        """处理完成回调"""
        self.processing = False
        self._set_progress_visible(False)

        if not self._success:
            self.btn_process.config(text="⚡ 开始处理 (Ctrl+Enter)",
                                    bg=ACCENT, state="normal")
            messagebox.showerror("处理失败", self._error)
            return

        # 加载结果
        self.result_img = Image.open(self._result_path).convert("RGB")
        self.view_mode = "after"
        self.lbl_view_mode.config(text="处理结果", fg=GREEN_OK)
        self.btn_toggle.config(state="normal", text="🔄 切换原图")

        self.lbl_output_info.config(
            text=f"✅ {os.path.basename(self._result_path)}  |  "
                 f"{os.path.getsize(self._result_path)/1024:.1f} KB")

        self.lbl_status.config(text="✅ 处理完成！", fg=GREEN_OK)

        self.btn_process.config(text="⚡ 开始处理 (Ctrl+Enter)",
                                bg=ACCENT, state="normal")
        self.progress_var.set(100)

        self._redraw_preview()

    # ═══════════════════════════════════════════════════
    # 辅助
    # ═══════════════════════════════════════════════════
    def _btn(self, parent, text, cmd, bg, fg, **kw):
        return tk.Button(parent, text=text, font=("Segoe UI", 10),
                         fg=fg, bg=bg, activebackground=bg, activeforeground=fg,
                         bd=0, padx=12, pady=6, cursor="hand2",
                         command=cmd, **kw)

    def _set_progress_visible(self, v):
        if v:
            self.progress_bar.pack(fill="x", pady=(0, 2))
            self.progress_bar.lift()
        else:
            self.progress_bar.pack_forget()


# ═══════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════
def main():
    root = tk.Tk()
    # 设置窗口图标（如果存在）
    try:
        root.iconbitmap(default="")
    except:
        pass

    app = DreamcoreApp(root)

    # 居中显示
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    ww = root.winfo_width()
    wh = root.winfo_height()
    x = (sw - ww) // 2
    y = (sh - wh) // 2
    root.geometry(f"+{x}+{y}")

    root.mainloop()


if __name__ == '__main__':
    main()
