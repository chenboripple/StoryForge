"""
Video 生成器（按镜头生成片段并汇总）
"""
from __future__ import annotations

from typing import Dict, List

from core.models.video import (
    AssetManifest,
    VideoOutput,
    VideoRenderPlan,
    VideoScript,
)
from core.video.providers import VideoGenRequest, VideoProvider


class VideoGenerator:
    def __init__(self, video_provider: VideoProvider):
        self.video_provider = video_provider

    def build_render_plan(self, novel_id: str, script: VideoScript, manifest: AssetManifest) -> VideoRenderPlan:
        by_shot: Dict[str, List[str]] = {}
        for shot in script.shots:
            related = [
                a.asset_id
                for a in manifest.assets
                if a.shot_id == shot.shot_id or a.scene_id == shot.scene_id
            ]
            by_shot[shot.shot_id] = related

        return VideoRenderPlan(
            novel_id=novel_id,
            shot_asset_map=by_shot,
            soundtrack_hint="cinematic ambient score",
            subtitle_policy="burned",
        )

    def generate(self, script: VideoScript, plan: VideoRenderPlan, manifest: AssetManifest) -> VideoOutput:
        clip_uris: List[str] = []
        total_duration = 0.0

        for shot in script.shots:
            references = []
            for aid in plan.shot_asset_map.get(shot.shot_id, []):
                for asset in manifest.assets:
                    if asset.asset_id == aid:
                        references.append(asset.uri)
                        break

            req = VideoGenRequest(
                prompt=f"shot {shot.shot_id}: {shot.action}",
                reference_uris=references,
                duration_sec=shot.duration_sec,
                fps=24,
                metadata={"shot_id": shot.shot_id},
            )
            resp = self.video_provider.generate(req)
            clip_uris.append(resp.uri)
            total_duration += resp.duration_sec

        return VideoOutput(
            novel_id=script.novel_id,
            video_uri=f"stub://video/final/{script.novel_id}",
            clip_uris=clip_uris,
            duration_sec=total_duration,
            fps=24,
        )
