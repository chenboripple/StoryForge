"""
Video Assets - 视频生成相关数据模型
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..base import BaseModel


@dataclass
class ShotSpec(BaseModel):
    """单个镜头规格"""
    shot_id: str = ""
    chapter: int = 1
    sequence: int = 1
    duration_sec: float = 4.0
    camera_language: str = ""
    scene_id: str = ""
    season: str = ""
    weather: str = ""
    time_of_day: str = ""
    characters: List[str] = field(default_factory=list)
    age_stages: Dict[str, str] = field(default_factory=dict)  # character_id -> young/adult/old
    action: str = ""
    dialogue: str = ""
    narration: str = ""
    visual_prompt: str = ""


@dataclass
class VideoScript(BaseModel):
    """视频剧本（镜头级）"""
    novel_id: str = ""
    title: str = ""
    style: str = "cinematic"
    shots: List[ShotSpec] = field(default_factory=list)


@dataclass
class CharacterVisualProfile(BaseModel):
    """角色视觉档案（保持跨镜头一致）"""
    character_id: str = ""
    display_name: str = ""
    identity_seed: str = ""
    immutable_traits: Dict[str, str] = field(default_factory=dict)
    age_variants: Dict[str, str] = field(default_factory=dict)  # young/adult/old -> prompt suffix
    reference_image_ids: List[str] = field(default_factory=list)


@dataclass
class SceneCanonicalProfile(BaseModel):
    """场景规范档案（保持结构稳定，仅允许可变项变化）"""
    scene_id: str = ""
    display_name: str = ""
    immutable_structure: str = ""
    season_variants: Dict[str, str] = field(default_factory=dict)
    weather_variants: Dict[str, str] = field(default_factory=dict)
    time_variants: Dict[str, str] = field(default_factory=dict)
    reference_image_ids: List[str] = field(default_factory=list)


@dataclass
class VisualBible(BaseModel):
    """视觉圣经"""
    novel_id: str = ""
    art_direction: str = ""
    color_script: str = ""
    cinematography_rules: List[str] = field(default_factory=list)
    character_profiles: Dict[str, CharacterVisualProfile] = field(default_factory=dict)
    scene_profiles: Dict[str, SceneCanonicalProfile] = field(default_factory=dict)


@dataclass
class VideoAsset(BaseModel):
    """生成资产（角色图、场景图、镜头图、视频片段）"""
    asset_id: str = ""
    asset_type: str = ""  # character_portrait | scene_reference | shot_reference | video_clip
    shot_id: Optional[str] = None
    character_id: Optional[str] = None
    scene_id: Optional[str] = None
    age_stage: Optional[str] = None
    season: Optional[str] = None
    weather: Optional[str] = None
    time_of_day: Optional[str] = None
    provider: str = ""
    uri: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class AssetManifest(BaseModel):
    """资产索引"""
    novel_id: str = ""
    assets: List[VideoAsset] = field(default_factory=list)


@dataclass
class VideoRenderPlan(BaseModel):
    """视频渲染计划"""
    novel_id: str = ""
    shot_asset_map: Dict[str, List[str]] = field(default_factory=dict)  # shot_id -> asset_id list
    soundtrack_hint: str = ""
    subtitle_policy: str = "burned"


@dataclass
class ConsistencyIssue(BaseModel):
    """一致性问题"""
    issue_id: str = ""
    level: str = "warning"  # warning | error
    issue_type: str = ""  # character_identity | age_progression | scene_structure
    target_id: str = ""
    description: str = ""
    score: float = 0.0
    threshold: float = 0.0
    measured: float = 0.0


@dataclass
class ConsistencyMetrics(BaseModel):
    """一致性量化指标"""
    face_consistency: float = 0.0
    age_transition: float = 0.0
    scene_structure: float = 0.0


@dataclass
class ConsistencyThresholds(BaseModel):
    """一致性阈值"""
    face_consistency_min: float = 0.82
    age_transition_min: float = 0.58
    scene_structure_min: float = 0.76


@dataclass
class ConsistencyReport(BaseModel):
    """一致性检查报告"""
    novel_id: str = ""
    passed: bool = True
    metrics: ConsistencyMetrics = field(default_factory=ConsistencyMetrics)
    thresholds: ConsistencyThresholds = field(default_factory=ConsistencyThresholds)
    issues: List[ConsistencyIssue] = field(default_factory=list)
    fallback_reasons: List[str] = field(default_factory=list)


@dataclass
class VideoOutput(BaseModel):
    """最终视频输出"""
    novel_id: str = ""
    video_uri: str = ""
    clip_uris: List[str] = field(default_factory=list)
    duration_sec: float = 0.0
    fps: int = 24


@dataclass
class VideoState(BaseModel):
    """视频阶段独立状态（与 NovelState 解耦）"""
    novel_id: str = ""
    status: str = "pending"  # pending | scripted | bibled | asseted | rendered | failed
    script: Optional[VideoScript] = None
    visual_bible: Optional[VisualBible] = None
    manifest: Optional[AssetManifest] = None
    render_plan: Optional[VideoRenderPlan] = None
    consistency_report: Optional[ConsistencyReport] = None
    output: Optional[VideoOutput] = None
    error_message: str = ""
