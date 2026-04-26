#!/usr/bin/env python3
"""StoryForge 操作页面（MVP）"""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel


@dataclass
class TaskRuntime:
    task_id: str
    project_dir: str
    command: str
    created_at: str
    status: str = "running"
    pid: Optional[int] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    return_code: Optional[int] = None
    logs: Deque[str] = field(default_factory=lambda: deque(maxlen=5000))
    log_file: Optional[str] = None
    process: Optional[subprocess.Popen] = None


class StartTaskRequest(BaseModel):
    project_dir: str
    command: Optional[str] = None


class SaveTemplateRequest(BaseModel):
    name: str
    project_dir: str
    command: str


app = FastAPI(title="StoryForge Console", version="0.1.1")
TASKS: Dict[str, TaskRuntime] = {}
TASK_LOCK = threading.Lock()
MAX_RUNNING_TASKS = int(os.getenv("STORYFORGE_MAX_RUNNING_TASKS", "2"))
TEMPLATE_FILE = Path(__file__).resolve().parent / "templates.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


def _tail_logs(logs: Deque[str], offset: int) -> List[str]:
    data = list(logs)
    if offset < 0:
        offset = 0
    return data[offset:]


def _running_tasks_count() -> int:
    with TASK_LOCK:
        return sum(1 for t in TASKS.values() if t.status == "running")


def _load_templates() -> List[dict]:
    if not TEMPLATE_FILE.exists():
        return []
    try:
        data = json.loads(TEMPLATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_templates(templates: List[dict]) -> None:
    TEMPLATE_FILE.write_text(
        json.dumps(templates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _run_task(task_id: str) -> None:
    with TASK_LOCK:
        task = TASKS[task_id]

    log_dir = Path(task.project_dir) / "debug_output" / "console_runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{task.task_id}.log"

    task.started_at = _now()
    task.log_file = str(log_file)

    process = subprocess.Popen(
        shlex.split(task.command),
        cwd=task.project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    task.process = process
    task.pid = process.pid

    with open(log_file, "w", encoding="utf-8") as fout:
        if process.stdout:
            for line in process.stdout:
                task.logs.append(line)
                fout.write(line)
                fout.flush()

    rc = process.wait()
    task.return_code = rc
    task.finished_at = _now()
    if task.status != "stopped":
        task.status = "success" if rc == 0 else "failed"


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>StoryForge 控制台</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 24px; }
    input { width: 520px; padding: 8px; margin: 4px 0; }
    button { padding: 8px 12px; margin-right: 8px; }
    #tasks { margin-top: 16px; }
    .task { border: 1px solid #ddd; padding: 10px; margin-bottom: 8px; border-radius: 8px; }
    pre { background: #111; color: #ddd; padding: 12px; border-radius: 8px; max-height: 420px; overflow: auto; }
    .row { margin-bottom: 8px; }
  </style>
</head>
<body>
  <h2>StoryForge 操作页面（MVP）</h2>
  <p>支持按小说保存模板、并发上限控制、日志下载。</p>
  <p>运行中上限：<strong id="max_running">-</strong></p>

  <div class="row">
    <label>任务参数模板</label><br />
    <select id="template_select" onchange="applyTemplate()"></select>
    <button onclick="saveTemplate()">保存模板</button>
    <button onclick="loadTemplates()">刷新模板</button>
  </div>

  <div class="row">
    <label>项目目录</label><br />
    <input id="project_dir" value="/Users/ripple/work space/StoryForge" />
  </div>
  <div class="row">
    <label>启动命令</label><br />
    <input id="command" value="python3 examples/debug_pipeline.py" />
  </div>
  <div style="margin-top:8px;">
    <button onclick="startTask()">启动任务</button>
    <button onclick="loadTasks()">刷新任务列表</button>
  </div>

  <div id="tasks"></div>

  <h3>日志</h3>
  <select id="task_select" onchange="offset=0;document.getElementById('logs').textContent='';pollLogs()"></select>
  <button onclick="stopTask()">停止选中任务</button>
  <button onclick="downloadLog()">下载日志</button>
  <pre id="logs"></pre>

<script>
let offset = 0;

async function loadConfig() {
  const res = await fetch('/api/config');
  if (!res.ok) return;
  const data = await res.json();
  document.getElementById('max_running').innerText = data.max_running_tasks;
}

async function loadTemplates() {
  const res = await fetch('/api/templates');
  if (!res.ok) return;
  const data = await res.json();
  const sel = document.getElementById('template_select');
  sel.innerHTML = '<option value="">(选择模板)</option>';
  for (const t of data.templates) {
    const opt = document.createElement('option');
    opt.value = t.name;
    opt.text = `${t.name} | ${t.project_dir}`;
    opt.dataset.project = t.project_dir;
    opt.dataset.command = t.command;
    sel.appendChild(opt);
  }
}

function applyTemplate() {
  const sel = document.getElementById('template_select');
  const opt = sel.options[sel.selectedIndex];
  if (!opt || !opt.dataset.project) return;
  document.getElementById('project_dir').value = opt.dataset.project;
  document.getElementById('command').value = opt.dataset.command;
}

async function saveTemplate() {
  const name = prompt('模板名称（建议小说名）');
  if (!name) return;
  const project_dir = document.getElementById('project_dir').value;
  const command = document.getElementById('command').value;
  const res = await fetch('/api/templates', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name, project_dir, command})
  });
  if (!res.ok) {
    alert(await res.text());
    return;
  }
  await loadTemplates();
}

async function startTask() {
  const project_dir = document.getElementById('project_dir').value;
  const command = document.getElementById('command').value;
  const res = await fetch('/api/tasks/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project_dir, command})
  });
  if (!res.ok) {
    alert(await res.text());
    return;
  }
  offset = 0;
  document.getElementById('logs').textContent = '';
  await loadTasks();
}

async function loadTasks() {
  const res = await fetch('/api/tasks');
  if (!res.ok) return;
  const data = await res.json();
  const wrap = document.getElementById('tasks');
  const sel = document.getElementById('task_select');
  const current = sel.value;
  wrap.innerHTML = '';
  sel.innerHTML = '';
  for (const t of data.tasks) {
    const d = document.createElement('div');
    d.className = 'task';
    d.innerText = `${t.task_id} | ${t.status} | ${t.command} | ${t.project_dir}`;
    wrap.appendChild(d);

    const opt = document.createElement('option');
    opt.value = t.task_id;
    opt.text = `${t.task_id} (${t.status})`;
    sel.appendChild(opt);
  }
  if (current) sel.value = current;
}

async function pollLogs() {
  const taskId = document.getElementById('task_select').value;
  if (!taskId) return;
  const res = await fetch(`/api/tasks/${taskId}/logs?offset=${offset}`);
  if (!res.ok) return;
  const data = await res.json();
  offset = data.next_offset;
  const logBox = document.getElementById('logs');
  logBox.textContent += data.lines.join('');
  logBox.scrollTop = logBox.scrollHeight;
}

async function stopTask() {
  const taskId = document.getElementById('task_select').value;
  if (!taskId) return;
  await fetch(`/api/tasks/${taskId}/stop`, {method: 'POST'});
  await loadTasks();
}

function downloadLog() {
  const taskId = document.getElementById('task_select').value;
  if (!taskId) return;
  window.open(`/api/tasks/${taskId}/log-file`, '_blank');
}

setInterval(async () => {
  await loadTasks();
  await pollLogs();
}, 3000);

loadConfig();
loadTemplates();
loadTasks();
</script>
</body>
</html>
"""


@app.get("/api/config")
async def get_config() -> dict:
    return {"max_running_tasks": MAX_RUNNING_TASKS}


@app.get("/api/templates")
async def list_templates() -> dict:
    return {"templates": _load_templates()}


@app.post("/api/templates")
async def save_template(req: SaveTemplateRequest) -> dict:
    item = {
        "name": req.name.strip(),
        "project_dir": os.path.abspath(req.project_dir.strip()),
        "command": req.command.strip(),
    }
    if not item["name"] or not item["project_dir"] or not item["command"]:
        raise HTTPException(status_code=400, detail="模板字段不能为空")

    templates = _load_templates()
    replaced = False
    for i, t in enumerate(templates):
        if t.get("name") == item["name"]:
            templates[i] = item
            replaced = True
            break
    if not replaced:
        templates.append(item)

    _save_templates(templates)
    return {"ok": True, "template": item}


@app.post("/api/tasks/start")
async def start_task(req: StartTaskRequest) -> dict:
    project_dir = os.path.abspath(req.project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")

    command = req.command or "python3 examples/debug_pipeline.py"

    if _running_tasks_count() >= MAX_RUNNING_TASKS:
        raise HTTPException(
            status_code=429,
            detail=f"运行中任务已达上限（{MAX_RUNNING_TASKS}），请先停止或等待已有任务结束",
        )

    task_id = uuid.uuid4().hex[:12]
    task = TaskRuntime(
        task_id=task_id,
        project_dir=project_dir,
        command=command,
        created_at=_now(),
    )

    with TASK_LOCK:
        TASKS[task_id] = task

    threading.Thread(target=_run_task, args=(task_id,), daemon=True).start()
    return {"ok": True, "task": _task_to_dict(task)}


@app.get("/api/tasks")
async def list_tasks() -> dict:
    with TASK_LOCK:
        tasks = sorted(TASKS.values(), key=lambda x: x.created_at, reverse=True)
        return {"tasks": [_task_to_dict(t) for t in tasks]}


@app.get("/api/tasks/{task_id}/logs")
async def get_logs(task_id: str, offset: int = 0) -> dict:
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


@app.get("/api/tasks/{task_id}/log-file")
async def get_log_file(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.log_file or not os.path.exists(task.log_file):
        raise HTTPException(status_code=404, detail="日志文件不存在")
    return FileResponse(task.log_file, filename=f"{task_id}.log", media_type="text/plain")


@app.post("/api/tasks/{task_id}/stop")
async def stop_task(task_id: str) -> dict:
    task = TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    proc = task.process
    if proc and proc.poll() is None:
        proc.terminate()
        await asyncio.sleep(0.2)
        if proc.poll() is None:
            proc.kill()
        task.status = "stopped"
        task.finished_at = _now()
    return {"ok": True, "task": _task_to_dict(task)}


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "tasks": len(TASKS)}
