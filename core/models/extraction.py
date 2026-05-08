"""
Extraction - 知识萃取数据
章节分析、实体提取、伏笔识别
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from .base import BaseModel


@dataclass
class ExtractedEntity(BaseModel):
    """提取出的实体基类"""
    entity_type: str = ""      # "character" | "location" | "foreshadowing" | "item"
    name: str = ""
    description: str = ""
    source_chapter: int = 1
    confidence: float = 0.8    # 置信度


@dataclass
class ExtractedCharacter(ExtractedEntity):
    """提取出的新人物"""
    entity_type: str = "character"
    appearance: str = ""
    personality: str = ""
    role: str = "supporting"   # "protagonist" | "supporting" | "antagonist" | "cameo"
    relationships: List[Dict] = field(default_factory=list)


@dataclass
class ExtractedForeshadowing(ExtractedEntity):
    """提取出的伏笔"""
    entity_type: str = "foreshadowing"
    foreshadowing_type: str = "plot"   # "plot" | "character" | "world"
    expected_payoff: str = ""          # 预期回收方式
    urgency: str = "medium"            # "low" | "medium" | "high"
    resolved: bool = False
    resolved_chapter: Optional[int] = None


@dataclass
class ExtractedLocation(ExtractedEntity):
    """提取出的新地点"""
    entity_type: str = "location"
    location_type: str = "place"       # "place" | "building" | "region" | "world"
    status: str = ""                   # 地点状态
    controlling_faction: str = ""


@dataclass
class CharacterUpdate(BaseModel):
    """角色状态变更"""
    character_name: str = ""
    update_type: str = ""         # "state" | "relationship" | "goal" | "death" | "injury"
    old_value: str = ""
    new_value: str = ""
    description: str = ""


@dataclass
class WorldUpdate(BaseModel):
    """世界设定变更"""
    update_type: str = ""         # "location_status" | "faction_change" | "rule_add"
    target: str = ""              # 变更目标（地点名/势力名等）
    old_value: str = ""
    new_value: str = ""
    description: str = ""


@dataclass
class ChapterAnalysis(BaseModel):
    """单章节分析结果"""
    novel_id: str = ""
    chapter: int = 1
    summary: str = ""                # 章节摘要
    events: List[Dict] = field(default_factory=list)        # 关键事件
    new_characters: List[ExtractedCharacter] = field(default_factory=list)
    new_locations: List[ExtractedLocation] = field(default_factory=list)
    new_foreshadowings: List[ExtractedForeshadowing] = field(default_factory=list)
    character_updates: List[CharacterUpdate] = field(default_factory=list)
    world_updates: List[WorldUpdate] = field(default_factory=list)
    resolved_foreshadowings: List[str] = field(default_factory=list)  # 已回收伏笔名
    key_quotes: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    extracted_at: str = ""

    def get_new_entity_count(self) -> int:
        """获取新实体数量"""
        return (
            len(self.new_characters)
            + len(self.new_locations)
            + len(self.new_foreshadowings)
        )

    def get_unresolved_foreshadowings(self) -> List[ExtractedForeshadowing]:
        """获取未回收的伏笔"""
        return [f for f in self.new_foreshadowings if not f.resolved]
