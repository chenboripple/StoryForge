"""
World Setting - 世界观设定
世界设定、时间线、地点、势力
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

from .base import BaseModel


class LocationType(Enum):
    """地点类型"""
    PLACE = "place"           # 普通地点
    BUILDING = "building"     # 建筑
    REGION = "region"         # 区域
    WORLD = "world"           # 世界/星球
    REALM = "realm"           # 位面/境界


class FactionType(Enum):
    """势力类型"""
    GOVERNMENT = "government"      # 官方组织
    RELIGION = "religion"          # 宗教组织
    ACADEMY = "academy"            # 学术机构
    GUILD = "guild"                # 行会/公会
    FAMILY = "family"              # 家族
    GANG = "gang"                  # 帮派
    OTHER = "other"                # 其他


@dataclass
class TimelineEvent(BaseModel):
    """时间线事件"""
    event_id: str = ""
    chapter: int = 0
    timestamp: str = ""             # 故事内时间（如"末日历47年3月"）
    event_type: str = "plot"        # "plot" | "character" | "world"
    description: str = ""
    characters_involved: List[str] = field(default_factory=list)
    location: str = ""
    significance: str = ""          # 重要性说明
    foreshadowing_paid: List[str] = field(default_factory=list)  # 回收的伏笔
    foreshadowing_set: List[str] = field(default_factory=list)   # 埋下的伏笔


@dataclass
class Location(BaseModel):
    """地点设定"""
    location_id: str = ""
    name: str = ""
    location_type: LocationType = LocationType.PLACE
    description: str = ""
    appearance: str = ""            # 外观描述
    atmosphere: str = ""            # 氛围
    status: str = ""                # 状态（如"被毁"、"被占"）
    controlling_faction: str = ""   # 控制势力
    parent_location: Optional[str] = None  # 上级地点（如城市属于某个国家）
    first_appearance: int = 1
    last_appearance: Optional[int] = None
    chapters_present: List[int] = field(default_factory=list)
    visual_tags: List[str] = field(default_factory=list)
    related_events: List[str] = field(default_factory=list)  # 相关事件ID
    properties: Dict[str, str] = field(default_factory=dict)  # 自定义属性


@dataclass
class Faction(BaseModel):
    """势力设定"""
    faction_id: str = ""
    name: str = ""
    faction_type: FactionType = FactionType.OTHER
    description: str = ""
    ideology: str = ""              # 理念/宗旨
    headquarters: str = ""          # 总部地点
    leader: str = ""                # 领袖
    notable_members: List[str] = field(default_factory=list)
    allies: List[str] = field(default_factory=list)    # 盟友势力ID
    enemies: List[str] = field(default_factory=list)   # 敌对势力ID
    status: str = ""                # 状态（如"繁荣"、"衰落"、"灭亡"）
    first_appearance: int = 1
    last_appearance: Optional[int] = None
    chapters_present: List[int] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)  # 标识/符号
    properties: Dict[str, str] = field(default_factory=dict)


@dataclass
class WorldSetting(BaseModel):
    """世界观设定总集"""
    world_id: str = ""
    name: str = ""
    overview: str = ""              # 世界观总览
    history: str = ""               # 历史背景
    rules: List[str] = field(default_factory=list)  # 世界规则（如物理法则、法术规则）
    timeline: List[TimelineEvent] = field(default_factory=list)
    locations: Dict[str, Location] = field(default_factory=dict)
    factions: Dict[str, Faction] = field(default_factory=dict)
    cultures: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    economies: List[str] = field(default_factory=list)
    politics: List[str] = field(default_factory=list)
    magic_system: str = ""          # 魔法/修炼体系
    technology_level: str = ""      # 科技水平
    visual_style: str = ""          # 视觉风格
    themes: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def add_location(self, location: Location):
        """添加地点"""
        self.locations[location.location_id] = location

    def add_faction(self, faction: Faction):
        """添加势力"""
        self.factions[faction.faction_id] = faction

    def add_event(self, event: TimelineEvent):
        """添加时间线事件"""
        self.timeline.append(event)

    def get_locations_by_chapter(self, chapter: int) -> List[Location]:
        """获取某章出现的地点"""
        return [
            loc for loc in self.locations.values()
            if chapter in loc.chapters_present
        ]

    def get_factions_by_chapter(self, chapter: int) -> List[Faction]:
        """获取某章出现的势力"""
        return [
            fac for fac in self.factions.values()
            if chapter in fac.chapters_present
        ]
