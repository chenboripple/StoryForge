"""
兼容层 - IP 资产模型
新代码请使用: from core.models.ip import CharacterIP, StoryBible, ...
"""
from __future__ import annotations

from core.models.ip.ip_assets import (
    CharacterIP,
    RelationshipEdge,
    SceneSetting,
    DerivedSetting,
    StoryBible,
)

__all__ = [
    "CharacterIP",
    "RelationshipEdge",
    "SceneSetting",
    "DerivedSetting",
    "StoryBible",
]
