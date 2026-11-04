"""
============================================================
长期记忆 — 用户画像管理器 (User Profile Manager)
============================================================
层级: 记忆与状态层 (Layer 5 — Memory & State)
功能:
  1. 持久化用户偏好（习惯的风格、强度、模型等）
  2. 记录使用频率和行为模式
  3. 支持跨会话的记忆读取和更新

持久化方式: JSON 文件存储
存储路径: D:/Dreamcore-skills/memory/data/user_profiles/
============================================================
"""

import json
import os
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构
# ============================================================

@dataclass
class UserPreference:
    """用户偏好设置"""
    # 风格偏好
    favorite_style: Optional[str] = None          # 最常用的风格ID
    style_usage_count: dict = field(default_factory=dict)  # {"dreamcore": 15, "weirdcore": 8}

    # 参数偏好
    default_intensity: str = "standard"
    default_model: str = "midjourney"
    preferred_aspect_ratio: Optional[str] = None
    preferred_language: str = "english"

    # 行为偏好
    output_mode: str = "full"                     # full / prompt_only / comparison
    show_tips: bool = True
    auto_copy_prompt: bool = False

    # 自定义偏好
    custom_keywords: list[str] = field(default_factory=list)  # 用户常用的额外关键词
    blacklisted_styles: list[str] = field(default_factory=list)  # 用户不喜欢的风格


@dataclass
class UserProfile:
    """用户完整画像"""
    user_id: str
    created_at: float
    updated_at: float

    # 偏好
    preferences: UserPreference = field(default_factory=UserPreference)

    # 统计
    total_conversions: int = 0
    total_sessions: int = 0
    last_style_used: Optional[str] = None
    last_access_at: Optional[float] = None

    # 历史记录摘要（不存完整对话，只存统计）
    monthly_usage: dict = field(default_factory=dict)  # {"2026-07": 45}
    top_scenes: list[str] = field(default_factory=list)  # 用户常处理的场景类型

    # 成就/等级
    level: int = 1
    achievements: list[str] = field(default_factory=list)


# ============================================================
# 用户画像管理器
# ============================================================

class UserProfileManager:
    """
    用户画像管理器 — 长期记忆

    能力:
      - 记住用户偏好（风格、强度、模型）
      - 统计使用频率和行为模式
      - 个性化推荐（"你上次用的是梦核，这次还继续吗？"）
      - 跨会话持久化
    """

    PROFILES_DIR = Path("D:/Dreamcore-skills/memory/data/user_profiles")
    PROFILE_FILENAME_TEMPLATE = "{user_id}.json"

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self._profile_path = self.PROFILES_DIR / self.PROFILE_FILENAME_TEMPLATE.format(user_id=user_id)
        self._profile: Optional[UserProfile] = None
        self._ensure_dir()

    def _ensure_dir(self):
        """确保存储目录存在"""
        os.makedirs(self.PROFILES_DIR, exist_ok=True)

    # === 加载/保存 ===

    def load(self) -> UserProfile:
        """加载用户画像（不存在则创建）"""
        if self._profile:
            return self._profile

        if self._profile_path.exists():
            try:
                with open(self._profile_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._profile = UserProfile(
                    user_id=data.get("user_id", self.user_id),
                    created_at=data.get("created_at", time.time()),
                    updated_at=data.get("updated_at", time.time()),
                    preferences=UserPreference(**data.get("preferences", {})),
                    total_conversions=data.get("total_conversions", 0),
                    total_sessions=data.get("total_sessions", 0),
                    last_style_used=data.get("last_style_used"),
                    last_access_at=data.get("last_access_at"),
                    monthly_usage=data.get("monthly_usage", {}),
                    top_scenes=data.get("top_scenes", []),
                    level=data.get("level", 1),
                    achievements=data.get("achievements", []),
                )
                logger.info(f"Profile loaded for user {self.user_id}")
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Corrupted profile, creating new: {e}")
                self._profile = self._create_default()
        else:
            self._profile = self._create_default()
            self.save()

        return self._profile

    def save(self):
        """持久化用户画像"""
        if not self._profile:
            return
        self._profile.updated_at = time.time()
        data = {
            "user_id": self._profile.user_id,
            "created_at": self._profile.created_at,
            "updated_at": self._profile.updated_at,
            "preferences": {
                "favorite_style": self._profile.preferences.favorite_style,
                "style_usage_count": self._profile.preferences.style_usage_count,
                "default_intensity": self._profile.preferences.default_intensity,
                "default_model": self._profile.preferences.default_model,
                "preferred_aspect_ratio": self._profile.preferences.preferred_aspect_ratio,
                "preferred_language": self._profile.preferences.preferred_language,
                "output_mode": self._profile.preferences.output_mode,
                "show_tips": self._profile.preferences.show_tips,
                "auto_copy_prompt": self._profile.preferences.auto_copy_prompt,
                "custom_keywords": self._profile.preferences.custom_keywords,
                "blacklisted_styles": self._profile.preferences.blacklisted_styles,
            },
            "total_conversions": self._profile.total_conversions,
            "total_sessions": self._profile.total_sessions,
            "last_style_used": self._profile.last_style_used,
            "last_access_at": self._profile.last_access_at,
            "monthly_usage": self._profile.monthly_usage,
            "top_scenes": self._profile.top_scenes,
            "level": self._profile.level,
            "achievements": self._profile.achievements,
        }
        os.makedirs(self._profile_path.parent, exist_ok=True)
        with open(self._profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Profile saved for user {self.user_id}")

    def _create_default(self) -> UserProfile:
        return UserProfile(
            user_id=self.user_id,
            created_at=time.time(),
            updated_at=time.time(),
        )

    # === 偏好管理 ===

    def get_preference(self, key: str, default=None):
        """获取单个偏好值"""
        profile = self.load()
        return getattr(profile.preferences, key, default)

    def set_preference(self, key: str, value):
        """设置单个偏好值"""
        profile = self.load()
        if hasattr(profile.preferences, key):
            setattr(profile.preferences, key, value)
            self.save()

    def update_style_usage(self, style_id: str):
        """记录一次风格使用"""
        profile = self.load()
        profile.preferences.style_usage_count[style_id] = \
            profile.preferences.style_usage_count.get(style_id, 0) + 1
        profile.last_style_used = style_id
        profile.total_conversions += 1
        profile.last_access_at = time.time()

        # 更新月度统计
        month_key = time.strftime("%Y-%m")
        profile.monthly_usage[month_key] = profile.monthly_usage.get(month_key, 0) + 1

        # 挖掘最常用风格
        if profile.preferences.style_usage_count:
            profile.preferences.favorite_style = max(
                profile.preferences.style_usage_count,
                key=profile.preferences.style_usage_count.get,
            )

        # 更新等级
        profile.level = min(10, 1 + profile.total_conversions // 50)

        self.save()

    # === 个性化推荐 ===

    def get_personalized_recommendations(self) -> list[str]:
        """
        基于用户历史推荐风格
        - 经常用的放在前面
        - 相关的推荐在中间
        - 排除黑名单
        """
        profile = self.load()
        ranked = []

        # 1. 用户最常用的优先
        if profile.preferences.favorite_style:
            ranked.append(profile.preferences.favorite_style)

        # 2. 相关的推荐风格
        related_map = {
            "dreamcore": ["chinese_dreamcore", "kidcore", "liminal_space"],
            "weirdcore": ["backrooms", "traumacore", "liminal_space"],
            "liminal_space": ["backrooms", "poolcore"],
            "traumacore": ["weirdcore", "chinese_dreamcore"],
            "backrooms": ["liminal_space", "weirdcore"],
            "kidcore": ["dreamcore", "webcore"],
            "poolcore": ["liminal_space", "dreamcore"],
            "webcore": ["kidcore", "hypnocore"],
            "hypnocore": ["weirdcore", "webcore"],
            "chinese_dreamcore": ["dreamcore", "traumacore"],
        }
        last_style = profile.last_style_used
        if last_style and last_style in related_map:
            for related in related_map[last_style]:
                if related not in ranked:
                    ranked.append(related)

        # 3. 剩余的按字母排序
        from core.style_matcher import StyleMatcher
        all_styles = StyleMatcher.get_style_ids()
        for sid in all_styles:
            if sid not in ranked and sid not in profile.preferences.blacklisted_styles:
                ranked.append(sid)

        return ranked[:5]  # 至多返回5个

    def get_greeting(self) -> str:
        """生成个性化问候语"""
        profile = self.load()
        if profile.total_conversions == 0:
            return "欢迎使用梦核风格转换器！请上传一张图片，选择您喜欢的风格即可开始。"
        last_style = profile.last_style_used
        total = profile.total_conversions
        if last_style:
            from core.style_matcher import StyleMatcher
            styles = StyleMatcher.get_all_styles_summary()
            style_name = next(
                (s["name_zh"] for s in styles if s["id"] == last_style), last_style
            )
            return (
                f"欢迎回来！您已累计转换 {total} 次，上次使用的是「{style_name}」。"
                f"今天想试试什么风格呢？"
            )
        return f"欢迎回来！您已累计转换 {total} 次。今天想试试什么风格呢？"
