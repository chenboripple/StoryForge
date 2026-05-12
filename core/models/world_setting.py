"""
兼容层 - 世界观设置模型
新代码请使用: from core.models.world import WorldSetting, Location, Faction, ...
"""
from __future__ import annotations

from core.models.world.world_setting import (
    WorldSetting,
    TimelineEvent,
    Location,
    LocationType,
    Faction,
    FactionType,
)

__all__ = [
    "WorldSetting",
    "TimelineEvent",
    "Location",
    "LocationType",
    "Faction",
    "FactionType",
]
