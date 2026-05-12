"""
Extraction Models - 知识萃取相关数据模型
章节分析、实体提取、伏笔识别
"""
from .extraction import (
    ChapterAnalysis,
    ExtractedEntity,
    ExtractedCharacter,
    ExtractedLocation,
    ExtractedForeshadowing,
    CharacterUpdate,
    WorldUpdate,
)

__all__ = [
    'ChapterAnalysis',
    'ExtractedEntity',
    'ExtractedCharacter',
    'ExtractedLocation',
    'ExtractedForeshadowing',
    'CharacterUpdate',
    'WorldUpdate',
]
