"""
EpisodeCard 数据模型
===================
Pydantic v2 严格校验分集卡点数据结构，含 4 维评分（0-10）。
"""

from pydantic import BaseModel, Field


class EpisodeCard(BaseModel):
    """单集卡点：核心剧情 + 4 维量化评分"""

    episode_num: int = Field(..., ge=1, description="集数编号")
    title: str = Field(default="", description="本集暂定标题")
    summary: str = Field(default="", description="核心剧情概要，节奏紧凑")
    cliffhanger: str = Field(default="", description="结尾悬念留白 / 强力钩子")

    # ── 四维评分（0-10） ──
    conflict_intensity: int = Field(
        default=5, ge=0, le=10, description="冲突烈度评分"
    )
    pleasure_index: int = Field(
        default=5, ge=0, le=10, description="爽感爆发度评分"
    )
    hook_strength: int = Field(
        default=5, ge=0, le=10, description="悬念钩子度评分"
    )
    emotional_resonance: int = Field(
        default=5, ge=0, le=10, description="情感共鸣度评分"
    )

    @property
    def avg_score(self) -> float:
        """四维平均分"""
        scores = [
            self.conflict_intensity,
            self.pleasure_index,
            self.hook_strength,
            self.emotional_resonance,
        ]
        return sum(scores) / len(scores)

    @property
    def is_weak(self) -> bool:
        """平均分低于 5 视为弱集"""
        return self.avg_score < 5.0

    @property
    def is_climax(self) -> bool:
        """是否为高潮集（平均分 ≥ 8）"""
        return self.avg_score >= 8.0
