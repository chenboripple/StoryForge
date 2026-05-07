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
        
        # 1. 角色一致性检查
        for name, arc in self.character_arcs.items():
            if name not in chapter_content:
                continue  # 角色未出场，跳过
            
            # 检查角色行为是否符合当前状态
            # 例如：如果角色状态是"重伤"，但章节中描述他"生龙活虎地战斗"
            if arc.current_state:
                # 定义不一致模式：状态 -> 矛盾描述关键词
                inconsistency_patterns = {
                    "重伤": ["生龙活虎", "精力充沛", "全力奔跑", "激烈战斗"],
                    "死亡": ["说话", "行动", "思考", "出现"],
                    "昏迷": ["说话", "行动", "思考", "决策"],
                    "被俘": ["自由行动", "独自离开", "无人看管"],
                    "敌对": ["亲密交谈", "合作", "信任", "帮助"],
                    "陌生": ["深情对视", "默契配合", "已知秘密"],
                }
                
                for state_keyword, forbidden_patterns in inconsistency_patterns.items():
                    if state_keyword in arc.current_state:
                        for pattern in forbidden_patterns:
                            if pattern in chapter_content:
                                # 确认是描述该角色的（简单上下文检查）
                                # 找到 pattern 出现的位置，检查前后100字符是否包含角色名
                                idx = chapter_content.find(pattern)
                                context = chapter_content[max(0, idx-100):min(len(chapter_content), idx+100)]
                                if name in context:
                                    issues.append(Inconsistency(
                                        type="character",
                                        description=f"{name}当前状态是'{arc.current_state}'，但出现了矛盾描述：'{pattern}'",
                                        chapter=chapter_num,
                                        severity="error"
                                    ))
            
            # 检查已完成的目标是否被重复提及为未完成
            for completed_goal in arc.completed_goals:
                # 如果角色还在追求已完成的目标，属于轻微不一致
                pursuit_patterns = ["想要", "决心", "立志", "目标是", "为了"]
                for pursuit in pursuit_patterns:
                    if pursuit in chapter_content and completed_goal in chapter_content:
                        idx = chapter_content.find(pursuit)
                        context = chapter_content[max(0, idx-50):min(len(chapter_content), idx+len(completed_goal)+50)]
                        if name in context and completed_goal in context:
                            issues.append(Inconsistency(
                                type="character",
                                description=f"{name}的目标'{completed_goal}'已在之前章节完成，但本章仍描述其在追求该目标",
                                chapter=chapter_num,
                                severity="warning"
                            ))
        
        # 2. 世界设定一致性检查
        for loc_name, loc_info in self.world_state.locations.items():
            if loc_name not in chapter_content:
                continue
            
            # 检查地点状态矛盾
            status = loc_info.get("status", "")
            if status:
                location_inconsistency_patterns = {
                    "损毁": ["完好无损", "正常运转", "繁华", "热闹"],
                    "废墟": ["新建", "装修", "营业中", "人来人往"],
                    "被占领": ["自由出入", "无人看守", "安全区"],
                    "危险": ["安全", "避难所", "放心", "无威胁"],
                }
                
                for status_keyword, forbidden_patterns in location_inconsistency_patterns.items():
                    if status_keyword in status:
                        for pattern in forbidden_patterns:
                            if pattern in chapter_content:
                                idx = chapter_content.find(pattern)
                                context = chapter_content[max(0, idx-80):min(len(chapter_content), idx+80)]
                                if loc_name in context:
                                    issues.append(Inconsistency(
                                        type="world",
                                        description=f"地点'{loc_name}'状态是'{status}'，但出现了矛盾描述：'{pattern}'",
                                        chapter=chapter_num,
                                        severity="error"
                                    ))
            
            # 检查地点控制势力矛盾
            controlled_by = loc_info.get("controlled_by", "")
            if controlled_by:
                # 如果地点被A势力控制，但描述中B势力在该地点自由行动
                for faction_name, faction_info in self.world_state.factions.items():
                    if faction_name != controlled_by and faction_name in chapter_content:
                        # 检查敌对势力是否出现在该地点
                        enemies = loc_info.get("enemies", [])
                        if faction_name in enemies:
                            idx = chapter_content.find(loc_name)
                            context = chapter_content[max(0, idx-100):min(len(chapter_content), idx+100)]
                            if faction_name in context:
                                issues.append(Inconsistency(
                                    type="world",
                                    description=f"地点'{loc_name}'被'{controlled_by}'控制，但敌对势力'{faction_name}'出现在该地点",
                                    chapter=chapter_num,
                                    severity="warning"
                                ))
        
        # 3. 时间线一致性检查
        if chapter_num > 1:
            prev_events = self._chapter_events.get(chapter_num - 1, [])
            current_events = self._chapter_events.get(chapter_num, [])
            
            for prev_event in prev_events:
                # 检查时间关键词矛盾
                time_indicators = {
                    "第二天": ["同一天", "当晚", "几小时后", "紧接着"],
                    "一周后": ["第二天", "隔天", "次日"],
                    "一个月后": ["一周后", "几天后", "第二天"],
                    "一年后": ["一个月后", "几周后", "几天后"],
                }
                
                for time_marker, contradictions in time_indicators.items():
                    if time_marker in prev_event.description:
                        for contradiction in contradictions:
                            if contradiction in chapter_content:
                                issues.append(Inconsistency(
                                    type="timeline",
                                    description=f"前一章标记时间为'{time_marker}'，但本章出现'{contradiction}'，时间线可能矛盾",
                                    chapter=chapter_num,
                                    severity="warning"
                                ))
        
        # 4. 伏笔回收检查（契诃夫之枪）
        unresolved = [g for g in self.chekhovs_guns if not g.get("resolved")]
        for gun in unresolved:
            gun_desc = gun.get("description", "")
            # 检查伏笔是否在本章被回收
            if gun_desc and any(keyword in chapter_content for keyword in gun_desc.split()[:3]):
                # 简单检查：如果伏笔描述中的前3个关键词出现在本章，认为可能已回收
                # 更精确的检查需要更复杂的NLP
                pass  # 这里只标记，不报错（回收伏笔是好事）
        
        # 5. 关系一致性检查
        for name, arc in self.character_arcs.items():
            if name not in chapter_content:
                continue
            
            for related_name, relation in arc.relationships.items():
                if related_name not in chapter_content:
                    continue
                
                # 检查关系矛盾
                relation_inconsistencies = {
                    "敌对": ["拥抱", "亲吻", "合作", "信任", "亲密"],
                    "陌生": ["默契", "心有灵犀", "老相识", "多年好友"],
                    "恋人": ["厌恶", "憎恨", "敌对", "互相提防"],
                    "父子": ["同辈相称", "直呼其名", "陌生称呼"],
                }
                
                for relation_type, forbidden_patterns in relation_inconsistencies.items():
                    if relation_type in relation:
                        for pattern in forbidden_patterns:
                            if pattern in chapter_content:
                                # 检查上下文是否涉及这两个角色
                                idx = chapter_content.find(pattern)
                                context = chapter_content[max(0, idx-120):min(len(chapter_content), idx+120)]
                                if name in context and related_name in context:
                                    issues.append(Inconsistency(
                                        type="plot",
                                        description=f"{name}与{related_name}的关系是'{relation}'，但出现了矛盾互动：'{pattern}'",
                                        chapter=chapter_num,
                                        severity="error"
                                    ))
        
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
