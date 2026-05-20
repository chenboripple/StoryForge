"""Video 共享 workflow。"""

from __future__ import annotations

from core.models.video import AssetManifest, ConsistencyReport, VideoScript, VideoState, VisualBible
from core.storage import StorageManager
from stages.video_assets.video_asset_generator import VideoAssetGenerator
from stages.video_bible.visual_bible_builder import VisualBibleBuilder
from stages.video_script.video_script_generator import VideoScriptGenerator

from .consistency import VideoConsistencyService


def generate_video_script_for_novel(
    sm: StorageManager,
    novel_id: str,
    script_generator: VideoScriptGenerator,
) -> VideoScript:
    meta = sm.load_novel_meta(novel_id)
    chapters = sm.load_chapters(novel_id)
    script = script_generator.generate(
        novel_id=novel_id,
        title=meta.novel_title if meta else novel_id,
        chapters=chapters,
    )
    sm.save_video_script(novel_id, script)

    video_state = sm.load_video_state(novel_id) or VideoState(novel_id=novel_id)
    video_state.script = script
    video_state.status = "scripted"
    sm.save_video_state(novel_id, video_state)
    return script


def build_visual_bible_for_novel(
    sm: StorageManager,
    novel_id: str,
    bible_builder: VisualBibleBuilder,
) -> VisualBible:
    script = sm.load_video_script(novel_id)
    chars = sm.load_characters(novel_id)
    if not script:
        raise RuntimeError("缺少视频剧本，无法构建视觉圣经")

    bible = bible_builder.build(novel_id, script, chars)
    sm.save_visual_bible(novel_id, bible)

    video_state = sm.load_video_state(novel_id) or VideoState(novel_id=novel_id)
    video_state.visual_bible = bible
    video_state.status = "bibled"
    sm.save_video_state(novel_id, video_state)
    return bible


def generate_video_assets_for_novel(
    sm: StorageManager,
    novel_id: str,
    asset_generator: VideoAssetGenerator,
) -> AssetManifest:
    script = sm.load_video_script(novel_id)
    bible = sm.load_visual_bible(novel_id)
    if not script or not bible:
        raise RuntimeError("缺少视频剧本或视觉圣经，无法生成资产")

    manifest = asset_generator.generate(novel_id, script, bible)
    sm.save_visual_bible(novel_id, bible)
    sm.save_video_manifest(novel_id, manifest)

    video_state = sm.load_video_state(novel_id) or VideoState(novel_id=novel_id)
    video_state.visual_bible = bible
    video_state.manifest = manifest
    video_state.status = "asseted"
    sm.save_video_state(novel_id, video_state)
    return manifest


def validate_video_consistency_for_novel(
    sm: StorageManager,
    novel_id: str,
    consistency_service: VideoConsistencyService,
    threshold_overrides: dict | None = None,
) -> ConsistencyReport:
    bible = sm.load_visual_bible(novel_id)
    manifest = sm.load_video_manifest(novel_id)
    if not bible or not manifest:
        raise RuntimeError("缺少视觉圣经或资产索引，请先生成视频剧本与资产")

    report = consistency_service.validate(
        novel_id=novel_id,
        bible=bible,
        manifest=manifest,
        threshold_overrides=threshold_overrides,
    )
    sm.save_video_consistency_report(novel_id, report)

    video_state = sm.load_video_state(novel_id) or VideoState(novel_id=novel_id)
    video_state.consistency_report = report
    video_state.status = "asseted" if report.passed else "failed"
    video_state.error_message = "\n".join(report.fallback_reasons) if report.fallback_reasons else ""
    sm.save_video_state(novel_id, video_state)
    return report