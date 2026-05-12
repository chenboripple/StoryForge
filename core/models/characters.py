"""
兼容层 - 角色模型
新代码请使用: from core.models.world import Character, Relationship, RelationshipType, CharacterGraph
"""
from __future__ import annotations

from core.models.world.characters import (
    Character,
    Relationship,
    RelationshipType,
    CharacterGraph,
)

__all__ = ["Character", "Relationship", "RelationshipType", "CharacterGraph"]
