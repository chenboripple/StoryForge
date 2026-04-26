"""
NovelForge - 核心状态定义
全局状态对象，贯穿整个 Pipeline
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


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
    timestamp: str = ""         # 时间戳


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


# ==================== 新：分层状态（推荐使用）====================

@dataclass
class NovelMetadata:
    """小说元数据"""
    novel_id: str = ""
    novel_title: str = ""
    genre: str = ""
    target_word_count: int = 3000
    author: str = ""


@dataclass
class CreationState:
    """创作层状态（新结构）"""
    # 大纲
    concept: str = ""
    outline: str = ""
    chapter_outlines: Dict[int, str] = field(default_factory=dict)  # 章级细纲
    
    # 章节
    chapters: Dict[int, Any] = field(default_factory=dict)  # 存 ChapterContent 对象
    chapter_status: Dict[int, ChapterStatus] = field(default_factory=dict)
    
    # 审稿
    current_chapter: int = 1
    review_round: int = 0
    max_review_rounds: int = 3
    reviews: Dict[int, List[Any]] = field(default_factory=dict)  # 存 ReviewRecord
    structured_reviews: Dict[int, List[Any]] = field(default_factory=dict)  # 存 ReviewResult


@dataclass
class ExtractionState:
    """萃取层状态"""
    knowledge_base: Dict[str, Any] = field(default_factory=dict)
    # 结构：
    # {
    #   "characters": {role_name: {"arc": [...], "traits": [...], ...}},
    #   "world": {"locations": [...], "rules": [...], ...},
    #   "plots": {"key_scenes": [...], "quotes": [...], ...}
    # }


@dataclass
class IPState:
    """IP 生成层状态"""
    character_ips: Dict[str, Dict] = field(default_factory=dict)
    visual_assets: Dict[str, List[Dict]] = field(default_factory=dict)
    video_scripts: List[Dict] = field(default_factory=list)


@dataclass
class NovelStateV2:
    """
    新状态对象：分层设计，各层只关心自己的数据
    向后兼容：提供访问旧字段的属性
    """
    # 核心
    metadata: NovelMetadata = field(default_factory=NovelMetadata)
    creation: CreationState = field(default_factory=CreationState)
    extraction: Optional[ExtractionState] = None
    ip_generation: Optional[IPState] = None
    
    # 记忆系统
    memory_dict: Optional[Dict] = None
    
    # 控制
    current_stage: PipelineStage = PipelineStage.CREATION
    error_message: str = ""
    human_feedback: Optional[str] = None
    should_pause: bool = False
    
    # 向后兼容属性访问
    @property
    def novel_id(self): return self.metadata.novel_id
    @novel_id.setter
    def novel_id(self, value): self.metadata.novel_id = value
    
    @property
    def novel_title(self): return self.metadata.novel_title
    @novel_title.setter
    def novel_title(self, value): self.metadata.novel_title = value
    
    @property
    def genre(self): return self.metadata.genre
    @genre.setter
    def genre(self, value): self.metadata.genre = value
    
    @property
    def target_word_count(self): return self.metadata.target_word_count
    @target_word_count.setter
    def target_word_count(self, value): self.metadata.target_word_count = value
    
    @property
    def concept(self): return self.creation.concept
    @concept.setter
    def concept(self, value): self.creation.concept = value
    
    @property
    def outline(self): return self.creation.outline
    @outline.setter
    def outline(self, value): self.creation.outline = value
    
    @property
    def current_chapter(self): return self.creation.current_chapter
    @current_chapter.setter
    def current_chapter(self, value): self.creation.current_chapter = value
    
    @property
    def review_round(self): return self.creation.review_round
    @review_round.setter
    def review_round(self, value): self.creation.review_round = value
    
    @property
    def max_review_rounds(self): return self.creation.max_review_rounds
    @max_review_rounds.setter
    def max_review_rounds(self, value): self.creation.max_review_rounds = value
    
    @property
    def chapters(self): return self.creation.chapters
    
    @property
    def chapter_status(self): return self.creation.chapter_status
    
    @property
    def reviews(self): return self.creation.reviews
    
    # 旧接口兼容的方法
    def get_current_chapter_status(self):
        return self.creation.chapter_status.get(
            self.creation.current_chapter, ChapterStatus.PENDING
        )
    
    def get_latest_review(self):
        chapter_reviews = self.creation.reviews.get(self.creation.current_chapter, [])
        return chapter_reviews[-1] if chapter_reviews else None
    
    def to_context_string(self):
        context = f"""
小说：{self.metadata.novel_title or '未命名'}
类型：{self.metadata.genre or '未指定'}
当前章节：第{self.creation.current_chapter}章
章节状态：{self.get_current_chapter_status().value}
"""
        return context
