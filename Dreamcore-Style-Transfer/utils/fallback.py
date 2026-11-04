"""
============================================================
兜底逻辑 & 异常处理 (Fallback & Error Handler)
============================================================
层级: 核心处理逻辑层辅助模块
功能:
  1. 当 API 超时或不可用时的降级策略
  2. 预设的安抚话术
  3. 缓存数据替代方案
  4. 错误恢复建议

设计原则:
  - 不静默失败：任何错误都有用户可见的提示
  - 优雅降级：部分功能不可用时仍能提供基础服务
  - 可恢复：尽可能给出重试/替代方案
============================================================
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable

logger = logging.getLogger(__name__)


# ============================================================
# 错误严重级别
# ============================================================

class ErrorSeverity(Enum):
    LOW = "low"           # 不影响核心功能（如统计记录失败）
    MEDIUM = "medium"     # 影响部分功能（如颜色分析失败）
    HIGH = "high"         # 影响核心功能（如图片分析失败）
    CRITICAL = "critical" # 导致 Skill 完全不可用


# ============================================================
# 错误类型定义
# ============================================================

@dataclass
class SkillError:
    """Skill 内部错误"""
    error_code: str
    message: str
    severity: ErrorSeverity
    recoverable: bool
    recovery_hint: str = ""
    technical_detail: str = ""


# 预定义错误
ERRORS = {
    "IMAGE_ANALYSIS_TIMEOUT": SkillError(
        error_code="E_IMG_TIMEOUT",
        message="图片分析超时，可能是图片过大或网络不稳定。",
        severity=ErrorSeverity.HIGH,
        recoverable=True,
        recovery_hint="请尝试压缩图片后重新上传，或手动描述图片内容。",
        technical_detail="Vision API call exceeded timeout limit.",
    ),
    "IMAGE_ANALYSIS_FAILED": SkillError(
        error_code="E_IMG_FAILED",
        message="图片分析失败，可能是图片格式不受支持或内容无法识别。",
        severity=ErrorSeverity.HIGH,
        recoverable=True,
        recovery_hint="请换一张图片试试，或直接告诉我图片内容（如「一个女孩在教室里」）。",
        technical_detail="Vision API returned an error or invalid response.",
    ),
    "STYLE_NOT_FOUND": SkillError(
        error_code="E_STYLE_404",
        message="找不到这种风格。",
        severity=ErrorSeverity.MEDIUM,
        recoverable=True,
        recovery_hint="请从支持的10种风格中选择：梦核、怪核、阈限空间、伤核、后室、童年核、池核、网核、催眠核、中式梦核。",
        technical_detail="Style ID not found in STYLE_INDEX.",
    ),
    "PROMPT_EMPTY": SkillError(
        error_code="E_PROMPT_EMPTY",
        message="提示词生成结果为空，请重试。",
        severity=ErrorSeverity.HIGH,
        recoverable=True,
        recovery_hint="请检查图片分析和风格匹配是否正常完成。",
        technical_detail="Assembled prompt was empty string.",
    ),
    "RATE_LIMITED": SkillError(
        error_code="E_RATE",
        message="请求过于频繁，请稍后再试。",
        severity=ErrorSeverity.LOW,
        recoverable=True,
        recovery_hint="建议每秒不超过1次请求。",
        technical_detail="Rate limit exceeded.",
    ),
    "SESSION_EXPIRED": SkillError(
        error_code="E_SESSION_EXPIRED",
        message="会话已过期（超过30分钟无操作），上下文已清空。",
        severity=ErrorSeverity.LOW,
        recoverable=True,
        recovery_hint="请重新上传图片并选择风格。",
        technical_detail="Session state expired due to inactivity.",
    ),
    "PROFILE_SAVE_FAILED": SkillError(
        error_code="E_PROFILE_SAVE",
        message="",  # 用户不需要看到这条
        severity=ErrorSeverity.LOW,
        recoverable=True,
        recovery_hint="",
        technical_detail="Failed to persist user profile.",
    ),
}


# ============================================================
# 降级策略
# ============================================================

class FallbackStrategy:
    """
    优雅降级策略管理器

    降级路径:
      Level 1: 完整功能 (Vision分析 + 配方匹配 + 提示词组装)
      Level 2: 基础功能 (用户描述 + 配方匹配 + 提示词组装)
      Level 3: 最小功能 (通用提示词模板)
    """

    DEGRADATION_LEVELS = {
        1: {
            "name": "完整功能",
            "description": "Vision API 分析图片 + 完整配方匹配 + 多模型输出",
            "requires": ["vision_api", "style_index", "prompt_assembler"],
        },
        2: {
            "name": "基础功能",
            "description": "用户手动描述图片 + 配方匹配 + 简化输出",
            "requires": ["manual_description", "style_index", "prompt_assembler"],
        },
        3: {
            "name": "最小功能",
            "description": "通用模板 + 用户选择风格",
            "requires": ["style_index", "template_prompts"],
        },
    }

    def __init__(self):
        self.current_level = 1

    def degrade(self) -> int:
        """降级到下一级"""
        if self.current_level < 3:
            self.current_level += 1
            logger.warning(
                f"Degraded to Level {self.current_level}: "
                f"{self.DEGRADATION_LEVELS[self.current_level]['name']}"
            )
        return self.current_level

    def can_provide_service(self) -> bool:
        """即使在降级状态，是否还能提供服务"""
        return self.current_level <= 3

    def get_level_description(self) -> str:
        return self.DEGRADATION_LEVELS.get(self.current_level, {}).get("description", "未知")

    # === 各降级级别的兜底提示词模板 ===

    @staticmethod
    def get_template_prompt(style_id: str, user_description: str = "a scene") -> str:
        """
        Level 3 降级时使用的通用模板
        当 Vision API 不可用且用户未提供描述时
        """
        templates = {
            "dreamcore": f"{user_description}, dreamcore aesthetic, nostalgic surreal, soft overexposed lighting, hazy, vintage 90s film",
            "weirdcore": f"{user_description}, weirdcore aesthetic, unsettling, glitch art, distorted, low quality",
            "liminal_space": f"{user_description}, liminal space, empty, eerie stillness, abandoned, transitional",
            "traumacore": f"{user_description}, traumacore aesthetic, melancholic, fragile, scrapbook style",
            "backrooms": f"{user_description}, the backrooms, endless yellow rooms, fluorescent lighting, trapped feeling",
            "kidcore": f"{user_description}, kidcore aesthetic, bright saturated colors, 90s toys, nostalgic",
            "poolcore": f"{user_description}, poolcore aesthetic, empty pool, blue tiles, clear still water, serene eerie",
            "webcore": f"{user_description}, webcore aesthetic, early internet, pixelated, Windows XP, old web",
            "hypnocore": f"{user_description}, hypnocore aesthetic, hypnotic spirals, psychedelic, disorienting",
            "chinese_dreamcore": f"{user_description}, Chinese dreamcore, 2000s China nostalgia, vintage CCD, electronic homesickness",
        }
        return templates.get(style_id, f"{user_description}, dreamcore aesthetic")


# ============================================================
# 安抚话术库
# ============================================================

class UserFriendlyMessages:
    """用户友好的话术模板"""

    @staticmethod
    def error_occurred(error: SkillError) -> str:
        """错误发生时的安抚话术"""
        severity_emoji = {
            ErrorSeverity.LOW: "ℹ️",
            ErrorSeverity.MEDIUM: "⚠️",
            ErrorSeverity.HIGH: "❌",
            ErrorSeverity.CRITICAL: "🚨",
        }
        emoji = severity_emoji.get(error.severity, "⚠️")
        msg = f"{emoji} {error.message}"
        if error.recovery_hint:
            msg += f"\n\n💡 {error.recovery_hint}"
        return msg

    @staticmethod
    def falling_back(level: int, description: str) -> str:
        """通知用户正在降级"""
        return (
            f"⚠️ 很抱歉，部分高级功能暂时不可用，已自动切换到「{description}」模式。\n"
            "您仍然可以继续使用核心功能。"
        )

    @staticmethod
    def waiting_too_long(seconds: int) -> str:
        """用户等待太久时的提示"""
        if seconds > 15:
            return "⏳ 处理时间比预期长，请耐心等待..."
        return ""

    @staticmethod
    def success_with_hiccups(errors: list[str]) -> str:
        """虽然有错误但核心功能正常时的提示"""
        msg = "✅ 处理完成！（部分非核心功能出现小问题，不影响使用）\n"
        return msg

    @staticmethod
    def suggest_retry(action: str) -> str:
        """建议用户重试"""
        return f"🔄 请尝试 {action}。如果问题持续，请稍后再试。"

    @staticmethod
    def upgrade_prompt() -> str:
        """引导用户升级"""
        return "💎 更多高级风格和参数调整是会员专属功能。升级会员解锁全部功能。"
