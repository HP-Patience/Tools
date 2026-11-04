"""
============================================================
多模态输出编排器 (Multi-Modal Output Composer)
============================================================
层级: 输出与交互层 (Layer 4 — Output & Interaction)
功能:
  1. 将组装好的提示词格式化为多种输出形态
  2. Markdown / 卡片 / 交互组件 / 流式输出
  3. 针对不同用户场景自适应呈现

架构位置: Skill Pipeline Stage 6 — Output Composition
============================================================
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# 输出格式枚举
# ============================================================

class OutputFormat(Enum):
    MARKDOWN = "markdown"           # 标准 Markdown 文本
    CARD = "card"                   # 结构化卡片（带图标、表格）
    INTERACTIVE = "interactive"     # 交互组件（按钮、下拉菜单）
    STREAMING = "streaming"         # 流式输出
    MINIMAL = "minimal"             # 极简模式（仅提示词）
    EXPORT = "export"               # 导出格式（JSON/YAML）


class OutputMode(Enum):
    FULL = "full"                   # 完整输出（分析+配方+提示词+建议）
    PROMPT_ONLY = "prompt_only"     # 仅提示词
    COMPARISON = "comparison"       # 多风格对比输出


# ============================================================
# 输出数据结构
# ============================================================

@dataclass
class OutputContent:
    """输出内容的完整结构"""
    # 图片分析摘要
    image_analysis_summary: dict = field(default_factory=dict)

    # 风格配方摘要
    style_recipe_summary: dict = field(default_factory=dict)

    # 提示词（多模型）
    prompts: dict = field(default_factory=dict)

    # 使用建议
    tips: list[str] = field(default_factory=list)

    # 交互建议（按钮/快捷追问）
    interaction_suggestions: list[dict] = field(default_factory=list)

    # 元数据
    metadata: dict = field(default_factory=dict)


# ============================================================
# 输出编排器
# ============================================================

class OutputComposer:
    """
    多模态输出编排器

    将内部结构化数据 → 格式化为用户可读的输出
    支持: Markdown / Card / Interactive / Streaming / Minimal
    """

    @staticmethod
    def compose_markdown(
        content: OutputContent,
        mode: OutputMode = OutputMode.FULL,
    ) -> str:
        """生成美观的 Markdown 格式输出"""

        if mode == OutputMode.PROMPT_ONLY:
            return OutputComposer._prompt_only_markdown(content)

        if mode == OutputMode.COMPARISON:
            return OutputComposer._comparison_markdown(content)

        return OutputComposer._full_markdown(content)

    @staticmethod
    def _full_markdown(content: OutputContent) -> str:
        """完整 Markdown 输出"""
        parts = []

        # === 头部 ===
        style_name = content.style_recipe_summary.get("name_zh", "未知风格")
        style_en = content.style_recipe_summary.get("name_en", "Unknown")
        parts.append(f"## 🎨 梦核风格转换结果 — {style_name} ({style_en})")
        parts.append("")

        # === 图片分析摘要 ===
        parts.append("### 📷 图片分析")
        parts.append("")
        img = content.image_analysis_summary
        parts.append("| 维度 | 内容 |")
        parts.append("|------|------|")
        if img.get("main_subject"):
            parts.append(f"| 主体 | {img['main_subject']} |")
        if img.get("scene_description_zh"):
            parts.append(f"| 场景 | {img['scene_description_zh']} |")
        if img.get("location_guess"):
            parts.append(f"| 地点类型 | {img['location_guess']} |")
        if img.get("dominant_colors"):
            color_str = "、".join(img["dominant_colors"][:3])
            parts.append(f"| 主色调 | {color_str} |")
        if img.get("lighting"):
            parts.append(f"| 光影 | {img['lighting']} |")
        if img.get("mood_keywords"):
            mood_str = "、".join(img["mood_keywords"][:3])
            parts.append(f"| 情绪基调 | {mood_str} |")
        parts.append("")

        # === 风格配方摘要 ===
        parts.append("### 🧪 风格配方")
        parts.append("")
        recipe = content.style_recipe_summary
        parts.append(f"> **核心**：{recipe.get('core_keywords', '')}")
        parts.append(f"> **视觉**：{recipe.get('visual_features', '')}")
        parts.append(f"> **情绪**：{recipe.get('mood_atmosphere', '')}")
        parts.append(f"> **时代**：{recipe.get('era_params', '')}")
        parts.append("")

        # === 最终提示词 ===
        parts.append("### 🖼️ 最终提示词")
        parts.append("")
        prompts = content.prompts

        # Midjourney
        if prompts.get("midjourney"):
            parts.append("#### Midjourney")
            parts.append("```")
            parts.append(f"{prompts['midjourney']['prompt']} {prompts['midjourney']['params']}")
            parts.append("```")
            parts.append("")

        # Stable Diffusion
        if prompts.get("stable_diffusion"):
            parts.append("#### Stable Diffusion")
            parts.append(f"**正向提示词 (Positive Prompt)：**")
            parts.append("```")
            parts.append(prompts["stable_diffusion"]["positive"])
            parts.append("```")
            parts.append(f"**负面提示词 (Negative Prompt)：**")
            parts.append("```")
            parts.append(prompts["stable_diffusion"]["negative"])
            parts.append("```")
            parts.append("")

        # DALL-E 3
        if prompts.get("dalle"):
            parts.append("#### DALL-E 3")
            parts.append("```")
            parts.append(prompts["dalle"])
            parts.append("```")
            parts.append("")

        # === 使用建议 ===
        if content.tips:
            parts.append("### 💡 使用建议")
            parts.append("")
            for i, tip in enumerate(content.tips, 1):
                parts.append(f"{i}. {tip}")
            parts.append("")

        # === 快捷操作 ===
        if content.interaction_suggestions:
            parts.append("### 🔄 快捷操作")
            parts.append("")
            for sug in content.interaction_suggestions:
                label = sug.get("label", "")
                command = sug.get("command", "")
                parts.append(f"- **{label}**：`{command}`")
            parts.append("")

        # === 页脚 ===
        parts.append("---")
        parts.append(f"*风格强度: {content.metadata.get('intensity', 'standard')} | "
                     f"词数: {content.metadata.get('word_count', 0)} | "
                     f"生成: Dreamcore Style Transfer v2.0*")

        return "\n".join(parts)

    @staticmethod
    def _prompt_only_markdown(content: OutputContent) -> str:
        """极简模式：仅输出提示词"""
        parts = []
        prompts = content.prompts

        if prompts.get("midjourney"):
            parts.append(f"**Midjourney:**")
            parts.append(f"```\n{prompts['midjourney']['prompt']} {prompts['midjourney']['params']}\n```")
            parts.append("")

        if prompts.get("stable_diffusion"):
            parts.append(f"**Stable Diffusion:**")
            parts.append(f"Positive: `{prompts['stable_diffusion']['positive']}`")
            parts.append(f"Negative: `{prompts['stable_diffusion']['negative']}`")
            parts.append("")

        return "\n".join(parts)

    @staticmethod
    def _comparison_markdown(content: OutputContent) -> str:
        """多风格对比输出"""
        parts = ["## 🎨 多风格对比", ""]
        parts.append("| 风格 | 提示词片段 | 情绪 | 适用场景 |")
        parts.append("|------|----------|------|----------|")
        for comparison in content.metadata.get("comparisons", []):
            parts.append(
                f"| {comparison.get('name', '')} | "
                f"{comparison.get('prompt_snippet', '')[:60]}... | "
                f"{comparison.get('mood', '')} | "
                f"{comparison.get('best_for', '')} |"
            )
        return "\n".join(parts)

    @staticmethod
    def compose_card(content: OutputContent) -> dict:
        """
        生成结构化卡片数据（JSON 格式）
        适合在 UI 中渲染为卡片组件
        """
        return {
            "card_type": "dreamcore_style_transfer",
            "version": "2.0",
            "header": {
                "title": f"{content.style_recipe_summary.get('name_zh', '')} 风格转换",
                "subtitle": content.style_recipe_summary.get("name_en", ""),
                "icon": "🎨",
            },
            "sections": [
                {
                    "type": "table",
                    "title": "📷 图片分析",
                    "rows": [
                        {"label": "主体", "value": content.image_analysis_summary.get("main_subject", "")},
                        {"label": "场景", "value": content.image_analysis_summary.get("scene_description_zh", "")},
                        {"label": "色调", "value": ", ".join(content.image_analysis_summary.get("dominant_colors", []))},
                    ],
                },
                {
                    "type": "code_block",
                    "title": "🖼️ Midjourney 提示词",
                    "language": "text",
                    "content": content.prompts.get("midjourney", {}).get("prompt", ""),
                    "params": content.prompts.get("midjourney", {}).get("params", ""),
                },
                {
                    "type": "code_block",
                    "title": "🖼️ Stable Diffusion 提示词",
                    "language": "text",
                    "content": content.prompts.get("stable_diffusion", {}).get("positive", ""),
                    "negative": content.prompts.get("stable_diffusion", {}).get("negative", ""),
                },
                {
                    "type": "actions",
                    "title": "🔄 快捷操作",
                    "buttons": [
                        {"label": "🔄 换一种风格", "action": "switch_style"},
                        {"label": "🔧 微调强度", "action": "tweak_intensity"},
                        {"label": "📋 复制提示词", "action": "copy_prompt"},
                        {"label": "🌟 生成对比图", "action": "compare_styles"},
                    ],
                },
            ],
            "footer": {
                "text": f"风格强度: {content.metadata.get('intensity', 'standard')} | Dreamcore Style Transfer v2.0",
            },
        }

    @staticmethod
    def compose_interactive(content: OutputContent) -> dict:
        """
        生成交互式输出（含可点击追问建议）

        Returns:
            dict: 包含文本内容和交互建议的结构
        """
        return {
            "text": OutputComposer.compose_markdown(content, OutputMode.FULL),
            "quick_replies": [
                {
                    "label": "🔄 换一种风格",
                    "prompt": "帮我换一种风格",
                    "style": "action",
                },
                {
                    "label": "🔧 再强烈一点",
                    "prompt": "风格再强烈一点",
                    "style": "tweak",
                },
                {
                    "label": "📋 仅看提示词",
                    "prompt": "只要提示词",
                    "style": "minimal",
                },
                {
                    "label": "🌟 对比3种风格",
                    "prompt": "对比一下这个场景用梦核、怪核和阈限空间的效果",
                    "style": "compare",
                },
                {
                    "label": "❓ 解释这个风格",
                    "prompt": "解释一下这个风格的特点",
                    "style": "info",
                },
            ],
            "context": {
                "current_style": content.style_recipe_summary.get("id", ""),
                "intensity": content.metadata.get("intensity", "standard"),
                "image_described": bool(content.image_analysis_summary.get("main_subject")),
            },
        }

    @staticmethod
    def compose_streaming_chunks(content: OutputContent) -> list[str]:
        """
        生成流式输出的分块列表
        模拟逐段输出的体验
        """
        chunks = []
        style_name = content.style_recipe_summary.get("name_zh", "")

        chunks.append(f"🎨 正在分析图片...\n")
        chunks.append(f"📷 识别到主体：{content.image_analysis_summary.get('main_subject', '未知')}\n")
        chunks.append(f"🌈 主色调：{', '.join(content.image_analysis_summary.get('dominant_colors', ['分析中']))}\n")
        chunks.append(f"\n🧪 已匹配风格配方：{style_name}\n")
        chunks.append(f"\n🖼️ 正在组装提示词...\n\n")
        chunks.append(OutputComposer.compose_markdown(content, OutputMode.PROMPT_ONLY))
        chunks.append("\n✨ 生成完成！您可以将提示词复制到 AI 绘画工具中使用。")

        return chunks

    @staticmethod
    def compose_export(content: OutputContent, format: str = "json") -> str:
        """
        导出为可保存的格式

        Args:
            content: 输出内容
            format: 导出格式 (json / yaml)
        """
        export_data = {
            "skill": "dreamcore-style-transfer",
            "version": "2.0.0",
            "timestamp": content.metadata.get("timestamp", ""),
            "style": {
                "id": content.style_recipe_summary.get("id", ""),
                "name": content.style_recipe_summary.get("name_zh", ""),
                "intensity": content.metadata.get("intensity", "standard"),
            },
            "image_analysis": content.image_analysis_summary,
            "prompts": content.prompts,
        }

        if format == "json":
            return json.dumps(export_data, ensure_ascii=False, indent=2)
        elif format == "yaml":
            # 简单 YAML 序列化
            return OutputComposer._to_yaml_simple(export_data)
        else:
            return json.dumps(export_data, ensure_ascii=False, indent=2)

    @staticmethod
    def _to_yaml_simple(data: dict, indent: int = 0) -> str:
        """简易 YAML 序列化器（无需第三方库）"""
        lines = []
        prefix = "  " * indent
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(OutputComposer._to_yaml_simple(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                for item in value:
                    lines.append(f"{prefix}  - {item}")
            elif isinstance(value, str):
                if "\n" in value:
                    lines.append(f"{prefix}{key}: |")
                    for subline in value.split("\n"):
                        lines.append(f"{prefix}  {subline}")
                else:
                    lines.append(f"{prefix}{key}: {value}")
            else:
                lines.append(f"{prefix}{key}: {value}")
        return "\n".join(lines)


# ============================================================
# 输出构建器（便捷方法）
# ============================================================

class OutputBuilder:
    """快速构建 OutputContent 的辅助类"""

    @staticmethod
    def build_from_analysis(
        analysis: dict,
        recipe_summary: dict,
        prompts: dict,
        intensity: str = "standard",
        tips: Optional[list[str]] = None,
        word_count: int = 0,
    ) -> OutputContent:
        """从分析结果和配方快速构建输出内容"""

        default_tips = [
            "建议在 Midjourney 中使用 --stylize 参数控制风格化程度（默认750）",
            "如果结果不够「核」，可以尝试增加 intensity 到「强烈」",
            "可以配合 --ar 参数调整画面比例，梦核风格推荐 4:3",
            "如生成出不需要的元素，请使用负面提示词排除",
            "不同 AI 绘画工具对同一提示词的理解会有差异，建议多试几次",
        ]

        return OutputContent(
            image_analysis_summary=analysis,
            style_recipe_summary=recipe_summary,
            prompts=prompts,
            tips=tips or default_tips,
            interaction_suggestions=[
                {"label": "换一种风格", "command": "帮我换一种风格"},
                {"label": "调整强度", "command": "风格再强烈一点 / 再柔和一点"},
                {"label": "对比风格", "command": "对比一下这个场景用其他风格的效果"},
                {"label": "仅看提示词", "command": "只要提示词，简化输出"},
            ],
            metadata={
                "intensity": intensity,
                "word_count": word_count,
                "timestamp": "",
            },
        )
