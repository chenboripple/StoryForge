"""视频剧本/视觉圣经/资产骨架生成 + 一致性检查。"""

from __future__ import annotations

from core.models.video import VideoState
from core.storage import StorageManager
from core.video import StubEmbeddingProvider, StubImageProvider, VideoConsistencyService
from core.video.workflow import (
    build_visual_bible_for_novel,
    generate_video_assets_for_novel,
    generate_video_script_for_novel,
    validate_video_consistency_for_novel,
)
from stages.video_assets.video_asset_generator import VideoAssetGenerator
from stages.video_bible.visual_bible_builder import VisualBibleBuilder
from stages.video_script.video_script_generator import VideoScriptGenerator


def _generate_video_script_assets(project_dir: str, novel_id: str, sm: StorageManager) -> dict:
    _ = project_dir
    meta = sm.load_novel_meta(novel_id)
    if not meta:
        raise RuntimeError(f"未找到小说: {novel_id}")

    chapters = sm.load_chapters(novel_id)
    if not chapters:
        raise RuntimeError(f"小说无章节内容: {novel_id}")

    script = generate_video_script_for_novel(sm, novel_id, VideoScriptGenerator())
    bible = build_visual_bible_for_novel(sm, novel_id, VisualBibleBuilder())
    manifest = generate_video_assets_for_novel(sm, novel_id, VideoAssetGenerator(image_provider=StubImageProvider()))

    state = sm.load_video_state(novel_id) or VideoState(novel_id=novel_id)
    state.script = script
    state.visual_bible = bible
    state.manifest = manifest
    state.status = "asseted"
    state.error_message = ""
    sm.save_video_state(novel_id, state)

    return {
        "novel_id": novel_id,
        "shot_count": len(script.shots),
        "character_profile_count": len(bible.character_profiles),
        "scene_profile_count": len(bible.scene_profiles),
        "asset_count": len(manifest.assets),
    }


def _check_video_consistency(project_dir: str, novel_id: str, thresholds: dict, sm: StorageManager) -> dict:
    _ = project_dir
    bible = sm.load_visual_bible(novel_id)
    manifest = sm.load_video_manifest(novel_id)
    if not bible or not manifest:
        raise RuntimeError("缺少视觉圣经或资产索引，请先生成视频剧本与资产")

    report = validate_video_consistency_for_novel(
        sm,
        novel_id,
        VideoConsistencyService(embedding_provider=StubEmbeddingProvider()),
        threshold_overrides=thresholds,
    )

    return report.to_dict()
