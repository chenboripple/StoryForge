"""FastAPI 依赖注入提供器。

每个 HTTP 请求获取独立 StorageManager，避免跨请求共享内存缓存。
"""

from __future__ import annotations

from fastapi import Depends, Request

from core.config import get_config
from core.storage import StorageConfig, StorageManager
from web_console.runtime.registry import TaskRegistry


def _new_storage_manager(cfg=None) -> StorageManager:
    runtime_cfg = cfg or get_config()
    return StorageManager(StorageConfig(data_dir=runtime_cfg.data_dir_abs))


def get_app_config_dep():
    return get_config()


def get_storage_manager_dep(cfg=Depends(get_app_config_dep)) -> StorageManager:
    return _new_storage_manager(cfg)


def get_task_registry(request: Request) -> TaskRegistry:
    """从应用状态获取 TaskRegistry。"""
    return request.app.state.task_registry
