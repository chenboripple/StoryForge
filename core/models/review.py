"""
兼容层 - 审稿模型
新代码请使用: from core.models.content import Review, ReviewRecord, ...
"""
from __future__ import annotations

from core.models.content.review import (
    Review,
    ReviewRecord,
    ReviewIssue,
    DimensionScore,
    ReviewVerdict,
)

__all__ = [
    "Review",
    "ReviewRecord",
    "ReviewIssue",
    "DimensionScore",
    "ReviewVerdict",
]
