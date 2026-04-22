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
