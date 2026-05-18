"""健康检查 / 控制台基础信息 (v1 API)"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from web_console.dependencies import get_app_config_dep, get_task_registry
from web_console.runtime.registry import TaskRegistry

router = APIRouter(tags=["health"])


@router.get("/config")
async def get_console_config(registry: TaskRegistry = Depends(get_task_registry)) -> dict:
    cfg = get_app_config_dep()
    with registry.task_lock:
        running_tasks = len(registry.running_task_ids)
        queued_tasks = len(registry.task_queue)
    return {
        "max_running_tasks": registry.max_running_tasks,
        "configured_max_running_tasks": cfg.console.max_running_tasks,
        "running_tasks": running_tasks,
        "queued_tasks": queued_tasks,
    }


@router.get("/health")
async def api_health(
    cfg=Depends(get_app_config_dep),
    registry: TaskRegistry = Depends(get_task_registry),
) -> dict:
    with registry.task_lock:
        running_tasks = len(registry.running_task_ids)
        queued_tasks = len(registry.task_queue)
    return {
        "status": "ok",
        "config_path": cfg.config_path,
        "data_dir": cfg.data_dir_abs,
        "running_tasks": running_tasks,
        "queued_tasks": queued_tasks,
    }
