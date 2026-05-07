"""
StoryForge - 核心状态定义
全局状态对象，贯穿整个 Pipeline
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import copy

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
class ProofreadRecord:
    """校对记录"""
    round: int
    proofreader: str
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
    proofread_records: Dict[int, List[Any]] = field(default_factory=dict)  # 校对记录

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

    def copy(self) -> "NovelState":
        """深拷贝，用于批量创作时隔离各章状态"""
        return copy.deepcopy(self)

    @classmethod
    def from_dict(cls, data: dict) -> "NovelState":
        """从字典安全构造，自动过滤不在 dataclass 中的字段"""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}

        # 反序列化嵌套对象
        if "current_stage" in filtered and isinstance(filtered["current_stage"], str):
            filtered["current_stage"] = PipelineStage(filtered["current_stage"])

        if "characters" in filtered and isinstance(filtered["characters"], list):
            filtered["characters"] = [
                CharacterInfo(**c) if isinstance(c, dict) else c
                for c in filtered["characters"]
            ]

        if "chapter_status" in filtered and isinstance(filtered["chapter_status"], dict):
            filtered["chapter_status"] = {
                int(k): ChapterStatus(v) if isinstance(v, str) else v
                for k, v in filtered["chapter_status"].items()
            }

        if "chapters" in filtered and isinstance(filtered["chapters"], dict):
            filtered["chapters"] = {int(k): v for k, v in filtered["chapters"].items()}

        if "volume_outline" in filtered and isinstance(filtered["volume_outline"], dict):
            filtered["volume_outline"] = {int(k): v for k, v in filtered["volume_outline"].items()}

        if "reviews" in filtered and isinstance(filtered["reviews"], dict):
            filtered["reviews"] = {
                int(k): [ReviewRecord(**r) if isinstance(r, dict) else r for r in v]
                for k, v in filtered["reviews"].items()
            }

        if "proofread_records" in filtered and isinstance(filtered["proofread_records"], dict):
            filtered["proofread_records"] = {
                int(k): [ProofreadRecord(**p) if isinstance(p, dict) else p for p in v]
                for k, v in filtered["proofread_records"].items()
            }

        return cls(**filtered)

    def to_dict(self) -> dict:
        """序列化为字典（JSON 友好），用于存储与 API 输出"""
        return {
            # 元数据
            "novel_id": self.novel_id,
            "novel_title": self.novel_title,
            "genre": self.genre,
            "target_word_count": self.target_word_count,
            "current_stage": self.current_stage.value if isinstance(self.current_stage, PipelineStage) else self.current_stage,
            # 创作层
            "concept": self.concept,
            "outline": self.outline,
            "volume_outline": {str(k): v for k, v in self.volume_outline.items()},
            "characters": [
                {
                    "name": c.name,
                    "age": c.age,
                    "appearance": c.appearance,
                    "personality": c.personality,
                    "background": c.background,
                    "goals": list(c.goals),
                    "relationships": dict(c.relationships),
                    "classic_lines": list(c.classic_lines),
                }
                for c in self.characters
            ],
            "chapters": {str(k): v for k, v in self.chapters.items()},
            "chapter_status": {
                str(k): (v.value if isinstance(v, ChapterStatus) else v)
                for k, v in self.chapter_status.items()
            },
            # 审稿
            "current_chapter": self.current_chapter,
            "review_round": self.review_round,
            "max_review_rounds": self.max_review_rounds,
            "reviews": {
                str(k): [
                    {
                        "round": r.round,
                        "reviewer": r.reviewer,
                        "score": r.score,
                        "comments": r.comments,
                        "passed": r.passed,
                        "timestamp": r.timestamp,
                    }
                    for r in v
                ]
                for k, v in self.reviews.items()
            },
            "proofread_records": {
                str(k): [
                    {
                        "round": p.round,
                        "proofreader": p.proofreader,
                        "comments": p.comments,
                        "passed": p.passed,
                        "timestamp": p.timestamp,
                    }
                    for p in v
                ]
                for k, v in self.proofread_records.items()
            },
            # 萃取层 / IP 层
            "knowledge_base": self.knowledge_base,
            "character_ips": self.character_ips,
            "visual_assets": self.visual_assets,
            # 控制
            "error_message": self.error_message,
            "human_feedback": self.human_feedback,
            "should_pause": self.should_pause,
        }

    def to_index_entry(self) -> dict:
        """生成轻量索引条目（用于清单页）"""
        total_chapters = len(self.chapters)
        approved_chapters = sum(
            1 for s in self.chapter_status.values()
            if s == ChapterStatus.APPROVED
        )
        return {
            "novel_id": self.novel_id,
            "novel_title": self.novel_title,
            "genre": self.genre,
            "concept": self.concept[:120] if self.concept else "",
            "current_stage": self.current_stage.value if isinstance(self.current_stage, PipelineStage) else self.current_stage,
            "current_chapter": self.current_chapter,
            "total_chapters": total_chapters,
            "approved_chapters": approved_chapters,
            "character_count": len(self.characters),
        }
