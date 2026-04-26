"""
StoryForge - 大纲细化阶段
参考 novel-project-init skill 的 JSON 文档体系
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class ChapterStatus(Enum):
    """章节状态"""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    DRAFT = "draft"
    REVIEWING = "reviewing"
    COMPLETED = "completed"


@dataclass
class VolumeOutline:
    """卷级大纲"""
    volume_id: int
    name: str
    words: int
    chapters: int
    goal: str
    arc: str  # 起始状态→结束状态
    start_end_table: Dict[str, Dict[str, str]] = field(default_factory=dict)
    acts: List[Dict] = field(default_factory=list)
    chapter_outlines: List[Dict] = field(default_factory=list)
    character_growth: Dict[str, List[Dict]] = field(default_factory=dict)
    foreshadowing_setup: List[Dict] = field(default_factory=list)


@dataclass
class ChapterPlan:
    """章级写作计划"""
    chapter_id: int
    title: str
    theme: str
    plot: str
    scenes: List[str] = field(default_factory=list)
    hooks: List[str] = field(default_factory=list)
    words_target: int = 3000
    status: str = "not_started"
    characters_involved: List[str] = field(default_factory=list)
    key_events: List[str] = field(default_factory=list)
    foreshadowing: List[str] = field(default_factory=list)


@dataclass
class NovelOutline:
    """全书大纲"""
    title: str
    meta: Dict[str, Any] = field(default_factory=dict)
    selling_points: List[str] = field(default_factory=list)
    main_conflicts: Dict[str, List[Dict]] = field(default_factory=dict)
    volumes: List[VolumeOutline] = field(default_factory=list)
    creation_principles: Dict[str, str] = field(default_factory=dict)
    key_reversals: List[Dict] = field(default_factory=list)


@dataclass
class CharacterProfile:
    """人物档案"""
    id: str  # 拼音+下划线
    name: str
    role: str
    age: Optional[int] = None
    appearance: str = ""
    tags: List[str] = field(default_factory=list)
    motivation: str = ""
    fear: str = ""
    arc: Dict = field(default_factory=dict)
    intro_chapter: int = 0
    current_location: str = ""
    location_log: List[Dict] = field(default_factory=list)
    relationships: List[Dict] = field(default_factory=list)
    personal_timeline: List[Dict] = field(default_factory=list)


@dataclass
class Foreshadowing:
    """伏笔追踪"""
    id: str  # F001 格式
    content: str
    setup_chapter: str = ""
    payoff_volume: str = ""
    status: str = "未回收"  # 未回收/部分回收/已回收/持续使用
    note: str = ""


@dataclass
class WorldSetting:
    """世界观设定"""
    world_name: str
    background: str
    power_structure: Dict = field(default_factory=dict)
    key_locations: Dict = field(default_factory=dict)
    rules: Dict = field(default_factory=dict)


@dataclass
class ProjectProgress:
    """项目进度"""
    current: Dict = field(default_factory=dict)
    completed: Dict = field(default_factory=dict)
    volumes: List[Dict] = field(default_factory=list)
    chapter_status: Dict[str, List[int]] = field(default_factory=dict)


class OutlineGenerator:
    """
    大纲生成器
    
    职责：
    1. 从概念生成全书大纲
    2. 从卷纲生成章级细纲
    3. 管理伏笔、人物、世界观
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def generate_novel_outline(
        self,
        title: str,
        concept: str,
        genre: str,
        total_words: int,
        total_volumes: int = 1,
        chapters_per_volume: int = 30,
        words_per_chapter: int = 3000
    ) -> NovelOutline:
        """
        生成全书大纲
        
        Args:
            title: 小说标题
            concept: 核心创意/一句话梗概
            genre: 类型
            total_words: 总字数
            total_volumes: 卷数
            chapters_per_volume: 每卷章数
            words_per_chapter: 每章字数
        """
        # TODO: 调用 LLM 生成大纲
        # 这里先返回一个基础结构
        return NovelOutline(
            title=title,
            meta={
                "type": genre,
                "total_words": total_words,
                "total_volumes": total_volumes,
                "chapters_per_volume": chapters_per_volume,
                "words_per_chapter": words_per_chapter,
                "total_chapters": total_volumes * chapters_per_volume
            },
            selling_points=[],
            main_conflicts={
                "external": [],
                "internal": [],
                "deep_theme": []
            },
            volumes=[],
            creation_principles={}
        )
    
    def generate_volume_outline(
        self,
        volume_id: int,
        novel_outline: NovelOutline,
        characters: List[CharacterProfile]
    ) -> VolumeOutline:
        """
        生成卷级大纲
        
        Args:
            volume_id: 卷号
            novel_outline: 全书大纲
            characters: 人物列表
        """
        # TODO: 调用 LLM 生成卷纲
        return VolumeOutline(
            volume_id=volume_id,
            name=f"第{volume_id}卷",
            words=0,
            chapters=0,
            goal="",
            arc="",
            chapter_outlines=[]
        )
    
    def generate_chapter_plan(
        self,
        chapter_id: int,
        volume_outline: VolumeOutline,
        characters: List[CharacterProfile],
        previous_chapters: List[ChapterPlan] = None
    ) -> ChapterPlan:
        """
        生成章级写作计划
        
        Args:
            chapter_id: 章节号
            volume_outline: 卷级大纲
            characters: 人物列表
            previous_chapters: 之前章节的计划
        """
        # TODO: 调用 LLM 生成章级细纲
        return ChapterPlan(
            chapter_id=chapter_id,
            title=f"第{chapter_id}章",
            theme="",
            plot="",
            words_target=volume_outline.chapter_outlines[chapter_id - 1].get("words_target", 3000) if volume_outline.chapter_outlines else 3000
        )
    
    def to_json(self, outline: NovelOutline) -> Dict:
        """转换为大纲 JSON"""
        return {
            "title": outline.title,
            "meta": outline.meta,
            "selling_points": outline.selling_points,
            "main_conflicts": outline.main_conflicts,
            "volumes": [
                {
                    "volume_id": v.volume_id,
                    "name": v.name,
                    "words": v.words,
                    "chapters": v.chapters,
                    "goal": v.goal,
                    "arc": v.arc,
                    "start_end_table": v.start_end_table,
                    "acts": v.acts,
                    "chapter_outlines": v.chapter_outlines,
                    "character_growth": v.character_growth,
                    "foreshadowing_setup": v.foreshadowing_setup
                }
                for v in outline.volumes
            ],
            "creation_principles": outline.creation_principles,
            "key_reversals": outline.key_reversals
        }
