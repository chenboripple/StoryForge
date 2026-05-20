"""
StoryForge 模型层（Models Layer）
定义所有数据结构，与存储解耦

分组说明：
- base.py - 基础模型类
- content/ - 创作相关（小说、大纲、章节、审稿、校对）
- world/ - 世界观相关（人物、地点、势力、时间线）
- extraction/ - 知识萃取相关
- ip/ - IP 生成相关
- agent/ - Agent 通信相关
- video/ - 视频生成相关

"""
# 基础模块
from .base import BaseModel, TimestampMixin, JSONSerializable

# 分组模块导入
from .content import (
    NovelMeta, PipelineStage,
    Outline, ChapterOutline, VolumeOutline,
    Chapter, ChapterStatus,
    Review, ReviewRecord, DimensionScore, ReviewVerdict, ReviewIssue,
    Proofread, ProofreadRecord, ProofreadIssue, ProofreadIssueType,
)
from .world import (
    Character, Relationship, RelationshipType, CharacterGraph,
    WorldSetting, TimelineEvent, Location, LocationType, Faction, FactionType,
)
from .extraction import (
    ChapterAnalysis,
    ExtractedEntity,
    ExtractedCharacter,
    ExtractedLocation,
    ExtractedForeshadowing,
    CharacterUpdate,
    WorldUpdate,
)
from .ip import (
    CharacterIP, RelationshipEdge, SceneSetting, DerivedSetting, StoryBible,
)
from .agent import (
    AgentMessage, RoutingSuggestion,
)
from .video import (
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
    # Content (创作相关)
    'NovelMeta', 'PipelineStage',
    'Outline', 'ChapterOutline', 'VolumeOutline',
    'Chapter', 'ChapterStatus',
    'Review', 'ReviewRecord', 'DimensionScore', 'ReviewVerdict', 'ReviewIssue',
    'Proofread', 'ProofreadRecord', 'ProofreadIssue', 'ProofreadIssueType',
    # World (世界观相关)
    'Character', 'Relationship', 'RelationshipType', 'CharacterGraph',
    'WorldSetting', 'TimelineEvent', 'Location', 'LocationType', 'Faction', 'FactionType',
    # Extraction (萃取相关)
    'ChapterAnalysis', 'ExtractedEntity', 'ExtractedCharacter', 'ExtractedLocation',
    'ExtractedForeshadowing', 'CharacterUpdate', 'WorldUpdate',
    # IP (IP生成相关)
    'CharacterIP', 'RelationshipEdge', 'SceneSetting', 'DerivedSetting', 'StoryBible',
    # Agent (Agent通信相关)
    'AgentMessage', 'RoutingSuggestion',
    # Video (视频生成相关)
    'ShotSpec', 'VideoScript', 'CharacterVisualProfile', 'SceneCanonicalProfile',
    'VisualBible', 'VideoAsset', 'AssetManifest', 'VideoRenderPlan',
    'ConsistencyIssue', 'ConsistencyMetrics', 'ConsistencyThresholds',
    'ConsistencyReport', 'VideoOutput', 'VideoState',
]
