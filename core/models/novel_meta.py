"""
兼容层 - 小说元数据模型
新代码请使用: from core.models.content import NovelMeta, PipelineStage
"""
from __future__ import annotations

from core.models.content.novel_meta import (
    NovelMeta,
    PipelineStage,
)

__all__ = ["NovelMeta", "PipelineStage"]
