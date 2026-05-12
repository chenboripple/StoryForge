"""
Video Models - 视频生成相关数据模型
镜头剧本、视觉圣经、资产、渲染计划、一致性检查
"""
from .video_assets import (
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
    'ShotSpec',
    'VideoScript',
    'CharacterVisualProfile',
    'SceneCanonicalProfile',
    'VisualBible',
    'VideoAsset',
    'AssetManifest',
    'VideoRenderPlan',
    'ConsistencyIssue',
    'ConsistencyMetrics',
    'ConsistencyThresholds',
    'ConsistencyReport',
    'VideoOutput',
    'VideoState',
]
