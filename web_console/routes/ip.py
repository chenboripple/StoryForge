"""IP 生成异步任务端点。"""

from __future__ import annotations

import os
import uuid
from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from web_console.runtime.models import IpTaskRuntime, QueueTask, _ip_task_to_dict
from web_console.runtime.queue import (
    IP_TASKS,
    TASK_LOCK,
    _enqueue_task,
    _save_runtime_state_unlocked,
)
from web_console.utils import _now, _resolve_project_dir

# 导入 services.ip 以触发 register_runner("ip", _run_ip_task) 注册。
import web_console.services.ip  # noqa: F401

router = APIRouter()


class GenerateIpRequest(BaseModel):
    project_dir: str
    novel_id: str
    character_ids: List[str] = Field(default_factory=list)
    force_regenerate: bool = False


@router.post("/api/ip/generate")
async def generate_ip(req: GenerateIpRequest) -> dict:
    project_dir = _resolve_project_dir(req.project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")

    character_ids = [c.strip() for c in req.character_ids if c and c.strip()]
    if not character_ids:
        raise HTTPException(status_code=400, detail="character_ids 不能为空")

    task_id = uuid.uuid4().hex[:12]
    task = IpTaskRuntime(
        task_id=task_id,
        project_dir=project_dir,
        novel_id=req.novel_id.strip(),
        character_ids=character_ids,
        force_regenerate=req.force_regenerate,
        created_at=_now(),
    )

    with TASK_LOCK:
        IP_TASKS[task_id] = task
        _save_runtime_state_unlocked()
    queue_position = _enqueue_task(QueueTask(task_id=task_id, task_type="ip"))

    return {"ok": True, "task": _ip_task_to_dict(task), "queue_position": queue_position}


@router.get("/api/ip/tasks")
async def list_ip_tasks() -> dict:
    with TASK_LOCK:
        tasks = sorted(IP_TASKS.values(), key=lambda x: x.created_at, reverse=True)
        return {"tasks": [_ip_task_to_dict(t) for t in tasks]}


@router.get("/api/ip/tasks/{task_id}")
async def get_ip_task(task_id: str) -> dict:
    with TASK_LOCK:
        task = IP_TASKS.get(task_id)
        task_payload = _ip_task_to_dict(task) if task else None
    if not task_payload:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"task": task_payload}
