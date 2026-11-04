# 🎨 Dreamcore Style Transfer — 梦核风格图像处理器

> 5 层闭环 AI Skill 架构 | 10 种"核"风格 | 纯 Pillow 像素级渲染

对任意图片应用"核"风格（梦核、怪核、后室、阈限空间等）的**真实图像处理**——不只是生成提示词，而是直接对图片进行色彩分级、曝光调整、颗粒噪点、柔光 Bloom、扭曲特效等像素级变换。

---

## 快速开始

### 方式一：桌面 GUI 应用（推荐）

```bash
# 安装依赖
pip install Pillow

# 启动 GUI 应用
python app.py
```

暗色主题桌面界面，左侧图片预览（支持原图/结果切换），右侧风格卡片点选，Ctrl+Enter 一键处理。

### 方式二：命令行交互式

```bash
python run.py
```

终端交互菜单：输入图片 → 选风格编号 → 选强度 → 自动输出。

### 方式二：命令行一行代码

```bash
python -c "
from core.image_processor import process_image
process_image('your_photo.jpg', 'dreamcore', 'standard', 'output.jpg')
"
```

**输入** → `D:\your_photo.jpg`
**输出** → `./output/your_photo_dreamcore.jpg`

---

## 支持的风格
风格更改制作示例在examples中
| # | 风格 | 命令 | 视觉效果 |
|---|------|------|----------|
| 1 | 🌀 **经典梦核** | `dreamcore` | 过曝 + 柔光Bloom + 褪色 + 90s胶片颗粒 + 暗角 |
| 2 | 👁️ **怪核** | `weirdcore` | 高对比 + 色散 + 故障线条 + 彩色噪点 |
| 3 | 🚪 **阈限空间** | `liminal_space` | 去饱和 + 冷色调 + 空旷感 + 暗角 |
| 4 | 💔 **伤核** | `traumacore` | 粉色高光 + 褪色 + 柔焦 + 重暗角 |
| 5 | 🟨 **后室** | `backrooms` | 黄色荧光 + VHS扫描线 + 彩色噪点 + 暗角 |
| 6 | 🌈 **童年核** | `kidcore` | 极高饱和 + 提亮 + Vibrance增强 |
| 7 | 🏊 **池核** | `poolcore` | 水下蓝 + 偏青 + 蓝色高光染色 |
| 8 | 💾 **网核** | `webcore` | 像素化 + CRT扫描线 + 故障 + Y2K色偏 |
| 9 | 🌀 **催眠核** | `hypnocore` | 漩涡扭曲 + 径向模糊 + 迷幻过饱和 |
| 10 | 📺 **中式梦核** | `chinese_dreamcore` | 暖黄褪色 + CCD细颗粒 + 轻扫描线 + 暗角 |

### 三种强度

| 强度 | 参数 | 效果 |
|------|------|------|
| `mild` | 所有参数 ×0.5 | 若有若无的风格暗示 |
| `standard` | 默认 | 标准风格效果 |
| `extreme` | 所有参数 ×1.5 | 极致力度的风格渲染 |

---

## 5 层处理管线

每张图片经过以下 5 个阶段依次处理：

```
原图
  │
  ├─ Stage 1: 色彩分级 (Color Grade)
  │   色温偏移 · 色调偏移 · 饱和度 · Vibrance · 褪色混合
  │   高光染色 · 阴影染色 · 亮度 · 对比度
  │
  ├─ Stage 2: 曝光调整 (Exposure)
  │   EV补偿 · Gamma校正 · 高光压低 · 阴影提亮
  │
  ├─ Stage 3: 颗粒噪点 (Grain & Noise)
  │   黑白/彩色颗粒 · 粒度控制 · 通道偏移(色差)
  │
  ├─ Stage 4: 柔光Bloom (Bloom & Blur)
  │   高光提取 → 高斯模糊 → 叠加 · 镜头柔焦 · 径向模糊
  │
  ├─ Stage 5: 扭曲特效 (Distortion)
  │   扫描线 · 暗角 · 像素化 · 故障偏移 · 漩涡扭曲
  │
  ▼
 输出
```

---

## 实际效果验证

### R-C.jpg (1200×675) → 梦核

| | 原图 | 梦核 |
|------|------|------|
| 色调 | RGB(179, 163, 130) | RGB(186, 172, 151) |
| 变化 | — | R+7, G+9, B+21 → 过曝褪色暖调 |

### R-C (1).jpg (1440×1080) → 多风格对比

| 风格 | 色调 | R 通道变化 | 特征 |
|------|------|-----------|------|
| 原图 | RGB(93, 132, 155) | — | 蓝调原片 |
| 池核 | RGB(99, 121, 136) | R+6 | 水下蓝, 偏青 |
| 后室 | RGB(130, 138, 139) | **R+37** | 病态黄, VHS扫描线 |

---

## 项目结构

```
D:\Dreamcore-Style-Transfer\
│
├── README.md                            ← 本文件
├── SKILL.md                             ← Skill 主定义 (5层架构文档)
├── run.py                               ← 🚀 交互式启动脚本（推荐）
│
├── core/                                ← 核心引擎
│   ├── image_processor.py               ← 🎯 图像处理引擎 (纯Pillow, 400+行)
│   ├── image_analyzer.py                ← Vision 图片分析 (用于生成提示词)
│   ├── style_matcher.py                 ← 风格匹配与推荐
│   ├── prompt_assembler.py              ← 提示词组装 (MJ/SD/DALL-E)
│   └── output_composer.py               ← 多模态输出编排
│
├── memory/                              ← 记忆与状态层
│   ├── session_state.py                 ← 会话状态机 + 查询历史
│   ├── user_profile.py                  ← 长期用户画像
│   └── conversation_context.py          ← 指代消解 + 上下文管理
│
├── knowledge/
│   └── style_knowledge_base.md          ← RAG 知识库 (风格文化起源)
│
├── styles/
│   └── style_recipes.yaml               ← 10种风格完整配方 (参数化)
│
├── triggers/
│   └── intent_patterns.yaml             ← 意图识别模式库
│
├── schemas/
│   └── input_schema.yaml                ← 输入参数规范 + 校验规则
│
├── config/
│   └── skill_config.yaml                ← Skill 总配置
│
├── utils/
│   ├── validator.py                     ← 参数校验引擎
│   └── fallback.py                      ← 兜底降级 + 安抚话术
│
├── examples/                            ← 示例图片 (10种风格样张)
│   ├── 01_dreamcore.jpg
│   ├── 02_weirdcore.jpg
│   └── ...
│
└── output/                              ← 输出目录
    ├── test_dreamcore_standard.jpg
    ├── test_backrooms_mild.jpg
    └── ...
```

**20 个文件 | ~4,900 行 | 纯 Python + YAML + Markdown | 无重型依赖**

---

## Python API

```python
from core.image_processor import process_image, list_styles, ImageProcessor

# 快速处理
process_image("input.jpg", "dreamcore", "standard", "output.jpg")

# 细粒度控制
processor = ImageProcessor(intensity="extreme")
result = processor.process("input.jpg", "backrooms", "output.jpg")

# 自定义参数
from core.image_processor import ColorGrade, Exposure, Grain, Bloom, Distortion, StylePreset
custom = StylePreset("my_style", "自定义",
    color=ColorGrade(temperature=0.8, saturation=0.6, fade=0.3),
    exposure=Exposure(ev=0.5, gamma=0.9),
    grain=Grain(amount=0.4, size=1.2),
    bloom=Bloom(intensity=0.3, threshold=190),
    distortion=Distortion(vignette=0.35),
)

# 查看所有风格
styles = list_styles()
# [{"id": "dreamcore", "name": "经典梦核"}, ...]
```

---

## 设计原则

1. **真正的图像处理** — 不是生成文本提示词，而是对像素进行实际变换
2. **零重型依赖** — 仅需 Pillow，无 numpy/OpenCV/GPU 需求
3. **确定性输出** — 相同输入 + 相同参数 = 相同结果（种子固定）
4. **优雅降级** — 大图自动等比缩放，防止内存溢出
5. **5 层架构** — 触发 → 输入校验 → 核心逻辑 → 输出呈现 → 记忆状态

---

## 技术栈

- **图像处理**: Pillow (PIL) 12.3+
- **色彩科学**: 通道分离/合并, Gamma 校正, 感知亮度计算
- **特效**: 高斯模糊, 通道偏移(Chromatic Aberration), 像素化, 扫描线
- **架构**: 5-Layer Closed-Loop Microservice Pattern

---

## License

MIT
