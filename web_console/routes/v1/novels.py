"""小说与章节资源端点 (v1 API)"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.models import NovelMeta, PipelineStage
from core.storage import StorageManager

from web_console.dependencies import get_storage_manager_dep
from web_console.services import character_visuals as character_visual_service
from web_console.services.novels import _discover_novels
from web_console.utils import _resolve_project_dir

router = APIRouter(tags=["novels"])


class CreateNovelRequest(BaseModel):
    novel_id: str
    novel_title: Optional[str] = None
    genre: str = "未分类"
    concept: str = ""
    target_word_count: int = 3000


class CharacterVisualGenerateRequest(BaseModel):
    prompt: str = ""
    slot_type: str = "main"  # main | gallery | video
    index: Optional[int] = None
    style: str = ""
    image_preset: str = "720p"
    aspect_ratio: str = "16:9"
    regenerate_all: bool = False  # 仅对 video 有效：若为 True，清空所有并重生成


class CharacterVisualFinalizeRequest(BaseModel):
    finalized: bool = True


@router.get("/novels")
async def list_novels(
    project_dir: Optional[str] = Query(None, description="项目目录（console模式可选）"),
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> Any:
    # 兼容历史行为：不传 project_dir 时返回索引列表。
    if project_dir is None or not project_dir.strip():
        return sm.list_novels()

    project_dir = _resolve_project_dir(project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")
    return {"novels": _discover_novels(project_dir, sm)}


@router.post("/novels")
async def create_novel(
    req: CreateNovelRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    novel_id = req.novel_id.strip()
    if not novel_id:
        raise HTTPException(status_code=400, detail="缺少小说ID")
    if sm.novel_exists(novel_id):
        raise HTTPException(status_code=409, detail=f"小说已存在: {novel_id}")

    meta = NovelMeta(
        novel_id=novel_id,
        novel_title=(req.novel_title or novel_id).strip(),
        genre=req.genre,
        concept=req.concept,
        target_word_count=req.target_word_count,
        current_stage=PipelineStage.CREATION,
        current_chapter=1,
        total_chapters=0,
        approved_chapters=0,
    )
    sm.save_novel_meta(novel_id, meta)
    sm.rebuild_index()
    return {"success": True, "novel_id": novel_id, "novel_title": meta.novel_title}


@router.get("/novels/{novel_id}")
async def get_novel(
    novel_id: str,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    result = meta.to_index_entry()
    characters_list: List[Dict[str, Any]] = []
    try:
        char_graph = sm.load_characters(novel_id)
        if char_graph and getattr(char_graph, "characters", None):
            for char in char_graph.characters:
                char_dict: Dict[str, Any] = {}
                if hasattr(char, "to_dict"):
                    try:
                        char_dict = char.to_dict()
                    except Exception:
                        pass
                if not char_dict:
                    char_dict = {
                        "id": getattr(char, "character_id", getattr(char, "id", "")),
                        "character_id": getattr(char, "character_id", ""),
                        "name": getattr(char, "name", ""),
                        "description": getattr(char, "description", ""),
                        "personality": getattr(char, "personality", ""),
                        "age": getattr(char, "age", None),
                        "gender": getattr(char, "gender", ""),
                    }
                characters_list.append(char_dict)
    except Exception:
        pass

    result["characters"] = characters_list
    return result


@router.get("/novels/{novel_id}/chapters")
async def list_chapters(
    novel_id: str,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    chapters = sm.load_chapters(novel_id)
    reviews = sm.load_reviews(novel_id)

    result = []
    for num in sorted(chapters.keys()):
        ch = chapters[num]
        review = reviews.get(num)
        latest = review.get_latest() if review else None
        result.append(
            {
                "chapter_num": num,
                "title": ch.title,
                "status": ch.status.value,
                "word_count": ch.word_count,
                "preview": ch.get_preview(),
                "review_rounds": len(review.records) if review else 0,
                "latest_score": latest.total_score if latest else None,
                "latest_passed": latest.passed if latest else None,
            }
        )

    return {
        "novel_id": novel_id,
        "current_chapter": meta.current_chapter,
        "total_chapters": meta.total_chapters,
        "chapters": result,
    }


@router.get("/novels/{novel_id}/chapters/{chapter_num}")
async def get_chapter(
    novel_id: str,
    chapter_num: int,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    chapters = sm.load_chapters(novel_id)
    ch = chapters.get(chapter_num)
    if ch is None:
        raise HTTPException(status_code=404, detail=f"chapter not found: {chapter_num}")

    reviews = sm.load_reviews(novel_id)
    review = reviews.get(chapter_num)
    proofreads = sm.load_proofreads(novel_id)
    proofread = proofreads.get(chapter_num)

    return {
        "novel_id": novel_id,
        "chapter_num": chapter_num,
        "title": ch.title,
        "status": ch.status.value,
        "content": ch.content,
        "word_count": ch.word_count,
        "reviews": [r.to_dict() for r in (review.records if review else [])],
        "proofread_records": [p.to_dict() for p in (proofread.records if proofread else [])],
    }


@router.get("/novels/{novel_id}/characters")
async def list_novel_characters(
    novel_id: str,
    project_dir: str = Query(..., description="项目目录"),
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    project_dir = _resolve_project_dir(project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")

    for item in _discover_novels(project_dir, sm):
        if item["novel_id"] == novel_id:
            return {"novel_id": novel_id, "characters": item.get("characters", [])}

    raise HTTPException(status_code=404, detail=f"小说不存在: {novel_id}")


@router.get("/novels/{novel_id}/characters/{character_id}/visuals")
async def get_character_visuals(
    novel_id: str,
    character_id: str,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    try:
        return character_visual_service.get_character_visuals(sm, novel_id, character_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取角色形象失败: {exc}") from exc


@router.post("/novels/{novel_id}/characters/{character_id}/visuals/generate")
async def generate_character_visuals(
    novel_id: str,
    character_id: str,
    req: CharacterVisualGenerateRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    try:
        return character_visual_service.generate_character_visual(
            sm=sm,
            novel_id=novel_id,
            character_id=character_id,
            prompt=req.prompt,
            slot_type=req.slot_type,
            index=req.index,
            style=req.style,
            image_preset=req.image_preset,
            aspect_ratio=req.aspect_ratio,
            regenerate_all=req.regenerate_all,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"生成角色形象失败: {exc}") from exc


@router.post("/novels/{novel_id}/characters/{character_id}/visuals/finalize")
async def finalize_character_visuals(
    novel_id: str,
    character_id: str,
    req: CharacterVisualFinalizeRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    try:
        return character_visual_service.finalize_character_visuals(
            sm=sm,
            novel_id=novel_id,
            character_id=character_id,
            finalized=req.finalized,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"更新定稿状态失败: {exc}") from exc
