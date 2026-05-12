"""
Chapter - 章节数据
章节内容、状态、版本管理
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum

from ..base import BaseModel


class ChapterStatus(Enum):
    """章节状态"""
    PENDING = "pending"
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    REVISING = "revising"
    PROOFREADING = "proofreading"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class Chapter(BaseModel):
    """章节"""
    novel_id: str = ""
    chapter_num: int = 1
    title: str = ""
    content: str = ""          # 正文
    word_count: int = 0
    version: int = 1           # 版本号

    # 内容来源
    generated_by: str = ""     # 生成Agent名称
    revised_by: str = ""       # 修改Agent名称
    proofread_by: str = ""     # 校对Agent名称

    # 状态
    status: ChapterStatus = ChapterStatus.PENDING
    created_at: str = ""
    updated_at: str = ""
    published_at: str = ""

    # 上下文
    outline: str = ""          # 本章大纲（创作时的参考）
    summary: str = ""          # 本章摘要
    key_events: List[str] = field(default_factory=list)
    characters_present: List[str] = field(default_factory=list)
    locations_present: List[str] = field(default_factory=list)

    # 审稿关联
    review_round: int = 0
    review_scores: List[int] = field(default_factory=list)  # 每轮评分
    latest_review_comment: str = ""

    # 历史版本
    history: List[Dict[str, Any]] = field(default_factory=list)
    # history: [{"version": 1, "content": "...", "updated_at": "..."}]

    def __post_init__(self):
        if self.word_count == 0 and self.content:
            self.word_count = len(self.content)

    def update_content(self, new_content: str, agent_name: str = ""):
        """更新内容，保存历史"""
        if self.content:
            self.history.append({
                "version": self.version,
                "content": self.content,
                "updated_at": self.updated_at,
                "updated_by": agent_name or self.revised_by,
            })
        self.content = new_content
        self.word_count = len(new_content)
        self.version += 1
        self.updated_at = self._now()

    def get_preview(self, length: int = 120) -> str:
        """获取预览"""
        return self.content[:length] if self.content else ""

    def to_index_entry(self) -> Dict[str, Any]:
        """轻量索引条目"""
        return {
            "chapter_num": self.chapter_num,
            "title": self.title,
            "status": self.status.value,
            "word_count": self.word_count,
            "version": self.version,
            "review_round": self.review_round,
            "latest_score": self.review_scores[-1] if self.review_scores else None,
            "preview": self.get_preview(),
        }

    @staticmethod
    def _now() -> str:
        from datetime import datetime
        return datetime.now().isoformat()
