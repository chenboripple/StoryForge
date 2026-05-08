"""
Outline - 大纲数据
总纲、卷纲、章级细纲
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .base import BaseModel


@dataclass
class ChapterOutline(BaseModel):
    """章级细纲"""
    chapter_num: int = 1
    title: str = ""
    theme: str = ""  # 主题
    plot: str = ""   # 情节概要
    scenes: List[str] = field(default_factory=list)  # 场景列表
    hooks: List[str] = field(default_factory=list)   # 钩子/伏笔
    characters_involved: List[str] = field(default_factory=list)  # 出场人物
    words_target: int = 3000
    key_conflicts: List[str] = field(default_factory=list)  # 关键冲突
    foreshadowings: List[str] = field(default_factory=list)  # 本章节埋下的伏笔


@dataclass
class VolumeOutline(BaseModel):
    """卷纲"""
    volume_num: int = 0
    title: str = ""
    theme: str = ""
    chapter_range: str = ""  # "1-10"
    summary: str = ""
    key_events: List[str] = field(default_factory=list)
    chapter_outlines: Dict[int, ChapterOutline] = field(default_factory=dict)


@dataclass
class Outline(BaseModel):
    """完整大纲"""
    novel_id: str = ""
    logline: str = ""  # 一句话梗概
    core_concept: str = ""  # 核心概念
    themes: List[str] = field(default_factory=list)  # 主题
    tone: str = ""  # 整体基调
    target_audience: str = ""  # 目标读者
    world_overview: str = ""  # 世界观概述

    # 总大纲
    overall_outline: str = ""

    # 卷纲
    volume_outlines: Dict[int, VolumeOutline] = field(default_factory=dict)

    # 章级细纲
    chapter_outlines: Dict[int, ChapterOutline] = field(default_factory=dict)

    def get_chapter_outline(self, chapter_num: int) -> Optional[ChapterOutline]:
        return self.chapter_outlines.get(chapter_num)

    def get_volume_for_chapter(self, chapter_num: int) -> Optional[VolumeOutline]:
        volume_num = (chapter_num - 1) // 10
        return self.volume_outlines.get(volume_num)
