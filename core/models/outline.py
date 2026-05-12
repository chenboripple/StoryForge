"""
兼容层 - 大纲模型
新代码请使用: from core.models.content import Outline, ChapterOutline, VolumeOutline
"""
from __future__ import annotations

from core.models.content.outline import (
    Outline,
    ChapterOutline,
    VolumeOutline,
)

__all__ = ["Outline", "ChapterOutline", "VolumeOutline"]
