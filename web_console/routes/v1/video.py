"""视频生成相关端点（骨架，可接入）(v1 API)"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.storage import StorageManager

from web_console.dependencies import get_storage_manager_dep
from web_console.services import video as video_service

router = APIRouter(tags=["video"])


class VideoScriptRequest(BaseModel):
    chapter_numbers: list[int] = Field(default_factory=list)
    style: str = "cinematic"


@router.get("/video/{novel_id}/state")
async def get_video_state(novel_id: str, sm: StorageManager = Depends(get_storage_manager_dep)) -> dict:
    state = sm.load_video_state(novel_id)
    return {"novel_id": novel_id, "state": state.to_dict() if state else None}


@router.get("/video/{novel_id}/script")
async def get_video_script(novel_id: str, sm: StorageManager = Depends(get_storage_manager_dep)) -> dict:
    script = sm.load_video_script(novel_id)
    if not script:
        raise HTTPException(status_code=404, detail="video script not found")
    return {"novel_id": novel_id, "script": script.to_dict()}


@router.post("/video/{novel_id}/script/generate")
async def generate_video_script(
    novel_id: str,
    req: VideoScriptRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    result = video_service.generate_video_script(novel_id, req.chapter_numbers, req.style, sm)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "生成失败")
    return {"success": True, "script": result.script.to_dict() if result.script else None}


@router.get("/video/{novel_id}/visual_bible")
async def get_visual_bible(novel_id: str, sm: StorageManager = Depends(get_storage_manager_dep)) -> dict:
    vb = sm.load_visual_bible(novel_id)
    if not vb:
        raise HTTPException(status_code=404, detail="visual bible not found")
    return {"novel_id": novel_id, "visual_bible": vb.to_dict()}


@router.post("/video/{novel_id}/visual_bible/generate")
async def generate_visual_bible(
    novel_id: str,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    result = video_service.generate_visual_bible(novel_id, sm)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "生成失败")
    return {"success": True, "visual_bible": result.visual_bible.to_dict() if result.visual_bible else None}


@router.get("/video/{novel_id}/consistency")
async def get_consistency_report(novel_id: str, sm: StorageManager = Depends(get_storage_manager_dep)) -> dict:
    report = sm.load_video_consistency_report(novel_id)
    state = sm.load_video_state(novel_id)
    return {
        "novel_id": novel_id,
        "report": report.to_dict() if report else None,
        "state": state.to_dict() if state else None,
    }


@router.post("/video/{novel_id}/consistency/check")
async def check_consistency(
    novel_id: str,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    result = video_service.check_consistency(novel_id, sm)
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "检查失败")
    return {
        "success": True,
        "passed": result.passed,
        "report": result.report.to_dict() if result.report else None,
    }
