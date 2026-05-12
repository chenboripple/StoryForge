"""任务注册表 - 封装所有任务运行时状态，避免模块级全局变量。

这是对之前 queue.py 中模块级全局变量的重构，使其可注入、可测试。
"""

from __future__ import annotations

import json
import shlex
import subprocess
import threading
from collections import deque
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
from web_console.utils import _now, _resolve_debug_output_dir


class TaskRegistry:
    """任务注册表 - 管理所有任务运行时状态。"""

    def __init__(self, storage_dir: Path | str):
        self.storage_dir = Path(storage_dir)
        self.runtime_state_file = self.storage_dir / "console" / "runtime_state.json"

        # 运行时状态
        self.tasks: Dict[str, TaskRuntime] = {}
        self.ip_tasks: Dict[str, IpTaskRuntime] = {}
        self.task_queue: Deque[QueueTask] = deque()
        self.task_lock = threading.Lock()
        self.task_cond = threading.Condition(self.task_lock)
        self.running_task_ids: set[str] = set()
        self.cancelled_task_ids: set[str] = set()
        self.dispatcher_started = False
        self.task_runners: Dict[str, Callable[[str], None]] = {}

        # 加载配置
        cfg = get_config()
        self.max_running_tasks = max(1, int(cfg.console.max_running_tasks))

    def register_runner(self, task_type: str, runner: Callable[[str], None]) -> None:
        """注册某类型任务的实际执行函数。"""
        self.task_runners[task_type] = runner

    def running_tasks_count(self) -> int:
        """获取当前运行的任务数量。"""
        with self.task_lock:
            return len(self.running_task_ids)

    def queue_size(self) -> int:
        """获取队列大小。"""
        with self.task_lock:
            return len(self.task_queue)

    def load_state(self) -> None:
        """从磁盘恢复任务和队列状态。"""
        if not self.runtime_state_file.exists():
            return

        try:
            payload = json.loads(self.runtime_state_file.read_text(encoding="utf-8"))
        except Exception:
            return

        if not isinstance(payload, dict):
            return

        restored_tasks: Dict[str, TaskRuntime] = {}
        for raw in payload.get("tasks", []):
            if not isinstance(raw, dict):
                continue
            task_id = str(raw.get("task_id") or "").strip()
            if not task_id:
                continue
            status = str(raw.get("status") or "queued")
            # 进程重启后 running 无法恢复，标记为 failed
            if status == "running":
                status = "failed"
            restored_tasks[task_id] = TaskRuntime(
                task_id=task_id,
                project_dir=str(raw.get("project_dir") or ""),
                command=str(raw.get("command") or ""),
                created_at=str(raw.get("created_at") or _now()),
                status=status,
                pid=raw.get("pid"),
                started_at=raw.get("started_at"),
                finished_at=raw.get("finished_at") or (_now() if status == "failed" else None),
                return_code=raw.get("return_code") if status != "failed" else (raw.get("return_code") or -1),
                log_file=raw.get("log_file"),
            )

        restored_ip_tasks: Dict[str, IpTaskRuntime] = {}
        for raw in payload.get("ip_tasks", []):
            if not isinstance(raw, dict):
                continue
            task_id = str(raw.get("task_id") or "").strip()
            if not task_id:
                continue
            status = str(raw.get("status") or "queued")
            error = raw.get("error")
            if status == "running":
                status = "failed"
                error = error or "任务在服务重启时中断"
            restored_ip_tasks[task_id] = IpTaskRuntime(
                task_id=task_id,
                project_dir=str(raw.get("project_dir") or ""),
                novel_id=str(raw.get("novel_id") or ""),
                character_ids=[str(x) for x in raw.get("character_ids", []) if str(x).strip()],
                force_regenerate=bool(raw.get("force_regenerate", False)),
                created_at=str(raw.get("created_at") or _now()),
                status=status,
                started_at=raw.get("started_at"),
                finished_at=raw.get("finished_at") or (_now() if status == "failed" else None),
                return_code=raw.get("return_code") if status != "failed" else (raw.get("return_code") or -1),
                error=error,
                result=raw.get("result") if isinstance(raw.get("result"), dict) else {},
            )

        restored_queue: Deque[QueueTask] = deque()
        for item in payload.get("queue", []):
            if not isinstance(item, dict):
                continue
            task_id = str(item.get("task_id") or "").strip()
            task_type = str(item.get("task_type") or "").strip()
            if not task_id or task_type not in {"pipeline", "ip"}:
                continue
            if task_type == "pipeline" and task_id not in restored_tasks:
                continue
            if task_type == "ip" and task_id not in restored_ip_tasks:
                continue
            restored_queue.append(QueueTask(task_id=task_id, task_type=task_type))

        with self.task_lock:
            self.tasks.clear()
            self.tasks.update(restored_tasks)
            self.ip_tasks.clear()
            self.ip_tasks.update(restored_ip_tasks)
            self.task_queue.clear()
            self.task_queue.extend(restored_queue)
            self.running_task_ids.clear()
            self.cancelled_task_ids.clear()

    def save_state(self) -> None:
        """持久化任务与队列状态。"""
        with self.task_lock:
            self._save_state_unlocked()

    def _save_state_unlocked(self) -> None:
        """持久化任务与队列状态（调用方必须持有锁）。"""
        payload = {
            "version": 1,
            "updated_at": _now(),
            "tasks": [_task_to_dict(task) for task in self.tasks.values()],
            "ip_tasks": [_ip_task_to_dict(task) for task in self.ip_tasks.values()],
            "queue": [{"task_id": item.task_id, "task_type": item.task_type} for item in self.task_queue],
        }
        self.runtime_state_file.parent.mkdir(parents=True, exist_ok=True)
        self.runtime_state_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def enqueue_task(self, task: QueueTask) -> int:
        """将任务加入队列，返回队列位置。"""
        with self.task_cond:
            self.task_queue.append(task)
            queue_position = len(self.task_queue)
            self._save_state_unlocked()
            self.task_cond.notify_all()
            return queue_position

    def remove_queued_task(self, task_id: str) -> bool:
        """从队列移除任务，返回是否找到并移除。"""
        with self.task_lock:
            return self._remove_queued_task_unlocked(task_id)

    def _remove_queued_task_unlocked(self, task_id: str) -> bool:
        """从队列移除任务（调用方必须持有锁）。"""
        for queued in list(self.task_queue):
            if queued.task_id == task_id:
                self.task_queue.remove(queued)
                return True
        return False

    def mark_task_running(self, task: QueueTask) -> None:
        """标记任务为运行中。"""
        if task.task_type == "pipeline":
            runtime = self.tasks.get(task.task_id)
        else:
            runtime = self.ip_tasks.get(task.task_id)
        if runtime:
            runtime.status = "running"
            if runtime.started_at is None:
                runtime.started_at = _now()

    def finalize_task(self, task_id: str) -> None:
        """任务完成后的清理工作。"""
        with self.task_cond:
            self.running_task_ids.discard(task_id)
            self._save_state_unlocked()

    def _dispatcher_loop(self) -> None:
        """调度循环（内部方法）。"""
        while True:
            task_to_run: Optional[QueueTask] = None
            with self.task_cond:
                while not self.task_queue or len(self.running_task_ids) >= self.max_running_tasks:
                    self.task_cond.wait()

                while self.task_queue and task_to_run is None:
                    task = self.task_queue.popleft()

                    # 被取消的任务不再调度，直接丢弃并清理标记
                    if task.task_id in self.cancelled_task_ids:
                        self.cancelled_task_ids.discard(task.task_id)
                        self._save_state_unlocked()
                        continue

                    # 任务对象可能已经被删除，跳过无效任务
                    runtime_exists = task.task_id in self.tasks if task.task_type == "pipeline" else task.task_id in self.ip_tasks
                    if not runtime_exists:
                        continue

                    task_to_run = task

                if task_to_run is None:
                    continue

                self.running_task_ids.add(task_to_run.task_id)
                self.mark_task_running(task_to_run)
                self._save_state_unlocked()

            threading.Thread(target=self._execute_queue_task, args=(task_to_run,), daemon=True).start()

    def _execute_queue_task(self, task: QueueTask) -> None:
        """执行队列中的任务（内部方法）。"""
        try:
            runner = self.task_runners.get(task.task_type)
            if runner is not None:
                runner(task.task_id)
        finally:
            self.finalize_task(task.task_id)

    def start_dispatcher(self) -> None:
        """启动调度循环。"""
        with self.task_lock:
            if self.dispatcher_started:
                return
            self.dispatcher_started = True
        threading.Thread(target=self._dispatcher_loop, daemon=True).start()

    def shutdown(self) -> None:
        """关闭调度器（用于应用退出时的清理）。"""
        # 尝试停止所有运行中的任务
        with self.task_lock:
            for task_id in list(self.running_task_ids):
                task = self.tasks.get(task_id) or self.ip_tasks.get(task_id)
                if task and hasattr(task, "process") and task.process and task.process.poll() is None:
                    try:
                        task.process.terminate()
                    except Exception:
                        pass

    def _run_task(self, task_id: str) -> None:
        """pipeline 类型任务的执行函数：fork subprocess 运行命令并采集日志。"""
        with self.task_lock:
            task = self.tasks[task_id]
            if task.started_at is None:
                task.started_at = _now()

        log_dir = _resolve_debug_output_dir() / "console_runs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{task.task_id}.log"

        with self.task_lock:
            task.log_file = str(log_file)

        process = subprocess.Popen(
            shlex.split(task.command),
            cwd=task.project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        with self.task_lock:
            task.process = process
            task.pid = process.pid
            self._save_state_unlocked()

        with open(log_file, "w", encoding="utf-8") as fout:
            if process.stdout:
                for line in process.stdout:
                    with self.task_lock:
                        task.logs.append(line)
                    fout.write(line)
                    fout.flush()

        rc = process.wait()
        with self.task_lock:
            task.return_code = rc
            task.finished_at = _now()
            if task.status != "stopped":
                task.status = "success" if rc == 0 else "failed"
            self._save_state_unlocked()
