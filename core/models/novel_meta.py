"""
NovelMeta - 小说元数据
整本书的基础信息、当前状态索引
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum

from .base import BaseModel


class PipelineStage(Enum):
    """Pipeline 阶段"""
    CREATION = "creation"
    EXTRACTION = "extraction"
    IP_GENERATION = "ip_generation"
    VIDEO_GENERATION = "video_generation"
    COMPLETED = "completed"


@dataclass
class NovelMeta(BaseModel):
    """小说元数据（索引级，轻量）"""
    novel_id: str = ""
    novel_title: str = ""
    genre: str = ""
    concept: str = ""  # 一句话概念
    target_word_count: int = 3000
    current_stage: PipelineStage = PipelineStage.CREATION
    current_chapter: int = 1
    total_chapters: int = 0
    approved_chapters: int = 0
    draft_chapters: int = 0
    review_chapters: int = 0
    rejected_chapters: int = 0

    # 各数据文件的路径（相对 novels/<id>/ 目录）
    outline_file: str = "outline.json"
    characters_file: str = "characters.json"
    world_setting_file: str = "world_setting.json"
    chapters_dir: str = "chapters"
    reviews_dir: str = "reviews"
    proofreads_dir: str = "proofreads"
    extractions_dir: str = "extractions"
    ip_assets_dir: str = "ip_assets"
    agent_comm_dir: str = "agent_comm"

    # 章节索引
    chapter_files: Dict[int, str] = field(default_factory=dict)

    # 控制字段
    error_message: str = ""
    should_pause: bool = False

    def get_stage_label(self) -> str:
        labels = {
            PipelineStage.CREATION: "创作中",
            PipelineStage.EXTRACTION: "萃取中",
            PipelineStage.IP_GENERATION: "IP生成中",
            PipelineStage.VIDEO_GENERATION: "视频生成中",
            PipelineStage.COMPLETED: "已完成",
        }
        return labels.get(self.current_stage, "未知")

    def get_progress(self) -> Dict[str, int]:
        """获取创作进度统计"""
        return {
            "total": self.total_chapters,
            "approved": self.approved_chapters,
            "draft": self.draft_chapters,
            "in_review": self.review_chapters,
            "rejected": self.rejected_chapters,
        }

    def to_index_entry(self) -> Dict[str, any]:
        """生成轻量索引条目"""
        return {
            "novel_id": self.novel_id,
            "novel_title": self.novel_title,
            "genre": self.genre,
            "concept": self.concept[:120] if self.concept else "",
            "current_stage": self.current_stage.value,
            "current_chapter": self.current_chapter,
            "total_chapters": self.total_chapters,
            "approved_chapters": self.approved_chapters,
            "progress_percent": round(self.approved_chapters / max(self.total_chapters, 1) * 100, 1),
        }
