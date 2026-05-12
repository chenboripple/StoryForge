"""IP 衍生生成（角色卡片 / 故事圣经）(v1 API)"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.storage import StorageManager

from web_console.dependencies import get_storage_manager_dep
from web_console.services import ip as ip_service

router = APIRouter(tags=["ip"])


@router.get("/ip/{novel_id}/story_bible")
async def get_story_bible(novel_id: str, sm: StorageManager = Depends(get_storage_manager_dep)) -> dict:
    bible = sm.load_story_bible(novel_id)
    if not bible:
        raise HTTPException(status_code=404, detail="story bible not found")
    return {"novel_id": novel_id, "story_bible": bible.to_dict()}


@router.get("/ip/{novel_id}/character/{character_id}")
async def get_character_ip(
    novel_id: str,
    character_id: str,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    bible = sm.load_story_bible(novel_id)
    if not bible:
        raise HTTPException(status_code=404, detail="story bible not found")
    char_ip = bible.get_character(character_id)
    if not char_ip:
        raise HTTPException(status_code=404, detail="character ip not found")
    return {"novel_id": novel_id, "character_id": character_id, "character_ip": char_ip.to_dict()}
