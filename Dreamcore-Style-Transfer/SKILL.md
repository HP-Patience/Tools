---
name: dreamcore-style-transfer
description: >
  完整的5层架构AI Skill — 将用户上传的图片转换为10种"核"风格的AI绘画提示词。
  触发词包括"梦核"、"怪核"、"阈限空间"、"伤核"、"后室"、"童年核"、"池核"、
  "网核"、"催眠核"、"中式梦核"等。支持感知→推理→执行→反馈的完整闭环，
  包含会话状态管理、用户画像长期记忆、多模态输出、优雅降级等高级特性。
version: "2.0.0"
architecture: "5-Layer Closed-Loop Microservice"
layers:
  - "Layer 1: Trigger / Wake-up (唤醒层)"
  - "Layer 2: Input Schema (输入规范层)"
  - "Layer 3: Logic & Orchestration (核心逻辑层)"
  - "Layer 4: Output & Interaction (输出呈现层)"
  - "Layer 5: Memory & State (记忆持久化层)"
---

# 🎨 梦核风格转换器 v2.0

> **架构**: 5 层闭环微服务架构 | **支持风格**: 10 种 | **输出**: Midjourney / Stable Diffusion / DALL-E 3

---

## 系统架构概览

```
┌─────────────────────────────────────────────────────┐
│                   SKILL ORCHESTRATOR                 │
├─────────────────────────────────────────────────────┤
│  Layer 1: TRIGGER    │  intent_patterns.yaml        │
│  Layer 2: INPUT      │  input_schema.yaml           │
│  Layer 3: LOGIC      │  core/*.py                   │
│  Layer 4: OUTPUT     │  core/output_composer.py     │
│  Layer 5: MEMORY     │  memory/*.py                 │
├─────────────────────────────────────────────────────┤
│  KNOWLEDGE BASE      │  knowledge/*.md              │
│  UTILITIES           │  utils/*.py                  │
│  STYLE RECIPES       │  styles/*.yaml               │
└─────────────────────────────────────────────────────┘
```

---

## Layer 1: 触发机制 (Trigger / Wake-up)

### 1.1 意图识别矩阵

**当用户消息匹配以下任一模式时，激活本 Skill：**

| 优先级 | 意图类型 | 触发模式 | 示例 |
|--------|---------|---------|------|
| P1 | 风格转换 | `把这张图变成{style}风格` | "把这张图变成梦核风格" |
| P1 | 风格转换 | 直接说风格名 `{style}` | "梦核"、"怪核" |
| P2 | 风格询问 | `有哪些风格？` | "都有什么核风格？" |
| P3 | 风格推荐 | `{feeling}的有没有？` | "有没有温暖一点的风格？" |
| P4 | 结果微调 | `再{adj}一点` | "再柔和一点" |

### 1.2 上下文唤醒规则

| 用户输入 | 继承上下文 | 重置内容 | 行为 |
|---------|-----------|---------|------|
| "那{style}呢？" | 图片 | 风格 | 同图换风格 |
| "换一张图，还是{style}" | 风格 | 图片 | 换图同风格 |
| "再{adj}一点" | 全部 | - | 参数微调 |

### 1.3 歧义消解

- **"梦核"同时匹配 dreamcore 和 chinese_dreamcore** → 反问确认
- **未上传图片** → 主动索要：`"请上传一张图片"`
- **模糊意图** → 展示 10 种风格列表供选择

**参考实现**: [triggers/intent_patterns.yaml](triggers/intent_patterns.yaml)

---

## Layer 2: 输入规范 (Input Schema)

### 2.1 参数定义

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `image` | image | ✅ | - | 待转换的图片 (PNG/JPG/WEBP/GIF/BMP, ≤50MB) |
| `style` | enum | ✅ | - | 目标风格 (10种之一，支持中英文别名) |
| `intensity` | enum | ❌ | `standard` | 风格强度: mild / standard / extreme |
| `target_model` | enum | ❌ | `midjourney` | 目标工具: midjourney / stable_diffusion / dall-e-3 / all |
| `aspect_ratio` | string | ❌ | 风格默认 | 画面比例，如 16:9、4:3、1:1 |
| `language` | enum | ❌ | `english` | 提示词语言 |

### 2.2 槽位填充 (Slot Filling) 流程

```
用户输入 → 参数提取 → 缺参检测 → 友好追问 → 参数补全 → 校验通过
```

**缺参话术模板**:
- 缺图片: `"好的！请先上传一张图片 📷（支持 PNG/JPG/WEBP，最大 50MB）"`
- 缺风格: `"请选择您想要的风格：\n1. 梦核 2. 怪核 3. 阈限空间 ..."`
- 模糊风格: `"您说的「{input}」可能指：①经典梦核 ②中式梦核，请问是哪一个？"`

### 2.3 参数格式化

| 用户输入 | 标准化结果 |
|---------|-----------|
| "轻一点" / "柔和" / "淡一点" | `intensity=mild` |
| "拉满" / "极致" / "重度" | `intensity=extreme` |
| "MJ" / "sd" / "dalle" | `model=midjourney/stable_diffusion/dall-e-3` |
| "16比9" / "16:9" / "宽屏" | `aspect_ratio=16:9` |

**参考实现**: [schemas/input_schema.yaml](schemas/input_schema.yaml), [utils/validator.py](utils/validator.py)

---

## Layer 3: 核心处理逻辑 (Logic & Orchestration)

### 3.1 Pipeline 流水线

```
Stage 1: TRIGGER          intent_patterns.yaml      ~500ms
    ↓
Stage 2: INPUT VALIDATION  validator.py              ~1000ms
    ↓
Stage 3: IMAGE ANALYSIS    core/image_analyzer.py    ~8000ms
    ↓
Stage 4: STYLE MATCHING    core/style_matcher.py     ~2000ms
    ↓
Stage 5: PROMPT ASSEMBLY   core/prompt_assembler.py  ~3000ms
    ↓
Stage 6: OUTPUT COMPOSE    core/output_composer.py   ~2000ms
    ↓
Stage 7: MEMORY SYNC       memory/*.py               ~1000ms
```

### 3.2 Stage 3 — 图片分析 (Image Analysis)

**执行步骤：**

1. 将图片传给 Claude Vision 模型
2. 使用结构化分析 Prompt（见 `image_analyzer.py:ANALYSIS_PROMPT`）
3. 提取：
   - 主体：人物/建筑/物体的英文描述
   - 场景类型：indoor/outdoor/urban/nature/portrait/...
   - 颜色：dominant_colors, accent_colors, color_temperature
   - 光影：natural/artificial/fluorescent/dim/bright/...
   - 情绪基调：mood_keywords
   - 年代推测：90s/00s/contemporary/vintage
   - **prompt_fragment**：≤30 词的英文提示词片段（核心输出）

**Fallback 策略**: Vision API 不可用时 → 基于图片元数据的基础分析 → 降级到 Level 2

**关键 Prompt 原则**:
- 生成英文提示词，因为 AI 绘画工具对英文理解最好
- 描述人物时使用通用描述词，避免识别真实身份
- prompt_fragment 控制在 30 词以内

### 3.3 Stage 4 — 风格匹配 (Style Matching)

**匹配策略（按优先级）**:

1. **精确别名匹配** — 遍历所有风格的 aliases 列表
2. **模糊关键词匹配** — 对核心关键词、情绪标签加权打分
3. **情绪映射匹配** — 用户描述的感觉词映射到风格
4. **场景映射匹配** — 根据图片的 scene_type 推荐
5. **无法确定** — 展示候选列表，引导用户选择

**风格推荐逻辑**:
- 用户说"温暖怀旧的" → 推荐 dreamcore, kidcore, chinese_dreamcore
- 图片是 indoor + architecture → 推荐 liminal_space, backrooms
- 用户上次用了 weirdcore → 这轮优先展示相关风格

### 3.4 Stage 5 — 提示词组装 (Prompt Assembly)

**组装结构**:
```
[图片内容描述], [风格核心关键词], [视觉特征], [情绪氛围], [时代参数], [画质标签]
```

**强度控制**:
- `mild`: 风格关键词密度 ×0.6，减少修饰
- `standard`: 正常密度，标准配方
- `extreme`: 密度 ×1.5，额外添加 "intense, heavy, extreme, overwhelming"

**多模型适配**:
- **Midjourney**: 逗号分隔的关键词 + `--ar --stylize --chaos --no` 参数
- **Stable Diffusion**: 正向提示词 + 负面提示词 + steps/cfg_scale
- **DALL-E 3**: 自然语言描述的完整句子

### 3.6 兜底逻辑 (Fallback)

| 失败场景 | 降级行为 |
|---------|---------|
| Vision API 超时 | 降级到 Level 2：请用户手动描述图片 |
| Vision API 返回无效 | 降级到 Level 3：使用通用提示词模板 |
| 风格匹配置信度 < 0.5 | 展示候选列表 |
| 提示词生成为空 | 使用模板提示词兜底 |
| 用户画像保存失败 | 静默跳过，不影响核心功能 |

**参考实现**: [core/image_analyzer.py](core/image_analyzer.py), [core/style_matcher.py](core/style_matcher.py), [core/prompt_assembler.py](core/prompt_assembler.py), [utils/fallback.py](utils/fallback.py)

---

## Layer 4: 输出与交互 (Output & Interaction)

### 4.1 输出模式

| 模式 | 触发方式 | 内容 |
|------|---------|------|
| **完整模式** (默认) | 正常触发 | 图片分析表格 + 风格配方摘要 + 多模型提示词 + 使用建议 + 快捷操作 |
| **极简模式** | 用户说"只要提示词" | 仅输出 Midjourney/SD 提示词 |
| **对比模式** | 用户说"对比几种风格" | 多风格横向对比表格 |
| **卡片模式** | 自动检测 UI 支持 | 结构化 JSON 卡片（含按钮） |

### 4.2 交互组件

每次完整输出后附带快捷追问按钮：

```
🔄 换一种风格    🔧 再强烈一点    📋 仅看提示词    🌟 对比3种风格    ❓ 解释这个风格
```

### 4.3 标准输出格式示例

```
## 🎨 梦核风格转换结果 — 经典梦核 (Dreamcore)

### 📷 图片分析
| 维度 | 内容 |
|------|------|
| 主体 | a young woman in school uniform |
| 场景 | vintage classroom with wooden desks |
| 地点类型 | classroom |
| 主色调 | warm yellow, deep brown, cream white |
| 光影 | natural light from windows |
| 情绪基调 | quiet, contemplative, nostalgic |

### 🧪 风格配方
> **核心**: nostalgic surreal dreamscape
> **视觉**: soft overexposed lighting, hazy atmosphere, high grain, vintage film quality
> **情绪**: wistful, familiar yet strange, comforting yet eerie
> **时代**: 90s film stock, retro photography, analog camera

### 🖼️ 最终提示词

#### Midjourney
a young woman in school uniform, vintage classroom with wooden desks, dreamcore aesthetic, soft overexposed lighting, hazy atmosphere, high grain, nostalgic feel, empty liminal space, vintage 90s film stock, highly detailed, atmospheric --ar 4:3 --stylize 750 --no people, modern, busy, realistic

#### Stable Diffusion
**正向**: a young woman in school uniform, vintage classroom with wooden desks, dreamcore aesthetic, soft overexposed lighting, hazy atmosphere, high grain, nostalgic feel, empty liminal space, vintage 90s film stock

**负面**: modern architecture, smartphones, realistic, sharp, clean, people, busy, digital art, 3d render

### 💡 使用建议
1. 建议在 Midjourney 中使用 --stylize 参数控制风格化程度
2. 如果结果不够「核」，可以尝试增加 intensity 到「强烈」
3. 建议配合 --ar 4:3 使用，模拟复古胶片的宽高比
4. 如生成出不需要的元素，请使用负面提示词排除

### 🔄 快捷操作
- **换一种风格**: "帮我换一种风格"
- **调整强度**: "风格再强烈一点 / 再柔和一点"
- **对比风格**: "对比一下这个场景用其他风格的效果"
- **仅看提示词**: "只要提示词，简化输出"

---
*风格强度: standard | 词数: 62 | Dreamcore Style Transfer v2.0*
```

**参考实现**: [core/output_composer.py](core/output_composer.py)

---

## Layer 5: 记忆与状态 (Memory & State)

### 5.1 三层记忆架构

```
┌──────────────────────────────────────────┐
│ Layer 3: 长期记忆 (User Profile)         │
│ 文件: memory/user_profile.py              │
│ 存储: D:/Dreamcore-skills/memory/data/   │
│ 内容: 用户偏好、使用统计、等级成就       │
│ 生命周期: 跨会话持久化                   │
├──────────────────────────────────────────┤
│ Layer 2: 会话状态 (Session State)        │
│ 文件: memory/session_state.py            │
│ 存储: 内存 (当前会话)                    │
│ 内容: 状态机、上下文、查询历史           │
│ 生命周期: 单次会话 (30分钟过期)          │
├──────────────────────────────────────────┤
│ Layer 1: 对话上下文 (Conversation)       │
│ 文件: memory/conversation_context.py     │
│ 存储: 内存 (最近N轮)                     │
│ 内容: 指代消解、话题追踪                 │
│ 生命周期: 最近50轮对话                   │
└──────────────────────────────────────────┘
```

### 5.2 状态机 (State Machine)

```
IDLE → AWAITING_IMAGE → IMAGE_RECEIVED → ANALYZING → ANALYZED
  → AWAITING_STYLE → STYLE_SELECTED → MATCHING_STYLE
  → ASSEMBLING_PROMPT → PROMPT_GENERATED → AWAITING_TWEAK
  → (循环: 微调 → 重新组装) or (回退: 换风格)
  → IDLE
```

### 5.3 跨轮对话示例

```
Turn 1: 用户: "把这张教室图变成梦核"
        Skill: [分析 → 匹配 → 生成梦核提示词]
        Memory: image=classroom.jpg, style=dreamcore

Turn 2: 用户: "那怪核呢？"
        Context: 检测省略模式 → 继承 image=classroom.jpg
        Skill: [跳过分析 → 切换风格为 weirdcore → 重新生成]
        Memory: style=weirdcore (更新)

Turn 3: 用户: "再柔和一点"
        Context: 检测强度调整 → 继承 image + style
        Skill: [调整 intensity → mild → 重新组装]
        Memory: intensity=mild (更新)

Turn 4: 用户: "换张图，公园的"
        Context: 检测换图 → 继承 style=weirdcore + intensity=mild
        Skill: [新图分析 → 使用已有风格参数 → 生成]
```

### 5.4 用户画像示例

```json
{
  "user_id": "user_abc",
  "preferences": {
    "favorite_style": "dreamcore",
    "style_usage_count": {"dreamcore": 15, "weirdcore": 8},
    "default_intensity": "standard",
    "default_model": "midjourney"
  },
  "total_conversions": 32,
  "last_style_used": "dreamcore",
  "top_scenes": ["classroom", "urban street"],
  "level": 1
}
```

**参考实现**: [memory/session_state.py](memory/session_state.py), [memory/user_profile.py](memory/user_profile.py), [memory/conversation_context.py](memory/conversation_context.py)

---

## 风格快速参考

| # | 风格 ID | 中文名 | 核心关键词 | 情绪 | Midjourney 推荐参数 |
|---|---------|--------|-----------|------|-------------------|
| 1 | `dreamcore` | 经典梦核 | nostalgic surreal | 怀念又陌生 | `--ar 4:3 --no modern,people` |
| 2 | `weirdcore` | 怪核 | unsettling chaotic | 焦虑不安 | `--ar 1:1 --no realistic,sharp` |
| 3 | `liminal_space` | 阈限空间 | transitional empty | 孤独停滞 | `--ar 16:9 --no people,daylight` |
| 4 | `traumacore` | 伤核 | trauma fragile | 忧郁脆弱 | `--ar 3:2 --no happy,realistic` |
| 5 | `backrooms` | 后室 | infinite trapped | 恐惧被困 | `--ar 4:3 --no windows,people` |
| 6 | `kidcore` | 童年核 | childhood saturated | 苦乐参半 | `--ar 1:1 --no dark,realistic` |
| 7 | `poolcore` | 池核 | aquatic tiles | 宁静诡异 | `--ar 16:9 --no people,ocean` |
| 8 | `webcore` | 网核 | early internet | 数码怀旧 | `--ar 4:3 --no modern,realistic` |
| 9 | `hypnocore` | 催眠核 | hypnotic psychedelic | 恍惚迷失 | `--ar 1:1 --no realistic,static` |
| 10 | `chinese_dreamcore` | 中式梦核 | Chinese nostalgia | 乡愁怀旧 | `--ar 4:3 --no modern,western` |

**完整配方**: [styles/style_recipes.yaml](styles/style_recipes.yaml)

---

## 异常处理清单

| 异常场景 | 检测条件 | 响应策略 |
|---------|---------|---------|
| 无图片 | `image == null` | 反问索要图片 |
| 图片格式不支持 | 扩展名不在白名单 | 提示支持的格式 |
| 图片过大 | > 50MB | 提示压缩后重试 |
| 风格不明确 | 匹配置信度 < 0.5 | 展示候选列表 |
| 风格歧义 | 匹配到多个 | 反问确认 |
| Vision API 超时 | > 15s 无响应 | 降级 Level 2 |
| 提示词为空 | 组装结果空 | 使用模板兜底 |
| 用户画像存储失败 | 文件写入异常 | 静默跳过 |
| 会话过期 | > 30min 无操作 | 提示 + 重置上下文 |
| 请求频率过高 | > 10次/分钟 | 提示稍后重试 |

---

## 文件结构索引

```
D:\Dreamcore-skills\
├── SKILL.md                           ← 本文件（主入口）
├── config\
│   └── skill_config.yaml              ← Skill 总配置
├── triggers\
│   └── intent_patterns.yaml           ← L1: 意图识别模式库
├── schemas\
│   └── input_schema.yaml              ← L2: 输入参数规范
├── styles\
│   └── style_recipes.yaml             ← 10种风格完整配方
├── core\
│   ├── image_analyzer.py              ← L3: 图片分析引擎
│   ├── prompt_assembler.py            ← L3: 提示词组装引擎
│   ├── style_matcher.py               ← L3: 风格匹配推荐
│   └── output_composer.py             ← L4: 多模态输出编排
├── memory\
│   ├── session_state.py               ← L5: 会话状态管理
│   ├── user_profile.py                ← L5: 长期用户画像
│   └── conversation_context.py        ← L5: 对话上下文
├── knowledge\
│   └── style_knowledge_base.md        ← RAG 知识库
└── utils\
    ├── validator.py                   ← 参数校验
    └── fallback.py                    ← 兜底降级
```

---

## 执行清单 (每次用户请求时)

当用户触发了本 Skill 后，按以下步骤执行：

- [ ] **L1**: 识别意图类型（转换/询问/推荐/微调）
- [ ] **L1**: 检测上下文继承（指代消解）
- [ ] **L2**: 提取并校验参数，缺参时槽位填充
- [ ] **L3**: 调用 Vision 模型分析图片（如已分析且图片未变则跳过）
- [ ] **L3**: 匹配目标风格，置信度不足时展示候选
- [ ] **L3**: 组装多模型提示词
- [ ] **L4**: 选择合适的输出模式，生成最终响应
- [ ] **L5**: 更新会话状态、记录查询历史
- [ ] **L5**: 更新用户画像（风格使用计数等）
- [ ] **异常**: 任何步骤失败时触发兜底逻辑
