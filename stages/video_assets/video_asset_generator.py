"""
Video asset 生成器（角色定妆、场景定场、镜头参考）
"""
from __future__ import annotations

from typing import List

from core.models.video_assets import AssetManifest, VideoAsset, VideoScript, VisualBible
from core.video.providers import ImageGenRequest, ImageProvider


class VideoAssetGenerator:
    def __init__(self, image_provider: ImageProvider):
        self.image_provider = image_provider

    def generate(self, novel_id: str, script: VideoScript, bible: VisualBible) -> AssetManifest:
        assets: List[VideoAsset] = []

        # 1) 角色定妆图
        for char_id, profile in bible.character_profiles.items():
            age_variants = profile.age_variants or {
                "adult": "adult face, stable posture",
            }
            for age_stage, age_hint in age_variants.items():
                req = ImageGenRequest(
                    prompt=f"character portrait: {profile.display_name}, {age_hint}",
                    identity_seed=profile.identity_seed,
                    metadata={
                        "type": "character_portrait",
                        "character_id": char_id,
                        "age_stage": age_stage,
                    },
                )
                resp = self.image_provider.generate(req)
                asset_id = f"char:{char_id}:portrait:{age_stage}"
                assets.append(
                    VideoAsset(
                        asset_id=asset_id,
                        asset_type="character_portrait",
                        character_id=char_id,
                        age_stage=age_stage,
                        provider=resp.provider,
                        uri=resp.uri,
                        metadata=resp.metadata,
                    )
                )
                profile.reference_image_ids.append(asset_id)

        # 2) 场景定场图
        for scene_id, profile in bible.scene_profiles.items():
            req = ImageGenRequest(
                prompt=f"scene reference: {profile.display_name}, stable architecture",
                metadata={"type": "scene_reference", "scene_id": scene_id},
            )
            resp = self.image_provider.generate(req)
            asset_id = f"scene:{scene_id}:reference"
            assets.append(
                VideoAsset(
                    asset_id=asset_id,
                    asset_type="scene_reference",
                    scene_id=scene_id,
                    provider=resp.provider,
                    uri=resp.uri,
                    metadata=resp.metadata,
                )
            )
            profile.reference_image_ids.append(asset_id)

        # 3) 镜头参考图
        for shot in script.shots:
            req = ImageGenRequest(
                prompt=shot.visual_prompt,
                metadata={"type": "shot_reference", "shot_id": shot.shot_id},
            )
            resp = self.image_provider.generate(req)
            assets.append(
                VideoAsset(
                    asset_id=f"shot:{shot.shot_id}:reference",
                    asset_type="shot_reference",
                    shot_id=shot.shot_id,
                    scene_id=shot.scene_id,
                    provider=resp.provider,
                    uri=resp.uri,
                    metadata=resp.metadata,
                )
            )

        return AssetManifest(novel_id=novel_id, assets=assets)
