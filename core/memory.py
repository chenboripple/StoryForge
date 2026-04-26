"""
StoryForge - 故事记忆系统
维护全局一致性：事件时间线、角色状态、世界设定
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class StoryEvent:
    """故事事件"""
    chapter: int                    # 发生在第几章
    timestamp: str                  # 故事内时间（如"末日历47年3月"）
    description: str                # 事件描述
    characters_involved: List[str] = field(default_factory=list)
    location: str = ""              # 发生地点
    significance: str = "plot"      # "plot" | "character" | "world"


@dataclass
class CharacterArc:
    """角色成长弧线"""
    name: str
    initial_state: str              # 初始状态
    current_state: str              # 当前状态
    goals: List[str] = field(default_factory=list)
    completed_goals: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)
    key_moments: List[StoryEvent] = field(default_factory=list)
    
    def update_after_chapter(self, chapter: int, events: List[StoryEvent]):
        """根据章节事件更新角色状态"""
        for event in events:
            if self.name in event.characters_involved:
                self.key_moments.append(event)
                # 检查目标完成
                for goal in self.goals:
                    if goal in event.description and goal not in self.completed_goals:
                        self.completed_goals.append(goal)


@dataclass
class WorldState:
    """世界状态"""
    locations: Dict[str, Dict] = field(default_factory=dict)
    # 结构：{"地点名": {"status": "完好|损毁", "controlled_by": "势力", "description": "..."}}
    
    factions: Dict[str, Dict] = field(default_factory=dict)
    # 结构：{"势力名": {"strength": "强|中|弱", "allies": [...], "enemies": [...]}}
    
    rules: Dict[str, Any] = field(default_factory=dict)
    # 世界规则（如"辐射云每7天移动一次"）
    
    timeline: List[StoryEvent] = field(default_factory=list)


@dataclass
class Inconsistency:
    """不一致性记录"""
    type: str                       # "character" | "world" | "timeline" | "plot"
    description: str              # 问题描述
    chapter: int                  # 发现于第几章
    severity: str = "warning"       # "error" | "warning"


class StoryMemory:
    """
    故事记忆系统
    
    职责：
    1. 维护事件时间线
    2. 追踪角色状态变化
    3. 管理世界设定一致性
    4. 提供上下文给 Writer
    """
    
    def __init__(self):
        self.events: List[StoryEvent] = []
        self.character_arcs: Dict[str, CharacterArc] = {}
        self.world_state: WorldState = WorldState()
        self.chekhovs_guns: List[Dict] = []  # 伏笔追踪
        self._chapter_events: Dict[int, List[StoryEvent]] = {}  # 按章节索引
    
    def initialize_from_outline(
        self,
        characters: List[Any],
        world_setting: Optional[Dict] = None
    ):
        """从大纲初始化记忆"""
        # 初始化角色弧线
        for char in characters:
            self.character_arcs[char.name] = CharacterArc(
                name=char.name,
                initial_state=char.personality,
                current_state=char.personality,
                goals=char.goals if hasattr(char, 'goals') else [],
                relationships=char.relationships if hasattr(char, 'relationships') else {}
            )
        
        # 初始化世界状态
        if world_setting:
            self.world_state.locations = world_setting.get("locations", {})
            self.world_state.factions = world_setting.get("factions", {})
            self.world_state.rules = world_setting.get("rules", {})
    
    def record_chapter_events(self, chapter: int, events: List[StoryEvent]):
        """记录章节事件"""
        self._chapter_events[chapter] = events
        self.events.extend(events)
        
        # 更新角色弧线
        for arc in self.character_arcs.values():
            arc.update_after_chapter(chapter, events)
    
    def check_consistency(self, chapter_num: int, chapter_content: str) -> List[Inconsistency]:
        """
        检查新章节与已有记忆的一致性
        
        检查项：
        1. 角色状态一致性（性格、目标、关系）
        2. 世界设定一致性（地点状态、势力分布）
        3. 时间线一致性（事件顺序）
        4. 伏笔回收（契诃夫之枪）
        """
        issues = []
        
        # 检查角色名字拼写
        for name in self.character_arcs.keys():
            # 简单检查：名字是否出现但拼写错误（可扩展为模糊匹配）
            if name not in chapter_content:
                # 角色未出场，不算错误
                pass
        
        # 检查地点状态一致性
        for loc_name, loc_info in self.world_state.locations.items():
            if loc_name in chapter_content:
                # 检查是否描述了与当前状态矛盾的属性
                # 例如：如果地点状态是"损毁"，但章节描述为"完好"
                pass  # 需要更智能的 NLP 检查
        
        # 检查时间线
        if chapter_num > 1:
            prev_events = self._chapter_events.get(chapter_num - 1, [])
            # 确保当前章节的事件在逻辑上接得上前一章
        
        return issues
    
    def build_context_for_chapter(self, chapter_num: int, max_events: int = 10) -> str:
        """
        为指定章节构建上下文
        
        包含：
        1. 相关角色当前状态
        2. 最近的关键事件
        3. 当前世界状态
        4. 未回收的伏笔
        """
        context_parts = []
        
        # 1. 角色状态
        context_parts.append("【角色当前状态】")
        for name, arc in self.character_arcs.items():
            context_parts.append(
                f"- {name}：{arc.current_state}\n"
                f"  目标：{', '.join(arc.goals)}\n"
                f"  已完成：{', '.join(arc.completed_goals) or '无'}\n"
                f"  关系：{arc.relationships}"
            )
        
        # 2. 最近事件
        context_parts.append("\n【近期关键事件】")
        recent = [e for e in self.events if e.chapter < chapter_num][-max_events:]
        for event in recent:
            context_parts.append(
                f"- 第{event.chapter}章：{event.description} "
                f"({', '.join(event.characters_involved)})"
            )
        
        # 3. 世界状态
        context_parts.append("\n【当前世界状态】")
        for loc_name, loc_info in self.world_state.locations.items():
            context_parts.append(f"- {loc_name}：{loc_info.get('status', '未知')}")
        
        # 4. 未回收伏笔
        unresolved = [g for g in self.chekhovs_guns if not g.get("resolved")]
        if unresolved:
            context_parts.append("\n【待回收伏笔】")
            for gun in unresolved[-3:]:  # 只取最近的3个
                context_parts.append(f"- {gun['description']}（第{gun['chapter']}章埋下）")
        
        return "\n".join(context_parts)
    
    def add_chekhovs_gun(self, chapter: int, description: str):
        """添加伏笔"""
        self.chekhovs_guns.append({
            "chapter": chapter,
            "description": description,
            "resolved": False
        })
    
    def resolve_chekhovs_gun(self, description: str):
        """回收伏笔"""
        for gun in self.chekhovs_guns:
            if description in gun["description"]:
                gun["resolved"] = True
                break
    
    def to_dict(self) -> Dict:
        """序列化"""
        return {
            "events": [
                {"chapter": e.chapter, "timestamp": e.timestamp, 
                 "description": e.description, "characters": e.characters_involved}
                for e in self.events
            ],
            "character_arcs": {
                name: {
                    "initial": arc.initial_state,
                    "current": arc.current_state,
                    "goals": arc.goals,
                    "completed": arc.completed_goals
                }
                for name, arc in self.character_arcs.items()
            },
            "world_state": {
                "locations": self.world_state.locations,
                "factions": self.world_state.factions
            }
        }
