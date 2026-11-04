"""
============================================================
短期记忆 — 会话状态管理器 (Session State Manager)
============================================================
层级: 记忆与状态层 (Layer 5 — Memory & State)
功能:
  1. 记录本次对话中的历史查询与结果
  2. 支持连续追问时的指代消解
  3. 管理多步骤任务的状态机
  4. 超时自动清理

关键设计:
  - 每次对话独立 session
  - 支持 undo/redo 风格回退
  - 状态变更记录完整 audit log

状态机示例:
  IDLE → IMAGE_UPLOADED → ANALYZED → STYLE_SELECTED → PROMPT_GENERATED → ... → IDLE
============================================================
"""

import json
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# 状态机定义
# ============================================================

class PipelineState(Enum):
    """Skill 流水线状态"""
    IDLE = "idle"                             # 空闲等待
    AWAITING_IMAGE = "awaiting_image"          # 等待用户上传图片
    IMAGE_RECEIVED = "image_received"          # 图片已接收
    ANALYZING = "analyzing"                    # 正在分析图片
    ANALYZED = "analyzed"                      # 图片分析完成
    AWAITING_STYLE = "awaiting_style"          # 等待用户选择风格
    STYLE_SELECTED = "style_selected"          # 风格已选择
    MATCHING_STYLE = "matching_style"          # 正在匹配风格
    ASSEMBLING_PROMPT = "assembling_prompt"    # 正在组装提示词
    PROMPT_GENERATED = "prompt_generated"      # 提示词已生成
    AWAITING_TWEAK = "awaiting_tweak"          # 等待用户确认/微调
    ERROR = "error"                            # 异常状态
    FALLBACK = "fallback"                      # 降级状态


# 状态转换规则
STATE_TRANSITIONS: dict[PipelineState, list[PipelineState]] = {
    PipelineState.IDLE: [
        PipelineState.AWAITING_IMAGE,
        PipelineState.IDLE,
    ],
    PipelineState.AWAITING_IMAGE: [
        PipelineState.IMAGE_RECEIVED,
        PipelineState.ERROR,
        PipelineState.IDLE,
    ],
    PipelineState.IMAGE_RECEIVED: [
        PipelineState.ANALYZING,
        PipelineState.ERROR,
    ],
    PipelineState.ANALYZING: [
        PipelineState.ANALYZED,
        PipelineState.FALLBACK,
        PipelineState.ERROR,
    ],
    PipelineState.ANALYZED: [
        PipelineState.AWAITING_STYLE,
        PipelineState.IDLE,
        PipelineState.ERROR,
    ],
    PipelineState.AWAITING_STYLE: [
        PipelineState.STYLE_SELECTED,
        PipelineState.IDLE,
    ],
    PipelineState.STYLE_SELECTED: [
        PipelineState.MATCHING_STYLE,
        PipelineState.ERROR,
    ],
    PipelineState.MATCHING_STYLE: [
        PipelineState.ASSEMBLING_PROMPT,
        PipelineState.AWAITING_STYLE,
        PipelineState.ERROR,
    ],
    PipelineState.ASSEMBLING_PROMPT: [
        PipelineState.PROMPT_GENERATED,
        PipelineState.ERROR,
    ],
    PipelineState.PROMPT_GENERATED: [
        PipelineState.AWAITING_TWEAK,
        PipelineState.IDLE,
        PipelineState.AWAITING_STYLE,  # 换风格
    ],
    PipelineState.AWAITING_TWEAK: [
        PipelineState.ASSEMBLING_PROMPT,  # 重新调整
        PipelineState.IDLE,
        PipelineState.AWAITING_STYLE,     # 换风格
    ],
    PipelineState.ERROR: [
        PipelineState.IDLE,
        PipelineState.AWAITING_IMAGE,
        PipelineState.AWAITING_STYLE,
    ],
    PipelineState.FALLBACK: [
        PipelineState.IDLE,
        PipelineState.AWAITING_STYLE,
    ],
}


# ============================================================
# 会话状态数据结构
# ============================================================

@dataclass
class QueryRecord:
    """单次查询的完整记录"""
    query_id: str
    timestamp: float
    user_input: str
    state_before: str
    state_after: str

    # 输入
    image_path: Optional[str] = None
    style_requested: Optional[str] = None
    intensity: str = "standard"
    target_model: str = "midjourney"

    # 分析结果
    image_analysis: Optional[dict] = None
    style_resolved: Optional[str] = None
    style_confidence: float = 0.0

    # 输出结果
    prompt_generated: Optional[str] = None
    output_format: str = "markdown"

    # 用户反馈
    user_feedback: Optional[str] = None
    user_satisfaction: Optional[str] = None  # satisfied / neutral / unsatisfied

    def to_dict(self) -> dict:
        return {
            "query_id": self.query_id,
            "timestamp": self.timestamp,
            "user_input": self.user_input,
            "image_path": self.image_path,
            "style_requested": self.style_requested,
            "style_resolved": self.style_resolved,
            "intensity": self.intensity,
            "prompt_generated": self.prompt_generated[:200] if self.prompt_generated else None,
            "output_format": self.output_format,
        }


@dataclass
class SessionState:
    """会话状态对象"""
    session_id: str
    created_at: float
    updated_at: float

    # 当前状态
    current_state: PipelineState = PipelineState.IDLE

    # 当前上下文
    current_image_path: Optional[str] = None
    current_image_analysis: Optional[dict] = None
    current_style_id: Optional[str] = None
    current_style_name: Optional[str] = None
    current_intensity: str = "standard"
    current_target_model: str = "midjourney"
    last_prompt: Optional[str] = None

    # 历史记录
    query_history: list[QueryRecord] = field(default_factory=list)
    max_history: int = 20

    # 统计
    total_queries: int = 0
    error_count: int = 0


# ============================================================
# 会话状态管理器
# ============================================================

class SessionStateManager:
    """
    会话状态管理器

    核心能力:
      - 状态机校验：确保状态转换合法
      - 上下文继承：下一轮对话自动继承上一轮的关键参数
      - 指代消解：当用户说"那换成梦核呢"，自动理解为"把刚才的图换成梦核风格"
      - 历史回溯：支持撤回和重试
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = SessionState(
            session_id=session_id,
            created_at=time.time(),
            updated_at=time.time(),
        )
        self._query_counter = 0
        logger.info(f"Session {session_id} created")

    # === 状态转换 ===

    def transition_to(self, new_state: PipelineState) -> bool:
        """
        尝试转换到新状态
        校验转换是否合法
        """
        allowed = STATE_TRANSITIONS.get(self.state.current_state, [])

        if new_state not in allowed:
            logger.warning(
                f"Invalid state transition: {self.state.current_state.value} → {new_state.value}"
            )
            # 不合法时自动回退到 IDLE
            if PipelineState.IDLE in allowed:
                self.state.current_state = PipelineState.IDLE
                self._touch()
                return False
            # IDLE 也不在允许列表时强制进入 ERROR
            self.state.current_state = PipelineState.ERROR
            self._touch()
            return False

        self.state.current_state = new_state
        self._touch()
        logger.info(f"State: → {new_state.value}")
        return True

    def is_in_state(self, state: PipelineState) -> bool:
        return self.state.current_state == state

    # === 上下文管理 ===

    def set_image(self, image_path: str, analysis: Optional[dict] = None):
        """设置当前图片及分析结果"""
        self.state.current_image_path = image_path
        self.state.current_image_analysis = analysis
        self._touch()

    def set_style(self, style_id: str, style_name: str):
        """设置当前选择的风格"""
        self.state.current_style_id = style_id
        self.state.current_style_name = style_name
        self._touch()

    def set_prompt(self, prompt: str):
        """保存生成的提示词"""
        self.state.last_prompt = prompt
        self._touch()

    def get_inheritable_context(self) -> dict:
        """
        获取可继承的上下文（用于下一轮对话的指代消解）
        """
        return {
            "image_path": self.state.current_image_path,
            "image_analysis": self.state.current_image_analysis,
            "style_id": self.state.current_style_id,
            "style_name": self.state.current_style_name,
            "intensity": self.state.current_intensity,
            "target_model": self.state.current_target_model,
        }

    def resolve_reference(self, user_input: str) -> dict:
        """
        指代消解：将用户输入中的代词/简称替换为具体值

        例：
          - "那换怪核呢" → 继承图片，切换风格到 weirdcore
          - "再强烈一点" → 继承所有上下文，增强 intensity
          - "这张图也用梦核" → 继承风格，重置图片
        """
        context = self.get_inheritable_context()
        resolved = {
            "user_input": user_input,
            "inherited": {},
            "resolved_style": None,
            "resolved_intensity": None,
            "resolved_image": None,
        }

        # 检查是否是风格切换（"那{style}呢"）
        from core.style_matcher import StyleMatcher
        style_result = StyleMatcher.resolve(user_input)
        if style_result["resolved"]:
            resolved["resolved_style"] = style_result["style_id"]
            # 继承图片
            if context["image_path"]:
                resolved["inherited"]["image"] = context["image_path"]
                resolved["inherited"]["image_analysis"] = context["image_analysis"]

        # 检查是否是强度调整
        intensity_keywords = {
            "mild": ["轻柔", "轻一点", "淡一点", "柔和", "温和", "一点点", "轻"],
            "standard": ["正常", "标准", "适中", "默认"],
            "extreme": ["强烈", "极致", "拉满", "重度", "极限", "重一点", "加强"],
        }
        for intensity, keywords in intensity_keywords.items():
            if any(kw in user_input for kw in keywords):
                resolved["resolved_intensity"] = intensity
                resolved["inherited"]["image"] = context["image_path"]
                resolved["inherited"]["style"] = context["style_id"]

        return resolved

    # === 历史记录 ===

    def record_query(self, record: QueryRecord):
        """记录一次查询"""
        if len(self.state.query_history) >= self.state.max_history:
            self.state.query_history.pop(0)  # 移除最早记录
        self.state.query_history.append(record)
        self.state.total_queries += 1
        self._query_counter += 1
        self._touch()

    def get_last_query(self) -> Optional[QueryRecord]:
        """获取最近一次查询"""
        if self.state.query_history:
            return self.state.query_history[-1]
        return None

    def get_last_n_queries(self, n: int = 5) -> list[QueryRecord]:
        """获取最近 n 次查询"""
        return self.state.query_history[-n:]

    def can_undo(self) -> bool:
        """是否存在可以撤回的操作"""
        return len(self.state.query_history) >= 2

    def undo_last(self) -> Optional[QueryRecord]:
        """
        撤回到上一次查询状态
        移除最后一次查询记录并恢复上下文
        """
        if not self.can_undo():
            return None
        # 移除最后一次
        removed = self.state.query_history.pop()
        # 恢复到上一次
        previous = self.state.query_history[-1] if self.state.query_history else None
        if previous:
            self.state.current_image_path = previous.image_path
            self.state.current_style_id = previous.style_resolved
            self.state.current_intensity = previous.intensity
            self.state.last_prompt = previous.prompt_generated
        self._touch()
        return removed

    # === 生命周期 ===

    def is_expired(self, max_idle_seconds: int = 1800) -> bool:
        """检查会话是否过期（默认30分钟无操作过期）"""
        return (time.time() - self.state.updated_at) > max_idle_seconds

    def reset(self):
        """重置会话状态（保留历史记录）"""
        self.state.current_state = PipelineState.IDLE
        self.state.current_image_path = None
        self.state.current_image_analysis = None
        self.state.current_style_id = None
        self.state.current_style_name = None
        self.state.last_prompt = None
        self._touch()

    def clear(self):
        """完全清除会话（包括历史记录）"""
        self.__init__(self.session_id)

    def _touch(self):
        self.state.updated_at = time.time()

    def get_status_report(self) -> str:
        """生成会话状态报告（调试用）"""
        return (
            f"Session: {self.session_id}\n"
            f"State: {self.state.current_state.value}\n"
            f"Queries: {self.state.total_queries}\n"
            f"Errors: {self.state.error_count}\n"
            f"Current style: {self.state.current_style_name or 'None'}\n"
            f"Current image: {self.state.current_image_path or 'None'}\n"
            f"Last prompt length: {len(self.state.last_prompt) if self.state.last_prompt else 0}"
        )
