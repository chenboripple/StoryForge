"""任务队列、调度循环、状态持久化、子进程 runner。

【兼容层】此模块现在是对 TaskRegistry 的兼容包装，
保持向后兼容。新代码应直接使用 TaskRegistry。

模块级全局（TASKS / IP_TASKS / TASK_QUEUE / TASK_LOCK / TASK_COND
/ RUNNING_TASK_IDS / CANCELLED_TASK_IDS / DISPATCHER_STARTED）集中在这里。
其他模块都通过 `from web_console.runtime.queue import TASKS` 等引用。

业务执行体不在本文件直接 import，改用 `register_runner(task_type, callable)`
注册表派发，以避免 runtime/queue.py ↔ services/ip.py 的循环依赖。
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Deque, Dict, Optional

from core.config import get_config
from web_console.runtime.models import (
    IpTaskRuntime,
    QueueTask,
    TaskRuntime,
    _ip_task_to_dict,
    _task_to_dict,
)
from web_console.runtime.registry import TaskRegistry
from web_console.utils import _now, _resolve_debug_output_dir

# -----------------------------------------------------------------------------
# 兼容层：保持旧接口不变，内部代理到默认的 TaskRegistry 实例
# -----------------------------------------------------------------------------

# 创建默认的注册表实例（用于向后兼容）
_cfg = get_config()
_default_registry = TaskRegistry(Path(_cfg.data_dir_abs))

# 兼容性别名：代理到 _default_registry
TASKS = _default_registry.tasks
IP_TASKS = _default_registry.ip_tasks
TASK_QUEUE = _default_registry.task_queue
TASK_LOCK = _default_registry.task_lock
TASK_COND = _default_registry.task_cond
RUNNING_TASK_IDS = _default_registry.running_task_ids
CANCELLED_TASK_IDS = _default_registry.cancelled_task_ids
DISPATCHER_STARTED = _default_registry.dispatcher_started
TASK_RUNNERS = _default_registry.task_runners
MAX_RUNNING_TASKS = _default_registry.max_running_tasks


def register_runner(task_type: str, runner: Callable[[str], None]) -> None:
    """注册某类型任务的实际执行函数。"""
    _default_registry.register_runner(task_type, runner)


def _running_tasks_count() -> int:
    """获取当前运行的任务数量。"""
    return _default_registry.running_tasks_count()


def _queue_size() -> int:
    """获取队列大小。"""
    return _default_registry.queue_size()


def _remove_queued_task_unlocked(task_id: str) -> bool:
    """从队列移除任务（调用方必须持有锁）。"""
    return _default_registry._remove_queued_task_unlocked(task_id)


def _save_runtime_state_unlocked() -> None:
    """持久化任务与队列状态（调用方必须持有锁）。"""
    _default_registry._save_state_unlocked()


def _load_runtime_state() -> None:
    """从磁盘恢复任务和队列状态。"""
    _default_registry.load_state()


def _enqueue_task(task: QueueTask) -> int:
    """将任务加入队列，返回队列位置。"""
    return _default_registry.enqueue_task(task)


def _mark_task_running(task: QueueTask) -> None:
    """标记任务为运行中。"""
    _default_registry.mark_task_running(task)


def _finalize_task(task_id: str) -> None:
    """任务完成后的清理工作。"""
    _default_registry.finalize_task(task_id)


def _start_dispatcher() -> None:
    """启动调度循环（向后兼容）。"""
    _default_registry.start_dispatcher()


def _run_task(task_id: str) -> None:
    """pipeline 类型任务的执行函数（向后兼容）。"""
    _default_registry._run_task(task_id)


# 启动时的初始化（向后兼容）
# 在 lifespan 中初始化，所以这里不再重复初始化
# _load_runtime_state()
# _start_dispatcher()

# 注册默认的 pipeline runner（仍然需要，因为 services.ip 可能在导入时使用）
register_runner("pipeline", _run_task)
