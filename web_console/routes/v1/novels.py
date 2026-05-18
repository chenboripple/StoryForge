"""小说与章节资源端点 (v1 API)"""

from __future__ import annotations

import os
import shlex
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from core.models import Character, CharacterGraph, NovelMeta, Outline, PipelineStage, WorldSetting
from core.storage import StorageManager

from web_console.dependencies import get_storage_manager_dep, get_task_registry
from web_console.runtime.models import QueueTask, TaskRuntime
from web_console.runtime.registry import TaskRegistry
from web_console.services import character_visuals as character_visual_service
from web_console.services import novel_cover as novel_cover_service
from web_console.services import visual_tasks as visual_task_service
from web_console.services.novels import _discover_novels
from web_console.utils import _now, _resolve_project_dir

router = APIRouter(tags=["novels"])


class CreateNovelRequest(BaseModel):
    novel_id: str
    novel_title: Optional[str] = None
    genre: str = "未分类"
    concept: str = ""
    target_word_count: int = 3000
    outline: str = ""
    characters: List[Dict[str, Any]] = []
    world_setting: str = ""


class NovelChapterGenerateRequest(BaseModel):
    chapter_num: Optional[int] = None


class ChapterProofreadRequest(BaseModel):
    scope: str = "chapter"  # chapter | volume | book
    chapter_num: Optional[int] = None
    volume_num: Optional[int] = None


class NovelReorderRequest(BaseModel):
    novel_ids: List[str]


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


class NovelCoverGenerateRequest(BaseModel):
    prompt: str = ""
    style: str = ""
    image_preset: str = "720p"
    aspect_ratio: str = "16:9"


def _enqueue_pipeline_command(
    registry: TaskRegistry,
    *,
    command: str,
    project_dir: Optional[str] = None,
) -> TaskRuntime:
    task_id = str(uuid.uuid4())
    task = TaskRuntime(
        task_id=task_id,
        project_dir=project_dir or os.getcwd(),
        command=command,
        created_at=_now(),
        status="queued",
    )
    with registry.task_cond:
        registry.tasks[task_id] = task
        registry.task_queue.append(QueueTask(task_id=task_id, task_type="pipeline"))
        registry._save_state_unlocked()
        registry.task_cond.notify_all()
    return task


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

    # 保存基础创作素材，避免“只创建元数据，不可继续生成”的断层。
    if (req.outline or "").strip():
        sm.save_outline(
            novel_id,
            Outline(
                novel_id=novel_id,
                core_concept=req.concept,
                overall_outline=req.outline.strip(),
            ),
        )

    if req.characters:
        normalized_chars: List[Character] = []
        for idx, raw in enumerate(req.characters, start=1):
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or "").strip()
            if not name:
                continue
            char_id = str(raw.get("id") or raw.get("character_id") or f"char_{idx}").strip() or f"char_{idx}"
            goals_raw = raw.get("goals")
            if isinstance(goals_raw, list):
                goals = [str(x).strip() for x in goals_raw if str(x).strip()]
            else:
                goals = [x.strip() for x in str(goals_raw or "").split("\n") if x.strip()]
            normalized_chars.append(
                Character(
                    character_id=char_id,
                    name=name,
                    role=str(raw.get("role") or "supporting"),
                    description=str(raw.get("description") or ""),
                    personality=str(raw.get("personality") or ""),
                    background=str(raw.get("background") or ""),
                    goals=goals,
                )
            )
        if normalized_chars:
            sm.save_characters(
                novel_id,
                CharacterGraph(novel_id=novel_id, characters=normalized_chars),
            )

    if (req.world_setting or "").strip():
        sm.save_world(
            novel_id,
            WorldSetting(name=f"{meta.novel_title} 世界", overview=req.world_setting.strip()),
        )

    sm.rebuild_index()
    return {"success": True, "novel_id": novel_id, "novel_title": meta.novel_title}


@router.post("/novels/reorder")
async def reorder_novels(
    req: NovelReorderRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    ids = [str(x or "").strip() for x in req.novel_ids]
    ids = [x for x in ids if x]
    if not ids:
        raise HTTPException(status_code=400, detail="novel_ids 不能为空")

    count = sm.reorder_novels(ids)
    return {"success": True, "count": count, "novel_ids": ids}


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


@router.get("/novels/{novel_id}/context")
async def get_novel_context(
    novel_id: str,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    outline = sm.load_outline(novel_id)
    world = sm.load_world(novel_id)

    timeline: List[Dict[str, Any]] = []
    if world and getattr(world, "timeline", None):
        for evt in world.timeline:
            try:
                timeline.append(evt.to_dict())
            except Exception:
                timeline.append({
                    "chapter": getattr(evt, "chapter", 0),
                    "timestamp": getattr(evt, "timestamp", ""),
                    "description": getattr(evt, "description", ""),
                })
    timeline.sort(key=lambda x: int(x.get("chapter") or 0))

    return {
        "novel_id": novel_id,
        "concept": meta.concept,
        "outline": {
            "overall_outline": getattr(outline, "overall_outline", "") if outline else "",
            "core_concept": getattr(outline, "core_concept", "") if outline else "",
            "themes": getattr(outline, "themes", []) if outline else [],
            "world_overview": getattr(outline, "world_overview", "") if outline else "",
        },
        "world": {
            "name": getattr(world, "name", "") if world else "",
            "overview": getattr(world, "overview", "") if world else "",
            "history": getattr(world, "history", "") if world else "",
            "rules": getattr(world, "rules", []) if world else [],
            "technology_level": getattr(world, "technology_level", "") if world else "",
            "magic_system": getattr(world, "magic_system", "") if world else "",
        },
        "timeline": timeline,
    }


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


@router.get("/novels/{novel_id}/cover")
async def get_novel_cover(
    novel_id: str,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    try:
        return novel_cover_service.get_novel_cover(sm, novel_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"读取小说封面失败: {exc}") from exc


@router.post("/novels/{novel_id}/cover/generate")
async def generate_novel_cover(
    novel_id: str,
    req: NovelCoverGenerateRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
    registry: TaskRegistry = Depends(get_task_registry),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    try:
        return visual_task_service.enqueue_novel_cover_task(
            registry=registry,
            novel_id=novel_id,
            prompt=req.prompt,
            style=req.style,
            image_preset=req.image_preset,
            aspect_ratio=req.aspect_ratio,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"提交小说封面任务失败: {exc}") from exc


@router.post("/novels/{novel_id}/characters/{character_id}/visuals/generate")
async def generate_character_visuals(
    novel_id: str,
    character_id: str,
    req: CharacterVisualGenerateRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
    registry: TaskRegistry = Depends(get_task_registry),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    try:
        return visual_task_service.enqueue_character_visual_task(
            registry=registry,
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
        raise HTTPException(status_code=500, detail=f"提交角色形象任务失败: {exc}") from exc


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


@router.post("/novels/{novel_id}/chapters/generate")
async def generate_novel_chapter(
    novel_id: str,
    req: NovelChapterGenerateRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
    registry: TaskRegistry = Depends(get_task_registry),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    chapter_num = req.chapter_num if isinstance(req.chapter_num, int) and req.chapter_num > 0 else int(meta.current_chapter or 1)
    command = (
        "python -m web_console.scripts.run_novel_chapter "
        f"--novel-id {shlex.quote(novel_id)} --chapter {chapter_num}"
    )
    task = _enqueue_pipeline_command(registry, command=command)

    return {
        "task_id": task.task_id,
        "status": "queued",
        "task_type": "pipeline",
        "novel_id": novel_id,
        "chapter_num": chapter_num,
        "command": command,
    }


@router.post("/novels/{novel_id}/chapters/next")
async def generate_next_chapter(
    novel_id: str,
    sm: StorageManager = Depends(get_storage_manager_dep),
    registry: TaskRegistry = Depends(get_task_registry),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    chapter_num = int(meta.current_chapter or 1)
    command = (
        "python -m web_console.scripts.run_novel_chapter "
        f"--novel-id {shlex.quote(novel_id)} --chapter {chapter_num}"
    )
    task = _enqueue_pipeline_command(registry, command=command)
    return {
        "task_id": task.task_id,
        "status": "queued",
        "task_type": "pipeline",
        "novel_id": novel_id,
        "chapter_num": chapter_num,
        "action": "generate_next",
    }


@router.post("/novels/{novel_id}/chapters/{chapter_num}/revise")
async def revise_chapter(
    novel_id: str,
    chapter_num: int,
    sm: StorageManager = Depends(get_storage_manager_dep),
    registry: TaskRegistry = Depends(get_task_registry),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")
    if chapter_num <= 0:
        raise HTTPException(status_code=400, detail="chapter_num 必须大于 0")

    command = (
        "python -m web_console.scripts.run_novel_chapter "
        f"--novel-id {shlex.quote(novel_id)} --chapter {chapter_num}"
    )
    task = _enqueue_pipeline_command(registry, command=command)
    return {
        "task_id": task.task_id,
        "status": "queued",
        "task_type": "pipeline",
        "novel_id": novel_id,
        "chapter_num": chapter_num,
        "action": "revise_chapter",
    }


@router.post("/novels/{novel_id}/chapters/proofread")
async def proofread_chapters(
    novel_id: str,
    req: ChapterProofreadRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
    registry: TaskRegistry = Depends(get_task_registry),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    scope = str(req.scope or "chapter").strip().lower()
    if scope not in {"chapter", "volume", "book"}:
        raise HTTPException(status_code=400, detail="scope 仅支持 chapter|volume|book")

    args: List[str] = [
        "python -m web_console.scripts.proofread_range",
        f"--novel-id {shlex.quote(novel_id)}",
        f"--scope {scope}",
    ]
    if isinstance(req.chapter_num, int) and req.chapter_num > 0:
        args.append(f"--chapter {req.chapter_num}")
    if isinstance(req.volume_num, int) and req.volume_num > 0:
        args.append(f"--volume {req.volume_num}")

    command = " ".join(args)
    task = _enqueue_pipeline_command(registry, command=command)
    return {
        "task_id": task.task_id,
        "status": "queued",
        "task_type": "pipeline",
        "novel_id": novel_id,
        "scope": scope,
        "chapter_num": req.chapter_num,
        "volume_num": req.volume_num,
        "action": "proofread",
    }
