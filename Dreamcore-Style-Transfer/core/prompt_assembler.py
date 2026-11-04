"""
============================================================
提示词组装引擎 (Prompt Assembly Engine)
============================================================
层级: 核心处理逻辑层 (Layer 3 — Logic & Orchestration)
功能:
  1. 将图片描述 + 风格配方 → 组装为完整提示词
  2. 支持多模型输出 (Midjourney / SD / DALL-E 3)
  3. 支持强度控制和自定义调整
  4. 包含负面提示词自动生成

架构位置: Skill Pipeline Stage 5 — Prompt Assembly
============================================================
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

class TargetModel(Enum):
    MIDJOURNEY = "midjourney"
    STABLE_DIFFUSION = "stable_diffusion"
    DALLE3 = "dall-e-3"


class Intensity(Enum):
    MILD = "mild"
    STANDARD = "standard"
    EXTREME = "extreme"


@dataclass
class StyleRecipe:
    """风格配方（从 style_recipes.yaml 加载）"""
    style_id: str
    style_name_zh: str
    style_name_en: str
    core_keywords: str
    visual_features: list[str] = field(default_factory=list)
    typical_scenes: list[str] = field(default_factory=list)
    mood_atmosphere: list[str] = field(default_factory=list)
    era_params: list[str] = field(default_factory=list)
    color_palette: dict = field(default_factory=dict)
    midjourney_params: dict = field(default_factory=dict)
    sd_params: dict = field(default_factory=dict)
    intensity_presets: dict = field(default_factory=dict)


@dataclass
class AssembledPrompt:
    """组装完成的提示词"""
    # 正向提示词
    positive_prompt: str = ""

    # 各模型专用格式
    midjourney_prompt: str = ""
    midjourney_params: str = ""

    sd_positive: str = ""
    sd_negative: str = ""
    sd_params: dict = field(default_factory=dict)

    dalle_prompt: str = ""

    # 元数据
    style_name: str = ""
    intensity: str = "standard"
    word_count: int = 0
    tokens_estimated: int = 0


# ============================================================
# 提示词组装器
# ============================================================

class PromptAssembler:
    """
    提示词组装引擎

    核心算法：
      1. 接收图片分析片段 + 风格配方
      2. 按结构分层组装：[主体] + [场景] + [风格核心] + [视觉特征] + [情绪] + [时代] + [画质]
      3. 根据强度参数增加/减少风格关键词密度
      4. 针对不同模型格式化输出
    """

    # === 提示词结构模板 ===
    PROMPT_STRUCTURE = {
        "midjourney": [
            "{image_description}",        # 图片内容
            "{core_keywords}",            # 风格核心
            "{visual_features}",          # 视觉特征
            "{mood_atmosphere}",          # 情绪氛围
            "{era_params}",               # 时代参数
            "{quality_tags}",             # 画质标签
        ],
        "stable_diffusion": [
            "{image_description}",
            "{core_keywords}",
            "{visual_features}",
            "{typical_scene}",
            "{mood_atmosphere}",
            "{era_params}",
            "{quality_tags}",
        ],
        "dall-e-3": [
            # DALL-E 3 使用自然语言描述，不需要逗号分隔的关键词
            "Transform this image into a {core_keywords} style: {image_description}. "
            "The result should have {visual_features}, with a mood of {mood_atmosphere}. "
            "Era: {era_params}.",
        ],
    }

    # === 强度调整因子 ===
    INTENSITY_ADJUSTMENTS = {
        Intensity.MILD: {
            "keyword_multiplier": 0.6,       # 风格关键词密度降低
            "extra_adjectives": [],           # 不额外添加修饰
            "negative_intensity": "normal",
        },
        Intensity.STANDARD: {
            "keyword_multiplier": 1.0,
            "extra_adjectives": [],
            "negative_intensity": "normal",
        },
        Intensity.EXTREME: {
            "keyword_multiplier": 1.5,
            "extra_adjectives": ["intense", "heavy", "extreme", "overwhelming"],
            "negative_intensity": "strong",
        },
    }

    @staticmethod
    def assemble(
        image_fragment: str,
        recipe: StyleRecipe,
        model: TargetModel = TargetModel.MIDJOURNEY,
        intensity: Intensity = Intensity.STANDARD,
        custom_additions: Optional[str] = None,
    ) -> AssembledPrompt:
        """
        核心组装方法

        Args:
            image_fragment: 图片分析后的英文描述片段
            recipe: 风格配方对象
            model: 目标生成模型
            intensity: 风格强度
            custom_additions: 用户自定义添加的关键词

        Returns:
            AssembledPrompt 完整组装结果
        """
        # === Step 1: 获取强度配置 ===
        intensity_config = PromptAssembler.INTENSITY_ADJUSTMENTS.get(
            intensity, PromptAssembler.INTENSITY_ADJUSTMENTS[Intensity.STANDARD]
        )

        # === Step 2: 构建各部分变量 ===
        # 视觉特征：根据强度调整数量
        visual_count = max(1, int(len(recipe.visual_features) * intensity_config["keyword_multiplier"]))
        visual_features_str = ", ".join(recipe.visual_features[:visual_count])

        # 情绪氛围
        mood_str = ", ".join(recipe.mood_atmosphere[:2])

        # 时代参数
        era_str = ", ".join(recipe.era_params[:2])

        # 额外形容词（极端强度时添加）
        if intensity_config["extra_adjectives"]:
            extra = " ".join(intensity_config["extra_adjectives"])
            visual_features_str = f"{extra}, {visual_features_str}"

        # 典型场景（选一个最匹配的）
        typical_scene = recipe.typical_scenes[0] if recipe.typical_scenes else ""

        # 画质标签
        quality_tags = "highly detailed, atmospheric"

        # === Step 3: 按模型格式组装 ===
        prompt = AssembledPrompt()
        prompt.style_name = recipe.style_name_zh
        prompt.intensity = intensity.value

        # -- Midjourney --
        mj_positive = PromptAssembler._fill_template(
            PromptAssembler.PROMPT_STRUCTURE["midjourney"],
            image_fragment=image_fragment,
            core_keywords=recipe.core_keywords,
            visual_features=visual_features_str,
            mood_atmosphere=mood_str,
            era_params=era_str,
            quality_tags=quality_tags,
            typical_scene=typical_scene,
        )
        # 添加自定义内容
        if custom_additions:
            mj_positive += f", {custom_additions}"

        mj_params = recipe.midjourney_params
        mj_params_str = PromptAssembler._format_mj_params(mj_params)

        prompt.midjourney_prompt = mj_positive
        prompt.midjourney_params = mj_params_str
        prompt.positive_prompt = mj_positive  # 默认正向提示词为 MJ 版本

        # -- Stable Diffusion --
        sd_positive = PromptAssembler._fill_template(
            PromptAssembler.PROMPT_STRUCTURE["stable_diffusion"],
            image_fragment=image_fragment,
            core_keywords=recipe.core_keywords,
            visual_features=visual_features_str,
            mood_atmosphere=mood_str,
            era_params=era_str,
            quality_tags=quality_tags,
            typical_scene=typical_scene,
        )
        if custom_additions:
            sd_positive += f", {custom_additions}"

        sd_negative = recipe.sd_params.get("negative_prompt", "")
        sd_params = {
            "steps": recipe.sd_params.get("steps", 30),
            "cfg_scale": recipe.sd_params.get("cfg_scale", 7.5),
        }

        # 极端强度时增强负面提示词
        if intensity == Intensity.EXTREME:
            sd_negative += ", clean, normal, realistic, traditional, conventional"

        prompt.sd_positive = sd_positive
        prompt.sd_negative = sd_negative
        prompt.sd_params = sd_params

        # -- DALL-E 3 --
        dalle_prompt = PromptAssembler._fill_template(
            PromptAssembler.PROMPT_STRUCTURE["dall-e-3"],
            image_fragment=image_fragment,
            core_keywords=recipe.core_keywords,
            visual_features=visual_features_str,
            mood_atmosphere=mood_str,
            era_params=era_str,
        )
        prompt.dalle_prompt = dalle_prompt

        # === Step 4: 统计 ===
        prompt.word_count = len(prompt.positive_prompt.split())
        prompt.tokens_estimated = prompt.word_count * 1.3  # 粗略估算

        return prompt

    @staticmethod
    def assemble_all_models(
        image_fragment: str,
        recipe: StyleRecipe,
        intensity: Intensity = Intensity.STANDARD,
        custom_additions: Optional[str] = None,
    ) -> AssembledPrompt:
        """
        为所有支持的模型生成提示词
        实际调用 assemble() 默认格式（包含所有模型）
        """
        return PromptAssembler.assemble(
            image_fragment=image_fragment,
            recipe=recipe,
            intensity=intensity,
            custom_additions=custom_additions,
        )

    @staticmethod
    def tweak_existing(
        existing: AssembledPrompt,
        tweak_type: str,
        tweak_value: str,
    ) -> AssembledPrompt:
        """
        对已有提示词进行微调（用于用户的"再柔和一点"等指令）

        Args:
            existing: 已有的组装结果
            tweak_type: 调整类型 (softer / stronger / warmer / colder / blurrier / sharper)
            tweak_value: 调整的具体描述
        """
        modifications = {
            "softer": ("soft focus, gentle atmosphere, mild dreamlike, reduced contrast",
                       ""),
            "stronger": ("intense, heavy atmosphere, deep immersion, overwhelming nostalgia",
                         "clean, normal, realistic"),
            "warmer": ("warm tones, golden light, cozy atmosphere",
                       "cold lighting, blue tones"),
            "colder": ("cold tones, blue lighting, detached atmosphere",
                       "warm lighting, golden hour"),
            "blurrier": ("soft focus, heavy blur, dreamy haze, out of focus",
                         "sharp focus, crystal clear"),
            "sharper": ("sharp focus, clear details, defined edges",
                         "blurry, soft focus, hazy"),
        }

        mod = modifications.get(tweak_type, ("", ""))

        existing.positive_prompt += f", {mod[0]}"
        existing.midjourney_prompt += f", {mod[0]}"
        existing.sd_positive += f", {mod[0]}"
        existing.sd_negative += f", {mod[1]}"

        return existing

    # === 内部辅助方法 ===

    @staticmethod
    def _fill_template(structure: list[str], **kwargs) -> str:
        """使用变量填充模板，跳过空值"""
        parts = []
        for item in structure:
            try:
                filled = item.format(**kwargs)
                # 跳过空片段
                if filled and filled.strip():
                    parts.append(filled)
            except KeyError:
                continue
        return ", ".join(parts)

    @staticmethod
    def _format_mj_params(params: dict) -> str:
        """格式化 Midjourney 参数"""
        parts = []
        if "ar" in params:
            parts.append(f"--ar {params['ar']}")
        if "stylize" in params:
            parts.append(f"--stylize {params['stylize']}")
        if "chaos" in params:
            parts.append(f"--chaos {params['chaos']}")
        if "negative" in params and params["negative"]:
            no_list = ", ".join(params["negative"])
            parts.append(f"--no {no_list}")
        return " ".join(parts)
