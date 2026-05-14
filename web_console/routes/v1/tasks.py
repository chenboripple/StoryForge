"""任务管理 (v1 API)"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from web_console.dependencies import get_app_config_dep, get_task_registry
from web_console.runtime.models import (
    IpTaskRuntime,
    QueueTask,
    TaskRuntime,
    _ip_task_to_dict,
    _task_to_dict,
)
from web_console.runtime.registry import TaskRegistry
from web_console.runtime.templates import _assert_command_allowed
from web_console.utils import _now, _resolve_project_dir

router = APIRouter(tags=["tasks"])


class StartTaskRequest(BaseModel):
    task_type: str = "pipeline"
    novel_id: Optional[str] = None
    character_ids: list[str] = []
    command: Optional[str] = None
    project_dir: Optional[str] = None
    force_regenerate: bool = False


class StopTaskRequest(BaseModel):
    task_id: str


def _validate_task_project_dir(project_dir: str) -> str:
    """任务执行目录约束：必须存在且不能是系统根目录。"""
    resolved = _resolve_project_dir(project_dir)
    if not os.path.isdir(resolved):
        raise HTTPException(status_code=400, detail="project_dir not exist")

    if Path(resolved).resolve() == Path("/"):
        raise HTTPException(status_code=400, detail="project_dir cannot be filesystem root")
    return resolved


def _refresh_and_get_task(registry: TaskRegistry, task_id: str) -> Optional[TaskRuntime]:
    """辅助函数：从 registry 中获取任务。"""
    with registry.task_lock:
        if task_id in registry.tasks:
            return registry.tasks[task_id]
        if task_id in registry.ip_tasks:
            return registry.ip_tasks[task_id]
        return None


@router.get("/tasks")
async def list_tasks(registry: TaskRegistry = Depends(get_task_registry)) -> dict:
    """列出所有任务。"""
    with registry.task_lock:
        return {
            "tasks": [_task_to_dict(t) for t in registry.tasks.values()],
            "ip_tasks": [_ip_task_to_dict(t) for t in registry.ip_tasks.values()],
        }


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    registry: TaskRegistry = Depends(get_task_registry),
) -> dict:
    """获取单个任务详情。"""
    task = _refresh_and_get_task(registry, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task not found")

    # 检查是否有日志文件，有就读一段追加返回
    log_content = ""
    try:
        if task.log_file and os.path.exists(task.log_file):
            with open(task.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                log_content = "".join(lines[-100:])
    except Exception:
        pass

    d = task.to_dict()
    d["log_tail"] = log_content
    return d


@router.post("/tasks")
async def start_task(
    req: StartTaskRequest,
    cfg=Depends(get_app_config_dep),
    registry: TaskRegistry = Depends(get_task_registry),
) -> dict:
    """启动新任务：可以是 pipeline（执行命令）或 ip（生成 IP）。"""
    if req.task_type not in ("pipeline", "ip"):
        raise HTTPException(status_code=400, detail="unsupported task_type")

    task_id = str(uuid.uuid4())

    if req.task_type == "pipeline":
        if not req.command:
            raise HTTPException(status_code=400, detail="command required")

        project_dir = _validate_task_project_dir(req.project_dir)
        _assert_command_allowed(project_dir, req.command)

        task = TaskRuntime(
            task_id=task_id,
            project_dir=project_dir,
            command=req.command,
            created_at=_now(),
            status="queued",
        )
        with registry.task_cond:
            registry.tasks[task_id] = task
            registry.task_queue.append(QueueTask(task_id=task_id, task_type="pipeline"))
            registry._save_state_unlocked()
            registry.task_cond.notify_all()
        return {"task_id": task_id, "task": _task_to_dict(task)}

    if req.task_type == "ip":
        if not req.novel_id:
            raise HTTPException(status_code=400, detail="novel_id required")

        project_dir = _validate_task_project_dir(req.project_dir)

        task = IpTaskRuntime(
            task_id=task_id,
            project_dir=project_dir,
            novel_id=req.novel_id,
            character_ids=req.character_ids,
            force_regenerate=req.force_regenerate,
            created_at=_now(),
            status="queued",
        )
        with registry.task_cond:
            registry.ip_tasks[task_id] = task
            registry.task_queue.append(QueueTask(task_id=task_id, task_type="ip"))
            registry._save_state_unlocked()
            registry.task_cond.notify_all()
        return {"task_id": task_id, "task": _ip_task_to_dict(task)}

    return {"task_id": task_id}


@router.post("/tasks/{task_id}/stop")
async def stop_task(
    task_id: str,
    registry: TaskRegistry = Depends(get_task_registry),
) -> dict:
    """停止任务。"""
    with registry.task_cond:
        # 先从队列移除，防止被调度
        registry._remove_queued_task_unlocked(task_id)
        # 如果是 pipeline 并且在运行，标记为 stopped 并尝试终止进程
        if task_id in registry.tasks:
            task = registry.tasks[task_id]
            if task.status == "running":
                task.status = "stopped"
                if task.process and task.process.poll() is None:
                    try:
                        task.process.terminate()
                        # 给一点时间，不行就 kill
                        try:
                            task.process.wait(timeout=3)
                        except Exception:
                            task.process.kill()
                    except Exception:
                        pass
            else:
                task.status = "cancelled"
            registry._save_state_unlocked()
            registry.task_cond.notify_all()
            return {"ok": True, "task": _task_to_dict(task)}

        if task_id in registry.ip_tasks:
            task = registry.ip_tasks[task_id]
            if task.status in ("queued", "running"):
                task.status = "cancelled"
            registry._save_state_unlocked()
            registry.task_cond.notify_all()
            return {"ok": True, "task": _ip_task_to_dict(task)}

    raise HTTPException(status_code=404, detail="task not found")


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    registry: TaskRegistry = Depends(get_task_registry),
) -> dict:
    """删除任务。"""
    with registry.task_cond:
        registry._remove_queued_task_unlocked(task_id)
        if task_id in registry.tasks:
            task = registry.tasks.pop(task_id)
            # 如果有日志文件也删除
            if task.log_file and os.path.exists(task.log_file):
                try:
                    os.unlink(task.log_file)
                except Exception:
                    pass
            registry._save_state_unlocked()
            return {"ok": True}
        if task_id in registry.ip_tasks:
            registry.ip_tasks.pop(task_id)
            registry._save_state_unlocked()
            return {"ok": True}

    raise HTTPException(status_code=404, detail="task not found")
