"""
兼容层 - 视频资产模型
新代码请使用: from core.models.video import VideoScript, VisualBible, ...
"""
from __future__ import annotations

from core.models.video.video_assets import (
    ShotSpec,
    VideoScript,
    CharacterVisualProfile,
    SceneCanonicalProfile,
    VisualBible,
    VideoAsset,
    AssetManifest,
    VideoRenderPlan,
    ConsistencyIssue,
    ConsistencyMetrics,
    ConsistencyThresholds,
    ConsistencyReport,
    VideoOutput,
    VideoState,
)

__all__ = [
    "ShotSpec",
    "VideoScript",
    "CharacterVisualProfile",
    "SceneCanonicalProfile",
    "VisualBible",
    "VideoAsset",
    "AssetManifest",
    "VideoRenderPlan",
    "ConsistencyIssue",
    "ConsistencyMetrics",
    "ConsistencyThresholds",
    "ConsistencyReport",
    "VideoOutput",
    "VideoState",
]
