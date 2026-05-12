"""
Characters - 人物数据
人物画像、关系图谱
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

from ..base import BaseModel


class RelationshipType(Enum):
    """关系类型"""
    FAMILY = "family"         # 家人
    FRIEND = "friend"         # 朋友
    ROMANTIC = "romantic"     # 爱人
    RIVAL = "rival"           # 对手
    ENEMY = "enemy"           # 敌人
    MENTOR = "mentor"         # 导师
    ACQUAINTANCE = "acquaintance"  # 熟人
    UNKNOWN = "unknown"       # 未知


@dataclass
class Relationship(BaseModel):
    """人物关系"""
    source_id: str = ""        # 源人物ID
    target_id: str = ""        # 目标人物ID
    relationship_type: RelationshipType = RelationshipType.UNKNOWN
    description: str = ""
    intensity: int = 5         # 关系强度 1-10
    first_appearance_chapter: int = 1  # 关系首次出现章节
    key_scenes: List[int] = field(default_factory=list)  # 关系关键场景
    evolution: List[Dict] = field(default_factory=list)  # 关系演变


@dataclass
class Character(BaseModel):
    """人物画像"""
    character_id: str = ""     # 唯一标识（拼音或英文）
    name: str = ""             # 姓名
    alias: List[str] = field(default_factory=list)  # 别名/外号
    age: Optional[int] = None
    gender: str = ""
    appearance: str = ""       # 外貌描述
    personality: str = ""      # 性格特点
    background: str = ""       # 背景故事

    # 核心属性
    goals: List[str] = field(default_factory=list)        # 目标
    fears: List[str] = field(default_factory=list)        # 恐惧
    strengths: List[str] = field(default_factory=list)    # 优点
    weaknesses: List[str] = field(default_factory=list)   # 缺点
    secrets: List[str] = field(default_factory=list)      # 秘密
    values: List[str] = field(default_factory=list)       # 价值观

    # 视觉参考
    visual_tags: List[str] = field(default_factory=list)
    face_description: str = ""
    clothing_style: str = ""
    posture: str = ""

    # 出场信息
    first_appearance_chapter: int = 1
    last_appearance_chapter: Optional[int] = None
    chapters_present: List[int] = field(default_factory=list)  # 出场章节列表
    total_scenes: int = 0

    # 角色定位
    role: str = "supporting"  # protagonist, supporting, antagonist, cameo
    importance: int = 5        # 重要度 1-10

    # 经典语录
    classic_lines: List[str] = field(default_factory=list)

    # 人物弧线
    character_arc: Dict[str, str] = field(default_factory=dict)

    # 关系（仅从该人物视角）
    relationships: Dict[str, Relationship] = field(default_factory=dict)

    def get_display_name(self) -> str:
        """获取显示名"""
        if self.name:
            return self.name
        return self.character_id

    def add_relationship(self, relationship: Relationship):
        """添加关系"""
        self.relationships[relationship.target_id] = relationship

    def get_relationship(self, target_id: str) -> Optional[Relationship]:
        """获取与某人的关系"""
        return self.relationships.get(target_id)


@dataclass
class CharacterGraph(BaseModel):
    """人物关系图（全图视图）"""
    novel_id: str = ""
    characters: List[Character] = field(default_factory=list)
    edges: List[Relationship] = field(default_factory=list)

    def get_character(self, char_id: str) -> Optional[Character]:
        for c in self.characters:
            if c.character_id == char_id:
                return c
        return None

    def get_characters_by_chapter(self, chapter_num: int) -> List[Character]:
        """获取某章出场的所有人物"""
        return [
            c for c in self.characters
            if chapter_num in c.chapters_present
        ]
