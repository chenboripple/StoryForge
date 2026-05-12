"""
兼容层 - 知识萃取模型
新代码请使用: from core.models.extraction import ChapterAnalysis, ExtractedCharacter, ...
"""
from __future__ import annotations

from core.models.extraction.extraction import (
    ChapterAnalysis,
    ExtractedEntity,
    ExtractedCharacter,
    ExtractedLocation,
    ExtractedForeshadowing,
    CharacterUpdate,
    WorldUpdate,
)

__all__ = [
    "ChapterAnalysis",
    "ExtractedEntity",
    "ExtractedCharacter",
    "ExtractedLocation",
    "ExtractedForeshadowing",
    "CharacterUpdate",
    "WorldUpdate",
]
