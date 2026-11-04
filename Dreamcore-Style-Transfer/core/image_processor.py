"""
============================================================
图像风格处理引擎 — 纯 Pillow 实现 (无 numpy 依赖)
============================================================
处理管线: 原图 → 色彩分级 → 曝光 → 颗粒 → 柔光 → 扭曲 → 输出
============================================================
"""

import os, sys, random, logging, math
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

from PIL import Image, ImageFilter, ImageEnhance, ImageOps, ImageChops


# ============================================================
# 参数
# ============================================================
@dataclass
class ColorGrade:
    temperature: float = 0.0
    tint: float = 0.0
    saturation: float = 1.0
    vibrance: float = 0.0
    brightness: int = 0
    contrast: int = 0
    fade: float = 0.0
    highlight_rgb: tuple = None
    shadow_rgb: tuple = None

@dataclass
class Exposure:
    ev: float = 0.0
    gamma: float = 1.0
    highlights: float = 0.0
    shadows: float = 0.0

@dataclass
class Grain:
    amount: float = 0.0
    size: float = 1.0
    color_noise: bool = False
    chroma_shift: float = 0.0

@dataclass
class Bloom:
    intensity: float = 0.0
    threshold: int = 200
    softness: float = 0.0
    radial: float = 0.0

@dataclass
class Distortion:
    glitch: float = 0.0
    pixelate: int = 0
    scanlines: float = 0.0
    vignette: float = 0.0
    swirl: float = 0.0

@dataclass
class StylePreset:
    style_id: str; name: str
    color: ColorGrade = field(default_factory=ColorGrade)
    exposure: Exposure = field(default_factory=Exposure)
    grain: Grain = field(default_factory=Grain)
    bloom: Bloom = field(default_factory=Bloom)
    distortion: Distortion = field(default_factory=Distortion)


# ============================================================
# 10 种风格预设
# ============================================================
PRESETS: dict[str, StylePreset] = {}

def _init():
    global PRESETS
    if PRESETS: return
    PRESETS.update({
        "dreamcore": StylePreset("dreamcore", "经典梦核",
            ColorGrade(0.6, 0, 0.7, 0, 15, -10, 0.35, (255,240,220), (40,30,50)),
            Exposure(0.8, 0.85, -0.2, 0.3),
            Grain(0.5, 1.2, False, 0.05),
            Bloom(0.5, 180, 0.3),
            Distortion(vignette=0.4)),
        "weirdcore": StylePreset("weirdcore", "怪核",
            ColorGrade(-0.3, 0.4, 1.3, 0, -10, 40, 0),
            Exposure(-0.3, 1.2, 0.4, -0.3),
            Grain(0.3, 2.0, True, 0.3),
            distortion=Distortion(glitch=0.4, vignette=0.2)),
        "liminal_space": StylePreset("liminal_space", "阈限空间",
            ColorGrade(-0.2, 0, 0.5, 0, -10, -20, 0.1, (255,255,240), (20,25,30)),
            Exposure(0, 0.9, -0.2, 0.1),
            Grain(0.15, 1.0),
            distortion=Distortion(vignette=0.3)),
        "traumacore": StylePreset("traumacore", "伤核",
            ColorGrade(0.2, 0.2, 0.5, 0, 10, -15, 0.4, (255,220,230), (50,40,60)),
            Exposure(0.3, 0.8, -0.4, 0.2),
            Grain(0.4, 0.8, False, 0.08),
            Bloom(0.3, 170, 0.2),
            distortion=Distortion(vignette=0.5)),
        "backrooms": StylePreset("backrooms", "后室",
            ColorGrade(0.8, 0.1, 0.6, 0, 20, 10, 0.2, (255,245,180), (60,55,30)),
            Exposure(0.5, 0.9, -0.3, 0),
            Grain(0.35, 1.5, True, 0.15),
            Bloom(0.2, 200),
            distortion=Distortion(scanlines=0.15, vignette=0.3)),
        "kidcore": StylePreset("kidcore", "童年核",
            ColorGrade(0.3, 0, 1.8, 0.4, 30, 30, 0),
            Exposure(0.5, 0.8, 0.2, 0.4),
            Grain(0.1, 0.5),
            Bloom(0.15, 220)),
        "poolcore": StylePreset("poolcore", "池核",
            ColorGrade(-0.6, -0.1, 0.6, 0, 5, -5, 0.15, (180,220,255), (20,40,70)),
            Exposure(0.1, 0.95, -0.1, 0.1),
            Grain(0.1, 1.0),
            Bloom(0.1, 230),
            distortion=Distortion(vignette=0.2)),
        "webcore": StylePreset("webcore", "网核",
            ColorGrade(0, 0, 1.2, 0, 0, 20, 0.1),
            Exposure(0, 1.1),
            Grain(0.2, 0.5, False, 0.1),
            distortion=Distortion(pixelate=4, scanlines=0.2, glitch=0.15)),
        "hypnocore": StylePreset("hypnocore", "催眠核",
            ColorGrade(0, 0, 1.6, 0.5, 10, 30, 0),
            Exposure(0.2, 1.0),
            Grain(0.25, 1.5, True),
            Bloom(0.4, 180, 0, 0.3),
            distortion=Distortion(swirl=0.4, glitch=0.2)),
        "chinese_dreamcore": StylePreset("chinese_dreamcore", "中式梦核",
            ColorGrade(0.5, 0, 0.55, 0, 5, -15, 0.3, (255,240,210), (40,35,30)),
            Exposure(0.3, 0.85, -0.3, 0.2),
            Grain(0.45, 0.7, True, 0.06),
            Bloom(0.25, 190, 0.15),
            distortion=Distortion(vignette=0.35, scanlines=0.05)),
    })
_init()


# ============================================================
# 工具函数
# ============================================================
def _clamp(v, lo=0, hi=255): return max(lo, min(hi, int(v)))
def _apply_rgb(img, fn):
    """对RGB三通道独立应用函数"""
    r, g, b = img.split()
    return Image.merge("RGB", (fn(r), fn(g), fn(b)))
def _luminance(img):
    """返回灰度图 (感知亮度)"""
    return img.convert("L")


# ============================================================
# 图像处理引擎
# ============================================================
class ImageProcessor:
    def __init__(self, intensity: str = "standard"):
        self.mult = {"mild": 0.5, "standard": 1.0, "extreme": 1.5}.get(intensity, 1.0)
        self.intensity = intensity

    # ---- 色彩分级 (纯PIL) ----
    def _color_grade(self, img, g: ColorGrade, m: float):
        """使用 PIL ImageEnhance + channel ops 实现色彩分级"""
        r, g_ch, b = img.split()

        # 色温: 暖=增R减B, 冷=减R增B
        t = g.temperature * m * 30
        if t != 0:
            r = r.point(lambda x: _clamp(x + t))
            b = b.point(lambda x: _clamp(x - t * 0.67))

        # 色调: 品红=增R减G, 绿=减R增G
        ti = g.tint * m * 15
        if ti != 0:
            r = r.point(lambda x: _clamp(x + ti))
            g_ch = g_ch.point(lambda x: _clamp(x - ti * 0.67))

        img = Image.merge("RGB", (r, g_ch, b))

        # 饱和度
        if g.saturation != 1.0:
            sat = 1.0 + (g.saturation - 1.0) * m
            img = ImageEnhance.Color(img).enhance(max(0, sat))

        # Vibrance (智能饱和度: 只增强低饱和区域)
        if g.vibrance != 0:
            v = g.vibrance * m * 0.3
            gray = img.convert("L")
            # 对低饱和区域更多增强
            mask = gray.point(lambda x: 255 - x)
            enhanced = ImageEnhance.Color(img).enhance(1.0 + v)
            img = Image.blend(img, enhanced, abs(v))

        # 褪色 (混合灰色)
        f = g.fade * m
        if f > 0:
            gray = img.convert("L").convert("RGB")
            img = Image.blend(img, gray, f * 0.5)

        # 亮度
        if g.brightness != 0:
            img = ImageEnhance.Brightness(img).enhance(1.0 + g.brightness * m * 0.005)

        # 对比度
        if g.contrast != 0:
            c = 1.0 + g.contrast * m * 0.01
            img = ImageEnhance.Contrast(img).enhance(max(0.01, c))

        # 高光染色
        if g.highlight_rgb:
            lum = _luminance(img)
            w = 0.15 * m
            overlay = Image.new("RGB", img.size, g.highlight_rgb)
            mask = lum.point(lambda x: 255 if x > 160 else 0)
            img = Image.composite(Image.blend(img, overlay, w), img, mask.convert("1"))

        # 阴影染色
        if g.shadow_rgb:
            lum = _luminance(img)
            w = 0.2 * m
            overlay = Image.new("RGB", img.size, g.shadow_rgb)
            mask = lum.point(lambda x: 255 if x < 90 else 0)
            img = Image.composite(Image.blend(img, overlay, w), img, mask.convert("1"))

        return img

    # ---- 曝光 ----
    def _exposure(self, img, e: Exposure, m: float):
        ev = e.ev * m
        if ev != 0:
            img = ImageEnhance.Brightness(img).enhance(1.0 + ev * 0.3)

        gamma = 1.0 + (e.gamma - 1.0) * m
        if gamma != 1.0:
            inv = 1.0 / max(0.1, gamma)
            img = _apply_rgb(img, lambda ch: ch.point(lambda x: _clamp(255 * ((x/255)**inv))))

        hl = e.highlights * m
        if hl != 0:
            lum = _luminance(img)
            lomask = lum.point(lambda x: 255 if x > 180 else 0).convert("1")
            darkened = _apply_rgb(img, lambda ch: ch.point(lambda x: _clamp(x - hl*40)))
            img = Image.composite(darkened, img, lomask)

        sh = e.shadows * m
        if sh != 0:
            lum = _luminance(img)
            shmask = lum.point(lambda x: 255 if x < 70 else 0).convert("1")
            brightened = _apply_rgb(img, lambda ch: ch.point(lambda x: _clamp(x + sh*50)))
            img = Image.composite(brightened, img, shmask)

        return img

    # ---- 颗粒噪点 ----
    def _grain(self, img, g: Grain, m: float):
        amt = g.amount * m
        if amt <= 0:
            return img

        w, h = img.size
        # 生成噪点图层
        sf = max(0.3, g.size)
        gw, gh = max(1, int(w/sf)), max(1, int(h/sf))
        noise_img = Image.new("L", (gw, gh))
        noise_px = noise_img.load()
        for y in range(gh):
            for x in range(gw):
                noise_px[x, y] = _clamp(128 + random.gauss(0, amt * 50))

        # 放大噪点
        noise_img = noise_img.resize((w, h), Image.BILINEAR)

        # 如果黑白噪点: 灰度 → RGB
        if g.color_noise:
            noise_rgb = Image.merge("RGB", (
                noise_img, noise_img, noise_img
            ))
        else:
            noise_rgb = Image.merge("RGB", (
                ImageChops.offset(noise_img, random.randint(0, 5), 0),
                noise_img,
                ImageChops.offset(noise_img, random.randint(-5, 0), 0),
            ))

        # 混合噪点
        noise_rgb = Image.blend(
            Image.new("RGB", (w, h), (128, 128, 128)),
            noise_rgb, 0.6
        )

        # 色差 (通道偏移)
        cs = g.chroma_shift * m
        if cs > 0:
            shift = max(1, int(cs * 8))
            r, g_ch, b = img.split()
            # R右移, B左移
            r = ImageChops.offset(r, shift, 0)
            b = ImageChops.offset(b, -shift, 0)
            img = Image.merge("RGB", (r, g_ch, b))

        return Image.blend(img, noise_rgb, 0.3)

    # ---- 柔光Bloom ----
    def _bloom(self, img, b: Bloom, m: float):
        bi = b.intensity * m
        sf = b.softness * m
        ra = b.radial * m

        if bi <= 0 and sf <= 0 and ra <= 0:
            return img

        w, h = img.size

        # Bloom: 提取高光 → 高斯模糊 → 与原图叠加
        if bi > 0:
            gray = img.convert("L")
            threshold = b.threshold
            mask = gray.point(lambda x: 255 if x > threshold else 0)
            highlights = Image.composite(img, Image.new("RGB", (w, h), (0,0,0)), mask.convert("1"))
            blur_rad = int(15 * bi)
            if blur_rad > 0:
                highlights = highlights.filter(ImageFilter.GaussianBlur(radius=blur_rad))
                img = Image.blend(img, highlights, bi * 0.3)

        # 镜头柔焦
        if sf > 0:
            blur_rad = max(0.5, 3 * sf)
            blurred = img.filter(ImageFilter.GaussianBlur(radius=blur_rad))
            img = Image.blend(img, blurred, sf * 0.3)

        # 径向模糊 (逐角度旋转叠加)
        if ra > 0:
            acc = Image.new("RGB", (w, h), (0,0,0))
            cx, cy = w//2, h//2
            for i in range(1, 7):
                ang = i * ra * 2
                rot = img.rotate(ang, center=(cx, cy))
                acc = Image.blend(acc, rot, 0.15)
            img = Image.blend(img, acc, ra * 0.3)

        return img

    # ---- 扭曲特效 ----
    def _distortion(self, img, d: Distortion, m: float):
        w, h = img.size
        px = img.load()

        # 扫描线
        sc = d.scanlines * m
        if sc > 0:
            darken = int(sc * 100)
            for y in range(1, h, 2):
                for x in range(w):
                    r, g, b = px[x, y]
                    px[x, y] = (_clamp(r-darken), _clamp(g-darken), _clamp(b-darken))

        # 暗角
        vi = d.vignette * m
        if vi > 0:
            cx, cy = w/2, h/2
            max_dist = math.sqrt(cx*cx + cy*cy)
            for y in range(h):
                for x in range(w):
                    dist = math.sqrt((x-cx)**2 + (y-cy)**2) / max_dist
                    factor = 1.0 - vi * 0.8 * dist * dist
                    factor = max(0, min(1, factor))
                    r, g, b = px[x, y]
                    px[x, y] = (_clamp(r*factor), _clamp(g*factor), _clamp(b*factor))

        # 像素化
        px_size = d.pixelate
        if px_size > 0:
            small_w, small_h = w // px_size, h // px_size
            small = img.resize((small_w, small_h), Image.NEAREST)
            img = small.resize((w, h), Image.NEAREST)
            px = img.load()

        # 故障效果
        gl = d.glitch * m
        if gl > 0:
            n_lines = int(gl * 30)
            for _ in range(n_lines):
                yp = random.randint(0, h-2)
                lh = random.randint(1, max(2, int(gl * 15)))
                sx = random.randint(-int(gl * 60), int(gl * 60))
                if yp + lh < h:
                    # 裁剪并偏移一行
                    strip = img.crop((0, yp, w, yp+lh))
                    strip = ImageChops.offset(strip, sx, 0)
                    img.paste(strip, (0, yp))

        # 漩涡
        sw = d.swirl * m
        if sw > 0:
            cx, cy = w//2, h//2
            rot = img.rotate(sw * 10, center=(cx, cy))
            img = Image.blend(img, rot, sw * 0.5)

        return img

    # ---- 主管线 ----
    def process(self, input_path: str, style_id: str, output_path: str = None) -> str:
        if style_id not in PRESETS:
            raise ValueError(f"Unknown style: '{style_id}'. Available: {list(PRESETS)}")
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Image not found: {input_path}")

        p = PRESETS[style_id]
        m = self.mult
        logger.info(f"Processing '{input_path}' → '{style_id}' [{self.intensity}]")

        img = Image.open(input_path).convert("RGB")
        ow, oh = img.size
        max_dim = 2048
        if max(ow, oh) > max_dim:
            ratio = max_dim / max(ow, oh)
            img = img.resize((int(ow*ratio), int(oh*ratio)), Image.LANCZOS)

        img = self._color_grade(img, p.color, m)
        img = self._exposure(img, p.exposure, m)
        img = self._grain(img, p.grain, m)
        img = self._bloom(img, p.bloom, m)
        img = self._distortion(img, p.distortion, m)

        if output_path is None:
            base, ext = os.path.splitext(input_path)
            output_path = f"{base}_{style_id}_{self.intensity}{ext}"
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        img.save(output_path, quality=95)
        logger.info(f"Saved: {output_path}")
        return output_path


def process_image(input_path: str, style_id: str, intensity: str = "standard",
                  output_path: str = None) -> str:
    return ImageProcessor(intensity).process(input_path, style_id, output_path)

def list_styles() -> list:
    return [{"id": k, "name": v.name} for k, v in PRESETS.items()]
