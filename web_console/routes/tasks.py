"""Pipeline 任务端点（启动/列表/日志/停止）。"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from web_console.runtime.models import QueueTask, TaskRuntime, _task_to_dict
from web_console.runtime.queue import (
    CANCELLED_TASK_IDS,
    TASK_COND,
    TASK_LOCK,
    TASKS,
    _enqueue_task,
    _remove_queued_task_unlocked,
    _save_runtime_state_unlocked,
)
from web_console.runtime.templates import DEFAULT_COMMAND, _assert_command_allowed
from web_console.utils import _now, _resolve_project_dir, _tail_logs

router = APIRouter()


class StartTaskRequest(BaseModel):
    project_dir: str
    command: Optional[str] = None


@router.post("/api/tasks/start")
async def start_task(req: StartTaskRequest) -> dict:
    project_dir = _resolve_project_dir(req.project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")

    command = (req.command or DEFAULT_COMMAND).strip()
    _assert_command_allowed(project_dir, command)

    task_id = uuid.uuid4().hex[:12]
    task = TaskRuntime(
        task_id=task_id,
        project_dir=project_dir,
        command=command,
        created_at=_now(),
    )

    with TASK_LOCK:
        TASKS[task_id] = task
        _save_runtime_state_unlocked()
    queue_position = _enqueue_task(QueueTask(task_id=task_id, task_type="pipeline"))

    return {"ok": True, "task": _task_to_dict(task), "queue_position": queue_position}


@router.get("/api/tasks")
async def list_tasks() -> dict:
    with TASK_LOCK:
        tasks = sorted(TASKS.values(), key=lambda x: x.created_at, reverse=True)
        return {"tasks": [_task_to_dict(t) for t in tasks]}


@router.get("/api/tasks/{task_id}/logs")
async def get_logs(task_id: str, offset: int = 0) -> dict:
    with TASK_LOCK:
        task = TASKS.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        lines = _tail_logs(task.logs, offset)
    return {
        "task_id": task_id,
        "offset": offset,
        "next_offset": offset + len(lines),
        "lines": lines,
    }


@router.get("/api/tasks/{task_id}/log-file")
async def get_log_file(task_id: str):
    with TASK_LOCK:
        task = TASKS.get(task_id)
        log_file = task.log_file if task else None
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not log_file or not os.path.exists(log_file):
        raise HTTPException(status_code=404, detail="日志文件不存在")
    return FileResponse(log_file, filename=f"{task_id}.log", media_type="text/plain")


@router.post("/api/tasks/{task_id}/stop")
async def stop_task(task_id: str) -> dict:
    with TASK_LOCK:
        task = TASKS.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        removed = _remove_queued_task_unlocked(task_id)
        if removed:
            CANCELLED_TASK_IDS.add(task_id)
            task.status = "stopped"
            task.finished_at = _now()
            _save_runtime_state_unlocked()
            TASK_COND.notify_all()
            return {"ok": True, "task": _task_to_dict(task)}

        if task.status == "queued":
            # queued 但不在队列中（可能已被调度线程取走），仍视为停止。
            CANCELLED_TASK_IDS.add(task_id)
            task.status = "stopped"
            task.finished_at = _now()
            _save_runtime_state_unlocked()
            TASK_COND.notify_all()
            return {"ok": True, "task": _task_to_dict(task)}

        proc = task.process

    if proc and proc.poll() is None:
        proc.terminate()
        await asyncio.sleep(0.2)
        if proc.poll() is None:
            proc.kill()
        with TASK_LOCK:
            task.status = "stopped"
            task.finished_at = _now()
            _save_runtime_state_unlocked()

    with TASK_LOCK:
        payload = _task_to_dict(task)
    return {"ok": True, "task": payload}
