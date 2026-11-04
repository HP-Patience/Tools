"""
============================================================
对话上下文管理器 (Conversation Context Manager)
============================================================
层级: 记忆与状态层 (Layer 5 — Memory & State)
功能:
  1. 管理多轮对话的完整上下文
  2. 指代消解：自动理解"它"、"那个"、"那"等指代词
  3. 上下文窗口管理：当对话过长时智能裁剪
  4. 话题切换检测与上下文重置

这是连接 Trigger 层和 Session State 的桥梁模块。
============================================================
"""

import re
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

class ContextScope(Enum):
    """上下文作用域"""
    CURRENT_TURN = "current_turn"     # 仅当前轮
    RECENT_TURNS = "recent_turns"     # 最近几轮
    ENTIRE_SESSION = "entire_session" # 整个会话
    CROSS_SESSION = "cross_session"   # 跨会话（长期记忆）


@dataclass
class ConversationTurn:
    """单轮对话"""
    turn_id: int
    timestamp: float
    user_input: str
    intent: str                       # 识别的意图类型
    entities: dict = field(default_factory=dict)  # 提取的实体
    resolved_references: dict = field(default_factory=dict)  # 消解后的引用
    skill_response_summary: str = ""  # Skill 回复的摘要
    context_snapshot: dict = field(default_factory=dict)  # 上下文快照


@dataclass
class ConversationContext:
    """完整对话上下文"""
    session_id: str
    turns: list[ConversationTurn] = field(default_factory=list)
    active_topic: str = "idle"        # 当前活动话题
    topic_turn_count: int = 0         # 当前话题持续的轮数
    max_turns: int = 50               # 最大保留轮数
    last_image_reference: Optional[str] = None  # 最近一次提到的图片
    last_style_reference: Optional[str] = None  # 最近一次提到的风格
    last_prompt_reference: Optional[str] = None  # 最近一次生成的提示词引用


# ============================================================
# 指代消解器
# ============================================================

class ReferenceResolver:
    """
    中文指代消解器

    处理以下指代类型:
      1. 代词: "它"、"他"、"她"、"这个"、"那个"、"这些"
      2. 省略: "那上海呢" → 继承上文意图
      3. 零指代: "换一个" → 继承上文对象
      4. 关联指代: "同样的风格" → 指向上文提到的风格
    """

    # 指代词模式
    PRONOUN_PATTERNS = {
        "image": [
            r"这张[图照片]?", r"那个[图照片]?", r"它",
            r"这[张个]图", r"上面那[张个]", r"刚才那[张个]",
            r"同[一张个]图", r"原图",
        ],
        "style": [
            r"这[种个]风格", r"那[种个]风格", r"同[样种]的风格",
            r"这个", r"那个", r"一样的",
        ],
        "prompt": [
            r"这个提示词", r"那个提示词", r"刚才的提示词",
            r"生成的[那个些]?", r"结果",
        ],
        "intensity": [
            r"这个强度", r"这个力度", r"这种程度",
            r"再.*一点", r"能不能再.*些",
        ],
    }

    # 省略模式的意图继承
    ELLIPSIS_PATTERNS = [
        r"那(.+)呢",     # "那梦核呢" → 继承图片，切换风格
        r"换(.+)吧",     # "换怪核吧" → 继承图片，切换风格
        r"还是(.+)",     # "还是梦核" → 继承图片，切换风格
        r"改成(.+)",     # "改成中式梦核" → 继承图片，切换风格
        r"试试(.+)",     # "试试阈限空间" → 继承图片，切换风格
    ]

    @staticmethod
    def detect_pronouns(user_input: str) -> dict:
        """检测用户输入中的指代词"""
        detected = {}
        for category, patterns in ReferenceResolver.PRONOUN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, user_input):
                    detected[category] = True
                    break
        return detected

    @staticmethod
    def detect_ellipsis(user_input: str) -> Optional[str]:
        """
        检测省略模式，返回提取的参数
        例: "那梦核呢" → "梦核"
        """
        for pattern in ReferenceResolver.ELLIPSIS_PATTERNS:
            match = re.search(pattern, user_input)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def resolve(user_input: str, context: ConversationContext) -> dict:
        """
        综合指代消解

        Args:
            user_input: 用户输入
            context: 当前对话上下文

        Returns:
            {
                "resolved_input": str,         # 消解后的等效输入
                "inherited_image": bool,       # 是否继承了上文图片
                "inherited_style": bool,       # 是否继承了上文风格
                "switched_style_to": str|None, # 如果切换了风格
                "confidence": float,           # 消解置信度
            }
        """
        result = {
            "resolved_input": user_input,
            "inherited_image": False,
            "inherited_style": False,
            "switched_style_to": None,
            "confidence": 1.0,
        }

        # 1. 检测省略模式
        ellipsis_param = ReferenceResolver.detect_ellipsis(user_input)
        if ellipsis_param and context.last_image_reference:
            # "那{style}呢" → 继承图片，切换风格
            result["inherited_image"] = True
            result["switched_style_to"] = ellipsis_param
            result["resolved_input"] = f"把之前的图片转换成{ellipsis_param}风格"
            result["confidence"] = 0.9
            return result

        # 2. 检测指代词
        pronouns = ReferenceResolver.detect_pronouns(user_input)

        if pronouns.get("image") and context.last_image_reference:
            result["inherited_image"] = True
            result["confidence"] = 0.85

        if pronouns.get("style") and context.last_style_reference:
            result["inherited_style"] = True
            result["confidence"] = 0.85

        # 3. 检测零指代（"换一个"、"再试一次" 等）
        zero_reference_patterns = [
            (r"(换一[个种]|再[试来].*|[再重]新.*)", True, True),  # 继承图片和风格
            (r"(再.*一点|调.*一下)", True, True),                   # 继承图片和风格
        ]
        user_lower = user_input.lower()
        for pattern, inherit_img, inherit_style in zero_reference_patterns:
            if re.search(pattern, user_lower):
                if inherit_img and context.last_image_reference:
                    result["inherited_image"] = True
                if inherit_style and context.last_style_reference:
                    result["inherited_style"] = True
                result["confidence"] = 0.8
                break

        return result


# ============================================================
# 对话上下文管理器
# ============================================================

class ConversationContextManager:
    """
    对话上下文管理器

    在每次用户输入时:
      1. 进行指代消解
      2. 更新上下文
      3. 检测话题切换
      4. 管理上下文窗口大小
    """

    def __init__(self, session_id: str, max_turns: int = 50):
        self.context = ConversationContext(
            session_id=session_id,
            max_turns=max_turns,
        )
        self.resolver = ReferenceResolver()

    def process_turn(self, user_input: str, detected_intent: str) -> dict:
        """
        处理一轮新的对话

        Returns:
            dict: 消解后的上下文信息，供 Skill 主逻辑使用
        """
        # 1. 指代消解
        resolution = self.resolver.resolve(user_input, self.context)

        # 2. 检测话题切换
        topic_changed = self._detect_topic_change(user_input, detected_intent)

        # 3. 创建本轮对话记录
        turn = ConversationTurn(
            turn_id=len(self.context.turns) + 1,
            timestamp=time.time(),
            user_input=user_input,
            intent=detected_intent,
            resolved_references=resolution,
        )
        self.context.turns.append(turn)

        # 4. 管理上下文窗口
        self._trim_context()

        # 5. 更新活动话题
        if topic_changed:
            self.context.active_topic = detected_intent
            self.context.topic_turn_count = 1
        else:
            self.context.topic_turn_count += 1

        return resolution

    def update_references(self, image_ref: Optional[str] = None,
                          style_ref: Optional[str] = None,
                          prompt_ref: Optional[str] = None):
        """更新当前上下文的引用"""
        if image_ref:
            self.context.last_image_reference = image_ref
        if style_ref:
            self.context.last_style_reference = style_ref
        if prompt_ref:
            self.context.last_prompt_reference = prompt_ref

        # 同步更新最近一轮对话的上下文快照
        if self.context.turns:
            self.context.turns[-1].context_snapshot = {
                "last_image": self.context.last_image_reference,
                "last_style": self.context.last_style_reference,
                "last_prompt": self.context.last_prompt_reference,
            }

    def get_recent_context_summary(self, n: int = 3) -> str:
        """获取最近 n 轮的对话摘要（用于提示 LLM）"""
        recent_turns = self.context.turns[-n:]
        lines = []
        for turn in recent_turns:
            lines.append(f"User: {turn.user_input}")
            if turn.skill_response_summary:
                lines.append(f"Assistant: {turn.skill_response_summary[:100]}")
        return "\n".join(lines)

    def is_same_topic(self, n: int = 3) -> bool:
        """检查最近 n 轮是否同一话题"""
        return self.context.topic_turn_count >= n

    def _detect_topic_change(self, user_input: str, detected_intent: str) -> bool:
        """检测话题是否切换"""
        # 1. 意图类型变了
        if detected_intent != self.context.active_topic and self.context.active_topic != "idle":
            return True

        # 2. 检测显式的话题重置信号
        reset_keywords = ["从头开始", "换一个主题", "不聊这个了", "新的任务", "清空上下文"]
        if any(kw in user_input for kw in reset_keywords):
            return True

        return False

    def _trim_context(self):
        """裁剪上下文窗口，保留最近 max_turns 轮"""
        if len(self.context.turns) > self.context.max_turns:
            excess = len(self.context.turns) - self.context.max_turns
            self.context.turns = self.context.turns[excess:]
            logger.info(f"Trimmed {excess} old turns from context")

    def clear(self):
        """重置上下文"""
        self.context = ConversationContext(
            session_id=self.context.session_id,
            max_turns=self.context.max_turns,
        )
