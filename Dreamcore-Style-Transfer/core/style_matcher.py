"""
============================================================
风格匹配与推荐引擎 (Style Matcher & Recommender)
============================================================
层级: 核心处理逻辑层 (Layer 3 — Logic & Orchestration)
功能:
  1. 根据用户输入精确匹配风格
  2. 根据图片内容自动推荐最佳风格
  3. 根据用户情绪/场景描述推荐风格
  4. 处理风格歧义消解

架构位置: Skill Pipeline Stage 4 — Style Matching
============================================================
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# 风格元数据 (从 style_recipes.yaml 硬编码一份快速索引)
# ============================================================

@dataclass
class StyleMeta:
    style_id: str
    name_zh: str
    name_en: str
    aliases: list[str]
    description: str
    core_keywords: str
    color_palette: dict
    mood_tags: list[str]
    scene_tags: list[str]
    match_score: float = 0.0  # 推荐时计算


# 风格索引表（快速查找）
STYLE_INDEX: dict[str, StyleMeta] = {
    "dreamcore": StyleMeta(
        style_id="dreamcore",
        name_zh="经典梦核",
        name_en="Dreamcore",
        aliases=["梦核", "dreamcore", "dream core", "梦核风", "梦核风格"],
        description="怀旧超现实主义梦境景观",
        core_keywords="nostalgic surreal dreamscape",
        color_palette={"primary": ["warm yellow", "soft pink", "faded orange"]},
        mood_tags=["nostalgic", "wistful", "familiar", "strange", "comforting", "eerie"],
        scene_tags=["indoor", "outdoor", "architecture", "urban", "nature"],
    ),
    "weirdcore": StyleMeta(
        style_id="weirdcore",
        name_zh="怪核",
        name_en="Weirdcore",
        aliases=["怪核", "weirdcore", "weird core", "怪诞核"],
        description="令人不安的混乱美学",
        core_keywords="unsettling disoriented chaotic",
        color_palette={"primary": ["acid green", "blood red", "deep purple"]},
        mood_tags=["anxiety", "dread", "confusion", "uncanny", "disturbing"],
        scene_tags=["indoor", "urban", "night", "portrait"],
    ),
    "liminal_space": StyleMeta(
        style_id="liminal_space",
        name_zh="阈限空间",
        name_en="Liminal Space",
        aliases=["阈限空间", "liminal space", "liminal", "阈限", "过渡空间"],
        description="空无一人的过渡空间",
        core_keywords="transitional space in-between liminal",
        color_palette={"primary": ["fluorescent white", "beige", "muted yellow"]},
        mood_tags=["solitude", "stillness", "unsettling", "empty", "quiet"],
        scene_tags=["indoor", "architecture", "urban", "night"],
    ),
    "traumacore": StyleMeta(
        style_id="traumacore",
        name_zh="伤核",
        name_en="Traumacore",
        aliases=["伤核", "traumacore", "trauma core", "创伤核"],
        description="可爱与破碎的并置",
        core_keywords="trauma pain vulnerability",
        color_palette={"primary": ["soft pink", "baby blue", "cream"]},
        mood_tags=["melancholic", "fragile", "sad", "vulnerable", "hurt"],
        scene_tags=["indoor", "portrait"],
    ),
    "backrooms": StyleMeta(
        style_id="backrooms",
        name_zh="后室",
        name_en="The Backrooms",
        aliases=["后室", "backrooms", "the backrooms", "幕后"],
        description="无尽的被困空间",
        core_keywords="infinite trapped eerie backrooms",
        color_palette={"primary": ["yellow", "beige", "off-white"]},
        mood_tags=["fear", "trapped", "claustrophobic", "endless", "being watched"],
        scene_tags=["indoor", "architecture"],
    ),
    "kidcore": StyleMeta(
        style_id="kidcore",
        name_zh="童年核",
        name_en="Kidcore",
        aliases=["童年核", "kidcore", "kid core", "童核", "儿童核"],
        description="90年代童年的色彩爆炸",
        core_keywords="childhood innocence wonder nostalgia",
        color_palette={"primary": ["bright red", "electric blue", "sunny yellow", "hot pink"]},
        mood_tags=["nostalgic", "playful", "innocent", "bittersweet", "happy"],
        scene_tags=["indoor", "outdoor", "portrait"],
    ),
    "poolcore": StyleMeta(
        style_id="poolcore",
        name_zh="池核",
        name_en="Poolcore",
        aliases=["池核", "poolcore", "pool core", "泳池核", "水核"],
        description="空无一人的游泳池阈限美学",
        core_keywords="aquatic liminal pool water",
        color_palette={"primary": ["pool blue", "white", "aquamarine"]},
        mood_tags=["serene", "eerie", "peaceful", "isolated", "calm"],
        scene_tags=["indoor", "outdoor", "architecture"],
    ),
    "webcore": StyleMeta(
        style_id="webcore",
        name_zh="网核",
        name_en="Webcore / Internetcore",
        aliases=["网核", "webcore", "internetcore", "网络核"],
        description="早期互联网的像素化怀旧",
        core_keywords="early internet nostalgia digital retro",
        color_palette={"primary": ["web safe blue", "#00FF00 green", "hot pink"]},
        mood_tags=["nostalgic", "digital", "lonely", "retro", "geeky"],
        scene_tags=["indoor", "abstract"],
    ),
    "hypnocore": StyleMeta(
        style_id="hypnocore",
        name_zh="催眠核",
        name_en="Hypnocore",
        aliases=["催眠核", "hypnocore", "hypno core", "迷幻核"],
        description="催眠漩涡与视错觉的迷失体验",
        core_keywords="hypnotic trance psychedelic disorienting",
        color_palette={"primary": ["psychedelic purple", "electric yellow", "magenta"]},
        mood_tags=["psychedelic", "disorienting", "trance", "lost", "trippy"],
        scene_tags=["abstract"],
    ),
    "chinese_dreamcore": StyleMeta(
        style_id="chinese_dreamcore",
        name_zh="中式梦核",
        name_en="Chinese Dreamcore",
        aliases=["中式梦核", "chinese dreamcore", "中国梦核", "电子乡愁"],
        description="中国90-00年代的电子乡愁",
        core_keywords="Chinese nostalgia electronic homesickness",
        color_palette={"primary": ["warm yellow", "faded red", "cream white"]},
        mood_tags=["nostalgic", "homesick", "melancholic", "collective", "warm"],
        scene_tags=["outdoor", "urban", "nature", "architecture", "indoor"],
    ),
}


# ============================================================
# 风格匹配器
# ============================================================

class StyleMatcher:
    """
    多策略风格匹配引擎

    匹配策略（按优先级）：
      1. 精确别名匹配
      2. 模糊关键词匹配
      3. 中文语义匹配
      4. 情绪映射匹配
      5. 场景映射匹配
    """

    @staticmethod
    def match_exact(user_input: str) -> Optional[str]:
        """
        策略1: 精确别名匹配
        遍历所有风格的别名列表，精确/包含匹配
        """
        user_lower = user_input.lower().strip()
        for style_id, meta in STYLE_INDEX.items():
            for alias in meta.aliases:
                if alias.lower() in user_lower or user_lower in alias.lower():
                    return style_id
        return None

    @staticmethod
    def match_fuzzy(user_input: str) -> list[tuple[str, float]]:
        """
        策略2: 模糊匹配返回候选列表（按匹配度排序）
        """
        user_lower = user_input.lower().strip()
        candidates = []

        for style_id, meta in STYLE_INDEX.items():
            score = 0.0
            # 核心关键词匹配
            if any(kw in user_lower for kw in meta.core_keywords.lower().split()):
                score += 0.4
            # 情绪标签匹配
            for mood in meta.mood_tags:
                if mood in user_lower:
                    score += 0.3
            # 场景标签匹配
            for scene in meta.scene_tags:
                if scene in user_lower:
                    score += 0.2
            # 描述词匹配
            desc_words = set(meta.description.lower().split())
            input_words = set(user_lower.split())
            overlap = desc_words & input_words
            if overlap:
                score += 0.1 * len(overlap) / max(len(desc_words), 1)

            if score > 0:
                candidates.append((style_id, min(score, 1.0)))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    @staticmethod
    def recommend_by_mood(mood_description: str) -> list[tuple[str, float]]:
        """
        策略3: 根据用户描述的情绪推荐风格
        """
        mood_mapping = {
            "温暖": ["dreamcore", "kidcore", "chinese_dreamcore"],
            "怀念": ["dreamcore", "kidcore", "chinese_dreamcore", "webcore"],
            "诡异": ["weirdcore", "liminal_space", "backrooms"],
            "不安": ["weirdcore", "backrooms", "liminal_space"],
            "孤独": ["liminal_space", "poolcore", "webcore"],
            "忧郁": ["traumacore", "chinese_dreamcore"],
            "恐惧": ["backrooms", "weirdcore"],
            "梦幻": ["dreamcore", "hypnocore", "poolcore"],
            "快乐": ["kidcore", "dreamcore"],
            "迷幻": ["hypnocore", "weirdcore"],
            "安静": ["poolcore", "liminal_space", "chinese_dreamcore"],
            "疯狂": ["weirdcore", "hypnocore"],
            "伤": ["traumacore", "chinese_dreamcore"],
            "暗黑": ["weirdcore", "backrooms"],
            "清晰": ["dreamcore", "kidcore", "chinese_dreamcore"],
            "模糊": ["dreamcore", "chinese_dreamcore", "weirdcore"],
        }

        matched_styles: dict[str, float] = {}
        for mood_keyword, style_list in mood_mapping.items():
            if mood_keyword in mood_description:
                for sid in style_list:
                    matched_styles[sid] = matched_styles.get(sid, 0) + 0.3

        # 排序并返回
        ranked = sorted(matched_styles.items(), key=lambda x: x[1], reverse=True)
        return ranked[:5]  # 至多返回5个

    @staticmethod
    def recommend_by_scene(scene_type: str) -> list[tuple[str, float]]:
        """
        策略4: 根据场景类型推荐风格
        """
        scene_mapping = {
            "indoor": ["backrooms", "liminal_space", "traumacore"],
            "outdoor": ["dreamcore", "chinese_dreamcore", "kidcore"],
            "urban": ["chinese_dreamcore", "weirdcore", "liminal_space"],
            "nature": ["dreamcore", "poolcore", "kidcore"],
            "portrait": ["weirdcore", "traumacore", "dreamcore"],
            "architecture": ["liminal_space", "backrooms", "chinese_dreamcore"],
            "night": ["weirdcore", "liminal_space", "dreamcore"],
            "day": ["dreamcore", "kidcore", "poolcore"],
            "abstract": ["hypnocore", "webcore", "weirdcore"],
        }

        style_list = scene_mapping.get(scene_type, ["dreamcore", "weirdcore", "liminal_space"])
        return [(sid, 0.5 - i * 0.1) for i, sid in enumerate(style_list)]

    @staticmethod
    def resolve(user_input: str) -> dict:
        """
        综合解析：尝试多种策略确定用户想要的风格

        Returns:
            {
                "resolved": bool,           # 是否成功解析
                "style_id": str | None,    # 确定的风格ID
                "confidence": float,        # 置信度
                "candidates": list,         # 备选列表
                "strategy_used": str,       # 使用的策略
                "needs_clarification": bool # 是否需要用户澄清
            }
        """
        # 1. 精确匹配
        exact = StyleMatcher.match_exact(user_input)
        if exact:
            return {
                "resolved": True,
                "style_id": exact,
                "confidence": 1.0,
                "candidates": [exact],
                "strategy_used": "exact_match",
                "needs_clarification": False,
            }

        # 2. 模糊匹配
        fuzzy = StyleMatcher.match_fuzzy(user_input)
        if fuzzy and fuzzy[0][1] >= 0.5:
            return {
                "resolved": True,
                "style_id": fuzzy[0][0],
                "confidence": fuzzy[0][1],
                "candidates": [s[0] for s in fuzzy[:3]],
                "strategy_used": "fuzzy_match",
                "needs_clarification": False,
            }

        # 3. 尝试情绪匹配
        mood_recs = StyleMatcher.recommend_by_mood(user_input)
        if mood_recs:
            return {
                "resolved": True,
                "style_id": mood_recs[0][0],
                "confidence": mood_recs[0][1],
                "candidates": [s[0] for s in mood_recs],
                "strategy_used": "mood_recommend",
                "needs_clarification": len(mood_recs) > 3,  # 候选太多时需要澄清
            }

        # 4. 无法确定
        return {
            "resolved": False,
            "style_id": None,
            "confidence": 0.0,
            "candidates": [],
            "strategy_used": "none",
            "needs_clarification": True,
        }

    @staticmethod
    def get_all_styles_summary() -> list[dict]:
        """获取所有风格的简要信息（用于展示风格列表）"""
        summaries = []
        for style_id, meta in STYLE_INDEX.items():
            summaries.append({
                "id": style_id,
                "name_zh": meta.name_zh,
                "name_en": meta.name_en,
                "description": meta.description,
                "mood_tags": meta.mood_tags[:3],
            })
        return summaries

    @staticmethod
    def get_style_ids() -> list[str]:
        """获取所有风格 ID 列表"""
        return list(STYLE_INDEX.keys())
