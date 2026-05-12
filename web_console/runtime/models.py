"""任务运行期数据模型（dataclass + 序列化）。

注意：这里的 TaskRuntime / IpTaskRuntime 是控制台运行期内存对象，
不要与 core/models 的领域模型混在一起。
"""

from __future__ import annotations

import subprocess
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional


@dataclass
class TaskRuntime:
    task_id: str
    project_dir: str
    command: str
    created_at: str
    status: str = "queued"
    pid: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    return_code: Optional[int] = None
    logs: Deque[str] = field(default_factory=lambda: deque(maxlen=5000))
    log_file: Optional[str] = None
    process: Optional[subprocess.Popen] = None


@dataclass
class IpTaskRuntime:
    task_id: str
    project_dir: str
    novel_id: str
    character_ids: List[str]
    force_regenerate: bool
    created_at: str
    status: str = "queued"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    return_code: Optional[int] = None
    error: Optional[str] = None
    result: Dict[str, object] = field(default_factory=dict)


@dataclass
class QueueTask:
    task_id: str
    task_type: str  # "pipeline" | "ip"


def _task_to_dict(task: TaskRuntime) -> dict:
    return {
        "task_id": task.task_id,
        "project_dir": task.project_dir,
        "command": task.command,
        "status": task.status,
        "pid": task.pid,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "return_code": task.return_code,
        "log_file": task.log_file,
    }


def _ip_task_to_dict(task: IpTaskRuntime) -> dict:
    return {
        "task_id": task.task_id,
        "project_dir": task.project_dir,
        "novel_id": task.novel_id,
        "character_ids": task.character_ids,
        "force_regenerate": task.force_regenerate,
        "status": task.status,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "finished_at": task.finished_at,
        "return_code": task.return_code,
        "error": task.error,
        "result": task.result,
    }
