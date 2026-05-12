"""视频剧本/视觉圣经/资产骨架生成 + 一致性检查。"""

from __future__ import annotations

from core.models.video_assets import VideoState
from core.storage import StorageManager
from core.video import StubEmbeddingProvider, StubImageProvider, VideoConsistencyService
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

    chars = sm.load_characters(novel_id)

    script_generator = VideoScriptGenerator()
    bible_builder = VisualBibleBuilder()
    asset_generator = VideoAssetGenerator(image_provider=StubImageProvider())

    script = script_generator.generate(
        novel_id=novel_id,
        title=meta.novel_title or novel_id,
        chapters=chapters,
    )
    bible = bible_builder.build(novel_id, script, chars)
    manifest = asset_generator.generate(novel_id, script, bible)

    sm.save_video_script(novel_id, script)
    sm.save_visual_bible(novel_id, bible)
    sm.save_video_manifest(novel_id, manifest)

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

    service = VideoConsistencyService(embedding_provider=StubEmbeddingProvider())
    report = service.validate(
        novel_id=novel_id,
        bible=bible,
        manifest=manifest,
        threshold_overrides=thresholds,
    )
    sm.save_video_consistency_report(novel_id, report)

    state = sm.load_video_state(novel_id) or VideoState(novel_id=novel_id)
    state.consistency_report = report
    state.status = "asseted" if report.passed else "failed"
    state.error_message = "\n".join(report.fallback_reasons) if report.fallback_reasons else ""
    sm.save_video_state(novel_id, state)

    return report.to_dict()
