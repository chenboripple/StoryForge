"""视频剧本生成与一致性检查端点。"""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.storage import StorageManager

from web_console.dependencies import get_storage_manager_dep
from web_console.services.video import (
    _check_video_consistency,
    _generate_video_script_assets,
)
from web_console.utils import _resolve_project_dir

router = APIRouter()


class GenerateVideoScriptRequest(BaseModel):
    project_dir: str
    novel_id: str


class CheckVideoConsistencyRequest(BaseModel):
    project_dir: str
    novel_id: str
    face_consistency_min: float = Field(default=0.82, ge=0.0, le=1.0)
    age_transition_min: float = Field(default=0.58, ge=0.0, le=1.0)
    scene_structure_min: float = Field(default=0.76, ge=0.0, le=1.0)


@router.post("/api/video/script/generate")
async def generate_video_script(
    req: GenerateVideoScriptRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    project_dir = _resolve_project_dir(req.project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")

    novel_id = req.novel_id.strip()
    if not novel_id:
        raise HTTPException(status_code=400, detail="novel_id 不能为空")

    try:
        result = _generate_video_script_assets(project_dir, novel_id, sm)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"ok": True, "result": result}


@router.post("/api/video/consistency/check")
async def check_video_consistency(
    req: CheckVideoConsistencyRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    project_dir = _resolve_project_dir(req.project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")

    novel_id = req.novel_id.strip()
    if not novel_id:
        raise HTTPException(status_code=400, detail="novel_id 不能为空")

    try:
        report = _check_video_consistency(
            project_dir,
            novel_id,
            thresholds={
                "face_consistency_min": req.face_consistency_min,
                "age_transition_min": req.age_transition_min,
                "scene_structure_min": req.scene_structure_min,
            },
            sm=sm,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"ok": True, "report": report}


@router.get("/api/video/consistency/{novel_id}")
async def get_video_consistency(
    novel_id: str,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    report = sm.load_video_consistency_report(novel_id)
    if not report:
        raise HTTPException(status_code=404, detail="未找到一致性报告")
    return {"ok": True, "report": report.to_dict()}
