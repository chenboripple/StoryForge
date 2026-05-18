"""视觉生成后台任务：角色图片与小说封面。"""

from __future__ import annotations

import uuid
from typing import Any, Dict

from web_console.dependencies import _new_storage_manager
from web_console.runtime.models import QueueTask, VisualTaskRuntime
from web_console.runtime.registry import TaskRegistry
from web_console.services import character_visuals, novel_cover
from web_console.utils import _now


def enqueue_character_visual_task(
    registry: TaskRegistry,
    *,
    novel_id: str,
    character_id: str,
    prompt: str,
    slot_type: str,
    index: int | None,
    style: str,
    image_preset: str,
    aspect_ratio: str,
    regenerate_all: bool,
) -> Dict[str, Any]:
    task_id = str(uuid.uuid4())
    task = VisualTaskRuntime(
        task_id=task_id,
        task_kind="character_visual",
        novel_id=novel_id,
        character_id=character_id,
        payload={
            "prompt": prompt,
            "slot_type": slot_type,
            "index": index,
            "style": style,
            "image_preset": image_preset,
            "aspect_ratio": aspect_ratio,
            "regenerate_all": regenerate_all,
        },
        created_at=_now(),
        status="queued",
    )

    with registry.task_cond:
        registry.visual_tasks[task_id] = task
        registry.task_queue.append(QueueTask(task_id=task_id, task_type="visual"))
        registry._save_state_unlocked()
        registry.task_cond.notify_all()

    return {
        "task_id": task_id,
        "status": "queued",
        "task_kind": task.task_kind,
        "novel_id": novel_id,
        "character_id": character_id,
    }


def enqueue_novel_cover_task(
    registry: TaskRegistry,
    *,
    novel_id: str,
    prompt: str,
    style: str,
    image_preset: str,
    aspect_ratio: str,
) -> Dict[str, Any]:
    task_id = str(uuid.uuid4())
    task = VisualTaskRuntime(
        task_id=task_id,
        task_kind="novel_cover",
        novel_id=novel_id,
        payload={
            "prompt": prompt,
            "style": style,
            "image_preset": image_preset,
            "aspect_ratio": aspect_ratio,
        },
        created_at=_now(),
        status="queued",
    )

    with registry.task_cond:
        registry.visual_tasks[task_id] = task
        registry.task_queue.append(QueueTask(task_id=task_id, task_type="visual"))
        registry._save_state_unlocked()
        registry.task_cond.notify_all()

    return {
        "task_id": task_id,
        "status": "queued",
        "task_kind": task.task_kind,
        "novel_id": novel_id,
    }


def _run_visual_task(task_id: str, registry: TaskRegistry) -> None:
    with registry.task_lock:
        task = registry.visual_tasks.get(task_id)
        if task is None:
            return
        if task.started_at is None:
            task.started_at = _now()

    try:
        sm = _new_storage_manager()
        if task.task_kind == "character_visual":
            payload = task.payload
            result = character_visuals.generate_character_visual(
                sm=sm,
                novel_id=task.novel_id,
                character_id=task.character_id,
                prompt=str(payload.get("prompt") or ""),
                slot_type=str(payload.get("slot_type") or "main"),
                index=payload.get("index"),
                style=str(payload.get("style") or ""),
                image_preset=str(payload.get("image_preset") or "720p"),
                aspect_ratio=str(payload.get("aspect_ratio") or "16:9"),
                regenerate_all=bool(payload.get("regenerate_all") or False),
            )
        elif task.task_kind == "novel_cover":
            payload = task.payload
            result = novel_cover.generate_novel_cover(
                sm=sm,
                novel_id=task.novel_id,
                prompt=str(payload.get("prompt") or ""),
                style=str(payload.get("style") or ""),
                image_preset=str(payload.get("image_preset") or "720p"),
                aspect_ratio=str(payload.get("aspect_ratio") or "16:9"),
            )
        else:
            raise RuntimeError(f"unsupported visual task kind: {task.task_kind}")

        with registry.task_lock:
            task.result = result if isinstance(result, dict) else {"result": result}
            task.return_code = 0
            task.status = "success"
            registry._save_state_unlocked()
    except Exception as exc:
        with registry.task_lock:
            task.error = str(exc)
            task.return_code = 1
            task.status = "failed"
            registry._save_state_unlocked()
    finally:
        with registry.task_lock:
            task.finished_at = _now()
            registry._save_state_unlocked()


def register_visual_runner(registry: TaskRegistry) -> None:
    def _runner(task_id: str) -> None:
        _run_visual_task(task_id, registry)

    registry.register_runner("visual", _runner)
