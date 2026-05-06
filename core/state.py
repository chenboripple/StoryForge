"""
NovelForge - 核心状态定义
全局状态对象，贯穿整个 Pipeline
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import copy


class ChapterStatus(Enum):
    """章节状态"""
    PENDING = "pending"         # 待写作
    DRAFT = "draft"             # 初稿完成
    IN_REVIEW = "in_review"     # 审稿中
    REVISING = "revising"       # 修改中
    PROOFREADING = "proofreading"  # 校对中
    APPROVED = "approved"       # 已通过
    REJECTED = "rejected"       # 被驳回


class PipelineStage(Enum):
    """Pipeline 阶段"""
    CREATION = "creation"       # 创作层
    EXTRACTION = "extraction"   # 萃取层
    IP_GENERATION = "ip_generation"  # IP 生成层


@dataclass
class ReviewRecord:
    """审稿记录"""
    round: int                  # 第几轮审稿
    reviewer: str               # 审稿人名字
    score: int                  # 评分 0-100
    comments: str               # 审稿意见
    passed: bool                # 是否通过
    timestamp: Optional[str] = None  # 时间戳


@dataclass
class ProofreadRecord:
    """校对记录"""
    round: int                  # 第几轮校对
    proofreader: str            # 校对人名字
    comments: str               # 校对意见
    passed: bool                # 是否通过
    timestamp: Optional[str] = None  # 时间戳


@dataclass
class CharacterInfo:
    """角色信息"""
    name: str
    age: Optional[int] = None
    appearance: str = ""        # 外貌描述
    personality: str = ""       # 性格标签
    background: str = ""        # 背景故事
    goals: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)
    classic_lines: List[str] = field(default_factory=list)  # 经典台词


@dataclass
class NovelState:
    """
    全局状态对象 - LangGraph 的共享状态
    
    设计原则：
    1. 所有 Agent 节点读写同一个状态对象
    2. 状态字段按阶段分组，便于追踪
    3. 不可变字段用 Optional，可变字段用空默认值
    """
    
    # ==================== 元数据 ====================
    novel_id: str = ""                          # 小说唯一标识
    novel_title: str = ""                       # 小说标题
    genre: str = ""                             # 类型（科幻/玄幻/都市...）
    target_word_count: int = 3000               # 目标单章字数
    current_stage: PipelineStage = PipelineStage.CREATION
    
    # ==================== 阶段一：创作层 ====================
    # 大纲
    concept: str = ""                           # 核心创意
    outline: str = ""                           # 完整大纲
    volume_outline: Dict[int, str] = field(default_factory=dict)  # 分卷大纲
    
    # 角色
    characters: List[CharacterInfo] = field(default_factory=list)
    
    # 章节（key: 章节号, value: 内容）
    chapters: Dict[int, str] = field(default_factory=dict)
    chapter_status: Dict[int, ChapterStatus] = field(default_factory=dict)
    
    # 审稿循环
    current_chapter: int = 1                    # 当前处理章节
    review_round: int = 0                       # 当前审稿轮次
    max_review_rounds: int = 3                  # 最大审稿轮次
    reviews: Dict[int, List[ReviewRecord]] = field(default_factory=dict)  # 章节审稿记录
    proofread_records: Dict[int, List[ProofreadRecord]] = field(default_factory=dict)  # 章节校对记录
    
    # ==================== 阶段二：萃取层 ====================
    knowledge_base: Dict[str, Any] = field(default_factory=dict)
    # 结构：
    # {
    #   "characters": {角色名: {外貌、性格、关系、成长弧线}},
    #   "world": {世界观设定},
    #   "plots": {名场面列表、金句、情感高潮点}
    # }
    
    # ==================== 阶段三：IP 生成层 ====================
    character_ips: Dict[str, Dict] = field(default_factory=dict)
    # 结构：
    # {
    #   "角色名": {
    #     "personality_config": {},  # 角色 AI 人格配置
    #     "visual_assets": [],       # 视觉资产列表
    #     "video_scripts": []        # 视频脚本
    #   }
    # }
    
    visual_assets: Dict[str, List[Dict]] = field(default_factory=dict)
    
    # ==================== 控制字段 ====================
    error_message: str = ""                     # 错误信息
    human_feedback: Optional[str] = None        # 人工反馈（Human-in-the-loop）
    should_pause: bool = False                  # 是否暂停等待人工介入
    
    def get_current_chapter_status(self) -> ChapterStatus:
        """获取当前章节状态"""
        return self.chapter_status.get(self.current_chapter, ChapterStatus.PENDING)
    
    def get_latest_review(self) -> Optional[ReviewRecord]:
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
