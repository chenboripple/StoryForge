"""
StoryForge - 核心状态定义
全局状态对象，贯穿整个 Pipeline
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum

from core.settings import get_settings


class ChapterStatus(Enum):
    """章节状态"""
    PENDING = "pending"
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    REVISING = "revising"
    PROOFREADING = "proofreading"
    APPROVED = "approved"
    REJECTED = "rejected"


class PipelineStage(Enum):
    """Pipeline 阶段"""
    CREATION = "creation"
    EXTRACTION = "extraction"
    IP_GENERATION = "ip_generation"


@dataclass
class ReviewRecord:
    """审稿记录"""
    round: int
    reviewer: str
    score: int
    comments: str
    passed: bool
    timestamp: str = ""


@dataclass
class CharacterInfo:
    """角色信息"""
    name: str
    age: Optional[int] = None
    appearance: str = ""
    personality: str = ""
    background: str = ""
    goals: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)
    classic_lines: List[str] = field(default_factory=list)


DEFAULT_SETTINGS = get_settings()


@dataclass
class NovelState:
    """小说全局状态"""

    # 元数据
    novel_id: str = ""
    novel_title: str = ""
    genre: str = ""
    target_word_count: int = DEFAULT_SETTINGS.pipeline.default_target_word_count
    current_stage: PipelineStage = PipelineStage.CREATION

    # 创作层
    concept: str = ""
    outline: str = ""
    volume_outline: Dict[int, str] = field(default_factory=dict)
    characters: List[CharacterInfo] = field(default_factory=list)

    # 章节与审稿（单一真源：creation['chapters']）
    chapters: Dict[int, Any] = field(default_factory=dict)
    chapter_status: Dict[int, ChapterStatus] = field(default_factory=dict)
    current_chapter: int = 1
    review_round: int = 0
    max_review_rounds: int = 3
    reviews: Dict[int, List[Any]] = field(default_factory=dict)
    structured_reviews: Dict[int, List[Any]] = field(default_factory=dict)
    proofread_results: Dict[int, List[Any]] = field(default_factory=dict)

    # 校对范围控制：chapter | volume | book | project_docs
    proofread_scope: str = "chapter"
    # 可选的综合校对输入（大纲/卷纲/世界观/时间线/人物设定等）
    proofread_context: Dict[str, Any] = field(default_factory=dict)

    # 萃取层
    knowledge_base: Dict[str, Any] = field(default_factory=dict)
    chapter_analyses: Dict[int, Any] = field(default_factory=dict)  # 知识萃取结果
    
    # IP 生成层
    character_ips: Dict[str, Dict] = field(default_factory=dict)
    visual_assets: Dict[str, List[Dict]] = field(default_factory=dict)
    story_bible: Optional[Any] = None  # Story Bible 对象

    # 兼容容器（仅用于存储非章节类辅助数据，不再与 chapters 双向绑定）
    creation: Dict[str, Any] = field(default_factory=dict)

    # 控制字段
    error_message: str = ""
    human_feedback: Optional[str] = None
    should_pause: bool = False

    def __post_init__(self):
        # 兼容旧数据：如果 creation 中有 chapters 且 self.chapters 为空，迁移一次
        if isinstance(self.creation, dict):
            if "chapters" in self.creation and not self.chapters:
                self.chapters = self.creation["chapters"]
            # 确保 creation 中有 chapters 引用（供旧代码访问）
            self.creation["chapters"] = self.chapters
        else:
            self.creation = {"chapters": self.chapters}
        
        # 初始化 creation 中的辅助字段
        if isinstance(self.creation, dict):
            self.creation.setdefault("chapter_outlines", {})
            self.creation.setdefault("chapter_summaries", {})
            self.creation.setdefault("extraction_notes", {})

    def get_current_chapter_status(self) -> ChapterStatus:
        """获取当前章节状态"""
        return self.chapter_status.get(self.current_chapter, ChapterStatus.PENDING)

    def get_latest_review(self) -> Optional[Any]:
        """获取当前章节最新审稿记录"""
        chapter_reviews = self.reviews.get(self.current_chapter, [])
        return chapter_reviews[-1] if chapter_reviews else None

    def can_continue_review(self) -> bool:
        """检查是否还能继续审稿（未超最大轮次）"""
        return self.review_round < self.max_review_rounds

    def to_context_string(self) -> str:
        """转换为上下文字符串（供 Agent 使用）"""
        context = f"""
小说：{self.novel_title or '未命名'}
类型：{self.genre or '未指定'}
当前章节：第{self.current_chapter}章
章节状态：{self.get_current_chapter_status().value}
"""
        if self.characters:
            context += f"\n主要角色：{', '.join(c.name for c in self.characters)}"
        if self.outline:
            context += f"\n大纲摘要：{self.outline[:200]}..."
        return context
