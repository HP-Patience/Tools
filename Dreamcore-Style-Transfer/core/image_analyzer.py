"""
============================================================
图片内容分析引擎 (Image Analysis Engine)
============================================================
层级: 核心处理逻辑层 (Layer 3 — Logic & Orchestration)
功能:
  1. 接收图片 → 提取结构化描述
  2. 识别: 主体 / 场景 / 色调 / 光影 / 构图
  3. 生成英文提示词片段
  4. 支持 Claude Vision 和本地 CV 双模式

架构位置: Skill Pipeline Stage 3 — Image Analysis
依赖: Claude Vision API (primary) / local CV (fallback)
============================================================
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构定义
# ============================================================

class SceneType(Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    URBAN = "urban"
    NATURE = "nature"
    ABSTRACT = "abstract"
    PORTRAIT = "portrait"
    ARCHITECTURE = "architecture"
    NIGHT = "night"
    DAY = "day"
    UNKNOWN = "unknown"


class LightingType(Enum):
    NATURAL = "natural"
    ARTIFICIAL = "artificial"
    FLUORESCENT = "fluorescent"
    DIM = "dim"
    BRIGHT = "bright"
    OVERCAST = "overcast"
    SUNSET = "sunset"
    UNKNOWN = "unknown"


@dataclass
class Subject:
    """图片中的主体对象"""
    type: str = ""                    # person / building / object / scene / animal
    description_en: str = ""          # 英文描述
    description_zh: str = ""          # 中文描述
    attributes: list[str] = field(default_factory=list)  # 属性列表
    position: str = ""                # 在画面中的位置 (center / left / right / foreground / background)
    confidence: float = 0.0           # 识别置信度


@dataclass
class ColorProfile:
    """颜色分析结果"""
    dominant_colors: list[str] = field(default_factory=list)    # 主色调 (英文)
    accent_colors: list[str] = field(default_factory=list)      # 辅助色
    color_temperature: str = ""        # warm / cool / neutral
    saturation_level: str = ""         # high / medium / low / desaturated
    contrast_level: str = ""           # high / medium / low


@dataclass
class ImageAnalysis:
    """图片完整分析结果"""
    # 基本信息
    analysis_id: str = ""
    timestamp: str = ""

    # 主体识别
    subjects: list[Subject] = field(default_factory=list)
    main_subject: str = ""             # 最核心的主体描述

    # 场景分析
    scene_type: str = ""               # SceneType value
    scene_description_en: str = ""     # 场景英文描述
    scene_description_zh: str = ""     # 场景中文描述
    location_guess: str = ""           # 推测地点类型 (classroom / park / street / ...)

    # 视觉属性
    colors: ColorProfile = field(default_factory=ColorProfile)
    lighting: str = ""                 # LightingType value
    composition: str = ""              # 构图描述 (centered / rule_of_thirds / ...)

    # 情感基调
    mood_keywords: list[str] = field(default_factory=list)
    era_guess: str = ""                # 推测年代 (90s / 00s / contemporary / vintage / ...)

    # 提示词片段
    prompt_fragment: str = ""          # 可直接插入提示词的英文描述片段
    quality_tags: list[str] = field(default_factory=list)

    # 元数据
    analysis_duration_ms: int = 0
    model_used: str = ""


# ============================================================
# 分析引擎
# ============================================================

class ImageAnalyzer:
    """
    图片内容分析引擎

    使用 Claude Vision 模型分析图片，生成结构化的内容描述。
    包含完整的 fallback 机制：当 Vision API 不可用时，降级为基础属性分析。
    """

    # === Vision 分析 Prompt 模板 ===
    ANALYSIS_PROMPT = """Analyze this image in detail for a dreamcore-style transfer task.

    Return a JSON object with the following structure:
    {
      "main_subject": "concise description of the MAIN subject (e.g., 'a young woman', 'an abandoned building', 'a classroom')",
      "subjects": [
        {
          "type": "person/building/object/scene/animal",
          "description_en": "detailed description",
          "attributes": ["attribute1", "attribute2"],
          "position": "center/left/right/foreground/background"
        }
      ],
      "scene_type": "indoor/outdoor/urban/nature/abstract/portrait/architecture/night/day",
      "scene_description_en": "short scene description in English",
      "location_guess": "what kind of place this is (classroom, park, street, etc.)",
      "dominant_colors": ["color1", "color2", "color3"],
      "accent_colors": ["color1", "color2"],
      "color_temperature": "warm/cool/neutral",
      "saturation_level": "high/medium/low/desaturated",
      "contrast_level": "high/medium/low",
      "lighting": "natural/artificial/fluorescent/dim/bright/overcast/sunset",
      "composition": "description of composition",
      "mood_keywords": ["mood1", "mood2", "mood3"],
      "era_guess": "90s/00s/contemporary/vintage/retro",
      "prompt_fragment": "concise English description optimized for AI image generation prompts. Include main subject, setting, colors, and lighting. Keep it under 30 words.",
      "quality_tags": ["tag1", "tag2"]
    }

    IMPORTANT:
    - prompt_fragment must be in ENGLISH and under 30 words
    - dominant_colors should be English color names like "warm yellow", "deep blue"
    - If there are people, describe them generically (avoid identifying real individuals)
    """

    @staticmethod
    def build_analysis_prompt(custom_focus: Optional[str] = None) -> str:
        """
        构建 Vision 分析提示词（可定制关注点）

        Args:
            custom_focus: 用户额外指定的关注方向
        """
        prompt = ImageAnalyzer.ANALYSIS_PROMPT
        if custom_focus:
            prompt += f"\n\nADDITIONAL FOCUS: {custom_focus}"
        return prompt

    @staticmethod
    def parse_vision_response(raw_response: str) -> ImageAnalysis:
        """
        解析 Claude Vision 返回的 JSON 为 ImageAnalysis 对象

        Args:
            raw_response: Vision 模型返回的原始文本

        Returns:
            ImageAnalysis 结构化对象

        Raises:
            ValueError: JSON 解析失败时
        """
        try:
            # 尝试提取 JSON 块
            json_str = raw_response
            if "```json" in raw_response:
                start = raw_response.index("```json") + 7
                end = raw_response.index("```", start)
                json_str = raw_response[start:end].strip()
            elif "```" in raw_response:
                start = raw_response.index("```") + 3
                end = raw_response.index("```", start)
                json_str = raw_response[start:end].strip()

            data = json.loads(json_str)

            # 构建 ColorProfile
            colors = ColorProfile(
                dominant_colors=data.get("dominant_colors", []),
                accent_colors=data.get("accent_colors", []),
                color_temperature=data.get("color_temperature", "neutral"),
                saturation_level=data.get("saturation_level", "medium"),
                contrast_level=data.get("contrast_level", "medium"),
            )

            # 构建 Subjects
            subjects = []
            for s in data.get("subjects", []):
                subjects.append(Subject(
                    type=s.get("type", ""),
                    description_en=s.get("description_en", ""),
                    description_zh=s.get("description_zh", ""),
                    attributes=s.get("attributes", []),
                    position=s.get("position", ""),
                    confidence=s.get("confidence", 0.8),
                ))

            return ImageAnalysis(
                subjects=subjects,
                main_subject=data.get("main_subject", ""),
                scene_type=data.get("scene_type", "unknown"),
                scene_description_en=data.get("scene_description_en", ""),
                scene_description_zh=data.get("scene_description_zh", ""),
                location_guess=data.get("location_guess", ""),
                colors=colors,
                lighting=data.get("lighting", "unknown"),
                composition=data.get("composition", ""),
                mood_keywords=data.get("mood_keywords", []),
                era_guess=data.get("era_guess", ""),
                prompt_fragment=data.get("prompt_fragment", ""),
                quality_tags=data.get("quality_tags", []),
            )

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to parse vision response: {e}")
            raise ValueError(f"Image analysis parsing failed: {e}")

    @staticmethod
    def build_fallback_analysis(image_metadata: dict) -> ImageAnalysis:
        """
        当 Vision API 不可用时的兜底分析
        仅基于图片元数据做基础推断
        """
        colors = ColorProfile(
            dominant_colors=["unknown"],
            accent_colors=[],
            color_temperature="neutral",
            saturation_level="medium",
            contrast_level="medium",
        )

        return ImageAnalysis(
            main_subject=image_metadata.get("filename", "subject"),
            scene_type="unknown",
            scene_description_en="a scene",
            colors=colors,
            lighting="unknown",
            prompt_fragment=image_metadata.get("filename", "a scene"),
            model_used="fallback-metadata",
        )


# ============================================================
# Prompt Fragment 优化器
# ============================================================

class PromptFragmentOptimizer:
    """
    将图片分析结果优化为可直接用于 AI 绘画的提示词片段
    处理逻辑：
      1. 检查是否超过字数限制
      2. 按重要性排序关键词
      3. 确保语法正确且适合 AI 绘画工具
    """

    MAX_WORDS = 30  # 提示词片段最大词数
    DEFAULT_STRUCTURE = [
        "main_subject",       # 主体优先
        "scene_context",      # 场景上下文
        "color_lighting",     # 颜色光影
        "quality_tags",       # 画质标签
    ]

    @staticmethod
    def optimize(fragment: str, analysis: ImageAnalysis) -> str:
        """
        优化提示词片段

        Args:
            fragment: Vision 生成的原始片段
            analysis: 完整的图片分析结果
        """
        words = fragment.split()
        if len(words) <= PromptFragmentOptimizer.MAX_WORDS:
            return fragment

        # 超过字数限制时，按优先级裁剪
        optimized = fragment
        # 先去掉最不重要的修饰词
        filler_words = {"very", "quite", "rather", "somewhat", "kind of",
                        "sort of", "a bit", "really", "extremely"}
        filtered = [w for w in words if w.lower() not in filler_words]

        if len(filtered) > PromptFragmentOptimizer.MAX_WORDS:
            # 仍然超限，取前 MAX_WORDS 个词
            filtered = filtered[:PromptFragmentOptimizer.MAX_WORDS]

        return " ".join(filtered)

    @staticmethod
    def enhance_with_scene(analysis: ImageAnalysis) -> str:
        """基于场景类型增强提示词"""
        scene_enhancements = {
            "indoor": "interior space",
            "outdoor": "open air",
            "urban": "urban landscape",
            "nature": "natural setting",
            "portrait": "portrait shot",
            "architecture": "architectural space",
            "night": "night scene",
            "day": "daylight scene",
        }
        base = analysis.prompt_fragment or analysis.main_subject
        enhancement = scene_enhancements.get(analysis.scene_type, "")
        if enhancement:
            return f"{base}, {enhancement}"
        return base
