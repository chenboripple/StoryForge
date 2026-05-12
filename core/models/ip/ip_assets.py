"""
IP Assets - IP 生成数据
人物 IP、关系边、场景设定、衍生设定、Story Bible
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..base import BaseModel


@dataclass
class CharacterIP(BaseModel):
    """人物 IP 档案"""
    character_id: str = ""    # 拼音+下划线，如"zhang_san"
    name: str = ""
    role: str = "supporting"  # "protagonist" | "supporting" | "antagonist" | "cameo"
    appearance: Dict[str, str] = field(default_factory=dict)
    # appearance 结构：{ "basic": "", "face": "", "clothing": "", "posture": "", "visual_tags": "" }
    personality: Dict = field(default_factory=dict)
    # personality 结构：{ "core": "", "traits": [], "strengths": [], "weaknesses": [], "fears": [], "motivations": [] }
    background: str = ""
    relationships: List[Dict] = field(default_factory=list)
    # relationships: [{"name": "", "relation": "", "description": ""}]
    character_arc: Dict[str, str] = field(default_factory=dict)
    # character_arc: {"start": "", "turning_points": [], "end": ""}
    famous_quotes: List[str] = field(default_factory=list)
    key_scenes: List[Dict] = field(default_factory=list)
    # key_scenes: [{"chapter": 1, "description": ""}]
    tags: List[str] = field(default_factory=list)
    first_appearance: int = 0
    last_appearance: int = 0
    total_scenes: int = 0


@dataclass
class RelationshipEdge(BaseModel):
    """关系边（用于图谱）"""
    source: str = ""            # 源角色 ID
    target: str = ""            # 目标角色 ID
    relation_type: str = ""     # "friend" | "enemy" | "family" | "romantic" | "mentor" | "rival"
    description: str = ""
    intensity: int = 5          # 关系强度 1-10
    evolution: List[Dict] = field(default_factory=list)
    # evolution: [{"chapter": 1, "change": ""}]


@dataclass
class SceneSetting(BaseModel):
    """场景设定"""
    scene_id: str = ""
    name: str = ""
    location: str = ""
    chapter: int = 1
    description: str = ""
    atmosphere: str = ""              # 氛围描述
    visual_references: List[str] = field(default_factory=list)  # 视觉参考关键词
    significance: str = ""            # 场景重要性说明
    props_in_scene: List[str] = field(default_factory=list)     # 关键道具
    characters_present: List[str] = field(default_factory=list) # 在场角色


@dataclass
class DerivedSetting(BaseModel):
    """衍生设定"""
    setting_type: str = ""     # "item" | "spell" | "faction" | "creature" | "rule"
    name: str = ""
    description: str = ""
    origin: str = ""           # 来源说明
    properties: Dict = field(default_factory=dict)
    related_characters: List[str] = field(default_factory=list)
    first_appearance: int = 0
    tags: List[str] = field(default_factory=list)


@dataclass
class StoryBible(BaseModel):
    """Story Bible"""
    title: str = ""
    version: str = "1.0"
    created_at: str = ""
    updated_at: str = ""
    logline: str = ""          # 一句话梗概
    core_concept: str = ""     # 核心概念
    themes: List[str] = field(default_factory=list)
    tone: str = ""
    target_audience: str = ""
    world_overview: str = ""
    characters: List[CharacterIP] = field(default_factory=list)
    relationships: List[RelationshipEdge] = field(default_factory=list)
    key_scenes: List[SceneSetting] = field(default_factory=list)
    derived_settings: List[DerivedSetting] = field(default_factory=list)
    chapter_summaries: Dict[int, str] = field(default_factory=dict)

    def get_character(self, character_id: str) -> Optional[CharacterIP]:
        """按 ID 获取角色 IP"""
        for c in self.characters:
            if c.character_id == character_id:
                return c
        return None

    def get_character_by_name(self, name: str) -> Optional[CharacterIP]:
        """按名称获取角色 IP"""
        for c in self.characters:
            if c.name == name:
                return c
        return None

    def get_scenes_for_chapter(self, chapter: int) -> List[SceneSetting]:
        """获取某章的场景"""
        return [s for s in self.key_scenes if s.chapter == chapter]
