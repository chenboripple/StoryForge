"""
兼容层 - 章节模型
新代码请使用: from core.models.content import Chapter, ChapterStatus
"""
from __future__ import annotations

from core.models.content.chapter import (
    Chapter,
    ChapterStatus,
)

__all__ = ["Chapter", "ChapterStatus"]
