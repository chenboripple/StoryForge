"""
StoryForge 模型层（Models Layer）
定义所有数据结构，与存储解耦
"""
from .base import BaseModel, TimestampMixin, JSONSerializable
from .novel_meta import NovelMeta, PipelineStage
from .outline import Outline, ChapterOutline, VolumeOutline
from .characters import Character, Relationship, RelationshipType, CharacterGraph
from .world_setting import WorldSetting, TimelineEvent, Location, LocationType, Faction, FactionType
from .chapter import Chapter, ChapterStatus
from .review import Review, ReviewRecord, DimensionScore, ReviewVerdict
from .proofread import Proofread, ProofreadRecord, ProofreadIssue
from .extraction import (
    ChapterAnalysis,
    ExtractedEntity,
    ExtractedCharacter,
    ExtractedLocation,
    ExtractedForeshadowing,
    CharacterUpdate,
    WorldUpdate,
)
from .ip_assets import CharacterIP, RelationshipEdge, SceneSetting, DerivedSetting, StoryBible
from .agent_comm import AgentMessage, RoutingSuggestion
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
    # Base
    'BaseModel', 'TimestampMixin', 'JSONSerializable',
    # Novel Meta
    'NovelMeta', 'PipelineStage',
    # Outline
    'Outline', 'ChapterOutline', 'VolumeOutline',
    # Characters
    'Character', 'Relationship', 'RelationshipType', 'CharacterGraph',
    # World Setting
    'WorldSetting', 'TimelineEvent', 'Location', 'LocationType', 'Faction', 'FactionType',
    # Chapter
    'Chapter', 'ChapterStatus',
    # Review
    'Review', 'ReviewRecord', 'DimensionScore', 'ReviewVerdict',
    # Proofread
    'Proofread', 'ProofreadRecord', 'ProofreadIssue',
    # Extraction
    'ChapterAnalysis', 'ExtractedEntity', 'ExtractedCharacter', 'ExtractedLocation',
    'ExtractedForeshadowing', 'CharacterUpdate', 'WorldUpdate',
    # IP Assets
    'CharacterIP', 'RelationshipEdge', 'SceneSetting', 'DerivedSetting', 'StoryBible',
    # Agent Communication
    'AgentMessage', 'RoutingSuggestion',
    # Video
    'ShotSpec', 'VideoScript', 'CharacterVisualProfile', 'SceneCanonicalProfile',
    'VisualBible', 'VideoAsset', 'AssetManifest', 'VideoRenderPlan',
    'ConsistencyIssue', 'ConsistencyMetrics', 'ConsistencyThresholds',
    'ConsistencyReport', 'VideoOutput', 'VideoState',
]
