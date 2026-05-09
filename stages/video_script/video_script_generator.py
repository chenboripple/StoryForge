"""
Video script 生成器
"""
from __future__ import annotations

from typing import Dict

from core.models.video_assets import ShotSpec, VideoScript
from core.models.chapter import Chapter


class VideoScriptGenerator:
    def generate(self, novel_id: str, title: str, chapters: Dict[int, Chapter]) -> VideoScript:
        shots = []
        sequence = 1
        for chapter_num in sorted(chapters.keys()):
            chapter = chapters[chapter_num]
            text = chapter.content or ""
            preview = text[:80] if text else f"第{chapter_num}章"
            shots.append(
                ShotSpec(
                    shot_id=f"ch{chapter_num:03d}_s001",
                    chapter=chapter_num,
                    sequence=sequence,
                    duration_sec=5.0,
                    camera_language="medium shot",
                    scene_id=f"scene_ch{chapter_num:03d}",
                    season="spring",
                    weather="clear",
                    time_of_day="day",
                    action=preview,
                    visual_prompt=f"cinematic scene from chapter {chapter_num}: {preview}",
                )
            )
            sequence += 1

        return VideoScript(novel_id=novel_id, title=title, shots=shots)
