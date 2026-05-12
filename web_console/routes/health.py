"""健康检查 / 控制台基础信息。"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from web_console.dependencies import get_app_config_dep
from web_console.runtime.queue import (
    IP_TASKS,
    MAX_RUNNING_TASKS,
    RUNNING_TASK_IDS,
    TASKS,
    TASK_LOCK,
    TASK_QUEUE,
    _queue_size,
    _running_tasks_count,
)

router = APIRouter()


@router.get("/api/config")
async def get_console_config() -> dict:
    cfg = get_app_config_dep()
    return {
        "max_running_tasks": MAX_RUNNING_TASKS,
        "configured_max_running_tasks": cfg.console.max_running_tasks,
        "running_tasks": _running_tasks_count(),
        "queued_tasks": _queue_size(),
    }


@router.get("/api/health")
async def api_health(cfg=Depends(get_app_config_dep)) -> dict:
    return {
        "status": "ok",
        "config_path": cfg.config_path,
        "data_dir": cfg.data_dir_abs,
    }


@router.get("/health")
async def health() -> dict:
    with TASK_LOCK:
        return {
            "ok": True,
            "tasks": len(TASKS),
            "ip_tasks": len(IP_TASKS),
            "running_tasks": len(RUNNING_TASK_IDS),
            "queued_tasks": len(TASK_QUEUE),
        }
