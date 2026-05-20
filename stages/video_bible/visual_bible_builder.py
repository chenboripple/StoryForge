"""
Visual bible 构建器
"""
from __future__ import annotations

from typing import Dict

from core.models.video import (
    CharacterVisualProfile,
    SceneCanonicalProfile,
    VideoScript,
    VisualBible,
)
from core.models.world import CharacterGraph


class VisualBibleBuilder:
    def build(self, novel_id: str, script: VideoScript, chars: CharacterGraph | None) -> VisualBible:
        character_profiles: Dict[str, CharacterVisualProfile] = {}
        if chars:
            for c in chars.characters:
                cid = c.character_id or c.name
                if not cid:
                    continue
                character_profiles[cid] = CharacterVisualProfile(
                    character_id=cid,
                    display_name=c.name or cid,
                    identity_seed=f"{novel_id}:{cid}",
                    immutable_traits={
                        "face": c.face_description or c.appearance,
                        "body": c.posture or "",
                    },
                    age_variants={
                        "young": "younger face, energetic posture",
                        "adult": "adult face, stable posture",
                        "old": "older face with wrinkles, slower posture",
                    },
                )

        scene_profiles: Dict[str, SceneCanonicalProfile] = {}
        for shot in script.shots:
            if shot.scene_id in scene_profiles:
                continue
            scene_profiles[shot.scene_id] = SceneCanonicalProfile(
                scene_id=shot.scene_id,
                display_name=shot.scene_id,
                immutable_structure="keep architecture and layout stable",
                season_variants={
                    "spring": "fresh greens and soft light",
                    "summer": "lush vegetation and strong sunlight",
                    "autumn": "golden leaves and dry air",
                    "winter": "bare trees and cold light",
                },
                weather_variants={
                    "clear": "clear sky",
                    "rain": "wet surfaces and rain streaks",
                    "snow": "snow-covered ground",
                    "fog": "mist and low visibility",
                },
                time_variants={
                    "day": "daylight",
                    "dusk": "golden hour",
                    "night": "night scene with practical lights",
                },
            )

        return VisualBible(
            novel_id=novel_id,
            art_direction="cinematic realism",
            color_script="progressively darker palette toward climax",
            cinematography_rules=[
                "preserve character identity across all shots",
                "preserve scene structure and layout",
                "apply seasonal and time-of-day variants only",
            ],
            character_profiles=character_profiles,
            scene_profiles=scene_profiles,
        )
