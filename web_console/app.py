"""StoryForge 操作页面（MVP）"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shlex
import subprocess
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Deque, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from core.settings import get_settings


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


@dataclass
class IpTaskRuntime:
    task_id: str
    project_dir: str
    novel_id: str
    character_ids: List[str]
    force_regenerate: bool
    created_at: str
    status: str = "running"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    return_code: Optional[int] = None
    error: Optional[str] = None
    result: Dict[str, object] = field(default_factory=dict)


class StartTaskRequest(BaseModel):
    project_dir: str
    command: Optional[str] = None


class SaveTemplateRequest(BaseModel):
    name: str
    project_dir: str
    command: str


class GenerateIpRequest(BaseModel):
    project_dir: str
    novel_id: str
    character_ids: List[str] = Field(default_factory=list)
    force_regenerate: bool = False


settings = get_settings()

app = FastAPI(title="StoryForge Console", version="0.2.0")
TASKS: Dict[str, TaskRuntime] = {}
IP_TASKS: Dict[str, IpTaskRuntime] = {}
TASK_LOCK = threading.Lock()
MAX_RUNNING_TASKS = settings.console.max_running_tasks
DEFAULT_COMMAND = settings.console.default_command
TEMPLATE_FILE = settings.console.template_file


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_name(raw: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fa5\-]+", "_", raw.strip())
    return cleaned.strip("_") or "unknown"


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


def _tail_logs(logs: Deque[str], offset: int) -> List[str]:
    data = list(logs)
    if offset < 0:
        offset = 0
    return data[offset:]


def _running_tasks_count() -> int:
    with TASK_LOCK:
        run_count = sum(1 for t in TASKS.values() if t.status == "running")
        ip_count = sum(1 for t in IP_TASKS.values() if t.status == "running")
        return run_count + ip_count


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


def _extract_chapter_text(chapter_obj: object) -> str:
    if isinstance(chapter_obj, str):
        return chapter_obj
    if isinstance(chapter_obj, dict):
        for key in ("text", "content", "chapter", "body"):
            if key in chapter_obj and isinstance(chapter_obj[key], str):
                return chapter_obj[key]
        return json.dumps(chapter_obj, ensure_ascii=False)
    text_attr = getattr(chapter_obj, "text", None)
    if isinstance(text_attr, str):
        return text_attr
    return str(chapter_obj)


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[。！？!?\n])", text)
    return [p.strip() for p in parts if p.strip()]


def _discover_novels(project_dir: str) -> List[dict]:
    debug_dir = Path(project_dir) / "debug_output"
    if not debug_dir.exists():
        return []

    snapshots = sorted(
        debug_dir.glob("state_final_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    novels: Dict[str, dict] = {}
    for snap in snapshots:
        try:
            data = json.loads(snap.read_text(encoding="utf-8"))
        except Exception:
            continue

        novel_id = str(data.get("novel_id") or snap.stem)
        if novel_id in novels:
            continue

        title = str(data.get("novel_title") or novel_id)
        chapters = data.get("chapters") if isinstance(data.get("chapters"), dict) else {}

        characters: List[str] = []
        if isinstance(data.get("characters"), list):
            for c in data["characters"]:
                if isinstance(c, dict) and c.get("name"):
                    characters.append(str(c["name"]))
                elif isinstance(c, str):
                    characters.append(c)
        if not characters and isinstance(data.get("character_ips"), dict):
            characters = [str(k) for k in data["character_ips"].keys()]

        novels[novel_id] = {
            "novel_id": novel_id,
            "novel_title": title,
            "snapshot_file": str(snap),
            "chapter_count": len(chapters),
            "characters": sorted(list({name.strip() for name in characters if name and name.strip()})),
            "updated_at": datetime.fromtimestamp(snap.stat().st_mtime).isoformat(timespec="seconds"),
        }

    return list(novels.values())


def _local_store_dir(project_dir: str) -> Path:
    return Path(project_dir) / "local_store"


def _ip_asset_dir(project_dir: str, novel_id: str) -> Path:
    return _local_store_dir(project_dir) / "ip_assets" / _safe_name(novel_id)


def _vector_store_file(project_dir: str) -> Path:
    return _local_store_dir(project_dir) / "vector_store.jsonl"


def _hash_vector(text: str, dim: int = 64) -> List[float]:
    tokens = re.findall(r"[\u4e00-\u9fa5]|[A-Za-z0-9_]+", text.lower())
    if not tokens:
        return [0.0] * dim

    vec = [0.0] * dim
    for tok in tokens:
        idx = hash(tok) % dim
        vec[idx] += 1.0

    norm = sum(v * v for v in vec) ** 0.5
    if norm == 0:
        return vec
    return [round(v / norm, 6) for v in vec]


def _upsert_vector_docs(project_dir: str, docs: List[dict]) -> int:
    store_file = _vector_store_file(project_dir)
    store_file.parent.mkdir(parents=True, exist_ok=True)

    records: Dict[str, dict] = {}
    if store_file.exists():
        for line in store_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            rec_id = str(rec.get("id") or "")
            if rec_id:
                records[rec_id] = rec

    upserted = 0
    for doc in docs:
        rec_id = str(doc.get("id") or "")
        if not rec_id:
            continue
        records[rec_id] = doc
        upserted += 1

    with open(store_file, "w", encoding="utf-8") as fout:
        for rec in records.values():
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return upserted


def _load_snapshot(project_dir: str, novel_id: str) -> dict:
    for item in _discover_novels(project_dir):
        if item["novel_id"] == novel_id:
            snap_file = Path(item["snapshot_file"])
            return json.loads(snap_file.read_text(encoding="utf-8"))
    raise RuntimeError(f"未找到小说快照: {novel_id}（请先跑一次生成流程）")


def _generate_character_ip(snapshot: dict, novel_id: str, novel_title: str, character_name: str) -> dict:
    chapters = snapshot.get("chapters") if isinstance(snapshot.get("chapters"), dict) else {}
    evidence: List[dict] = []

    for chapter_no, chapter_obj in chapters.items():
        chapter_text = _extract_chapter_text(chapter_obj)
        for sentence in _split_sentences(chapter_text):
            if character_name in sentence:
                evidence.append(
                    {
                        "chapter": str(chapter_no),
                        "quote": sentence[:200],
                    }
                )
            if len(evidence) >= 12:
                break
        if len(evidence) >= 12:
            break

    summary = (
        f"角色 {character_name} 在《{novel_title}》中共命中 {len(evidence)} 条证据片段。"
        "可在后续版本接入 LLM 生成更完整的人设卡。"
    )

    return {
        "novel_id": novel_id,
        "novel_title": novel_title,
        "character_id": character_name,
        "character_name": character_name,
        "generated_at": _now(),
        "summary": summary,
        "evidence": evidence,
        "version": datetime.now().strftime("%Y%m%d%H%M%S"),
    }


def _run_ip_task(task_id: str) -> None:
    with TASK_LOCK:
        task = IP_TASKS[task_id]

    task.started_at = _now()

    try:
        snapshot = _load_snapshot(task.project_dir, task.novel_id)
        novel_title = str(snapshot.get("novel_title") or task.novel_id)

        output_dir = _ip_asset_dir(task.project_dir, task.novel_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        generated_files: List[str] = []
        vector_docs: List[dict] = []

        for character_name in task.character_ids:
            asset_file = output_dir / f"{_safe_name(character_name)}.json"
            if asset_file.exists() and not task.force_regenerate:
                generated_files.append(str(asset_file))
                continue

            payload = _generate_character_ip(snapshot, task.novel_id, novel_title, character_name)
            asset_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            generated_files.append(str(asset_file))

            ip_text = payload.get("summary", "") + "\n" + "\n".join(
                f"第{e['chapter']}章: {e['quote']}" for e in payload.get("evidence", [])
            )
            vector_docs.append(
                {
                    "id": f"ip:{task.novel_id}:{character_name}",
                    "text": ip_text,
                    "vector": _hash_vector(ip_text),
                    "metadata": {
                        "doc_type": "character_ip",
                        "novel_id": task.novel_id,
                        "character_id": character_name,
                        "version": payload.get("version"),
                        "updated_at": payload.get("generated_at"),
                    },
                }
            )

            for idx, ev in enumerate(payload.get("evidence", [])):
                ev_text = f"{character_name} 第{ev['chapter']}章: {ev['quote']}"
                vector_docs.append(
                    {
                        "id": f"fact:{task.novel_id}:{character_name}:{idx}",
                        "text": ev_text,
                        "vector": _hash_vector(ev_text),
                        "metadata": {
                            "doc_type": "character_fact",
                            "novel_id": task.novel_id,
                            "character_id": character_name,
                            "chapter": ev.get("chapter"),
                            "updated_at": _now(),
                        },
                    }
                )

        upserted = _upsert_vector_docs(task.project_dir, vector_docs) if vector_docs else 0

        task.result = {
            "novel_id": task.novel_id,
            "character_count": len(task.character_ids),
            "generated_files": generated_files,
            "vector_docs_upserted": upserted,
            "vector_store": str(_vector_store_file(task.project_dir)),
        }
        task.return_code = 0
        task.status = "success"
    except Exception as exc:
        task.error = str(exc)
        task.return_code = 1
        task.status = "failed"
    finally:
        task.finished_at = _now()


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
    return f"""
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>StoryForge 控制台</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif; margin: 24px; }}
    input, select {{ width: 520px; padding: 8px; margin: 4px 0; }}
    button {{ padding: 8px 12px; margin-right: 8px; margin-top: 4px; }}
    #tasks {{ margin-top: 16px; }}
    .task {{ border: 1px solid #ddd; padding: 10px; margin-bottom: 8px; border-radius: 8px; }}
    pre {{ background: #111; color: #ddd; padding: 12px; border-radius: 8px; max-height: 420px; overflow: auto; }}
    .row {{ margin-bottom: 8px; }}
    .split {{ display: flex; gap: 24px; flex-wrap: wrap; }}
    .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px; min-width: 560px; }}
    #character_select {{ min-height: 140px; }}
  </style>
</head>
<body>
  <h2>StoryForge 操作页面（MVP）</h2>
  <p>支持按小说保存模板、并发上限控制、日志下载、人物IP手动生成与重生成。</p>
  <p>运行中上限：<strong id="max_running">-</strong></p>

  <div class="split">
    <div class="card">
      <h3>流程任务</h3>
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
        <input id="command" value="{DEFAULT_COMMAND}" />
      </div>
      <div style="margin-top:8px;">
        <button onclick="startTask()">启动任务</button>
        <button onclick="loadTasks()">刷新任务列表</button>
      </div>

      <div id="tasks"></div>

      <h4>日志</h4>
      <select id="task_select" onchange="offset=0;document.getElementById('logs').textContent='';pollLogs()"></select>
      <button onclick="stopTask()">停止选中任务</button>
      <button onclick="downloadLog()">下载日志</button>
      <pre id="logs"></pre>
    </div>

    <div class="card">
      <h3>人物 IP 生成（手动触发）</h3>
      <div class="row">
        <label>小说</label><br />
        <select id="novel_select" onchange="loadCharacters()"></select>
        <button onclick="loadNovels()">刷新小说列表</button>
      </div>
      <div class="row">
        <label>人物（可多选）</label><br />
        <select id="character_select" multiple></select>
      </div>
      <div class="row">
        <label>补充人物（逗号分隔，可选）</label><br />
        <input id="character_manual" placeholder="例如：林晚,陈默" />
      </div>
      <div>
        <button onclick="generateIp(false)">生成人物IP</button>
        <button onclick="generateIp(true)">重新生成（覆盖）</button>
        <button onclick="loadIpTasks()">刷新IP任务</button>
      </div>
      <pre id="ip_result"></pre>
      <div id="ip_tasks"></div>
    </div>
  </div>

<script>
let offset = 0;

async function loadConfig() {{
  const res = await fetch('/api/config');
  if (!res.ok) return;
  const data = await res.json();
  document.getElementById('max_running').innerText = data.max_running_tasks;
}}

async function loadTemplates() {{
  const res = await fetch('/api/templates');
  if (!res.ok) return;
  const data = await res.json();
  const sel = document.getElementById('template_select');
  sel.innerHTML = '<option value="">(选择模板)</option>';
  for (const t of data.templates) {{
    const opt = document.createElement('option');
    opt.value = t.name;
    opt.text = `${{t.name}} | ${{t.project_dir}}`;
    opt.dataset.project = t.project_dir;
    opt.dataset.command = t.command;
    sel.appendChild(opt);
  }}
}}

function applyTemplate() {{
  const sel = document.getElementById('template_select');
  const opt = sel.options[sel.selectedIndex];
  if (!opt || !opt.dataset.project) return;
  document.getElementById('project_dir').value = opt.dataset.project;
  document.getElementById('command').value = opt.dataset.command;
  loadNovels();
}}

async function saveTemplate() {{
  const name = prompt('模板名称（建议小说名）');
  if (!name) return;
  const project_dir = document.getElementById('project_dir').value;
  const command = document.getElementById('command').value;
  const res = await fetch('/api/templates', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{name, project_dir, command}})
  }});
  if (!res.ok) {{
    alert(await res.text());
    return;
  }}
  await loadTemplates();
}}

async function startTask() {{
  const project_dir = document.getElementById('project_dir').value;
  const command = document.getElementById('command').value;
  const res = await fetch('/api/tasks/start', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{project_dir, command}})
  }});
  if (!res.ok) {{
    alert(await res.text());
    return;
  }}
  offset = 0;
  document.getElementById('logs').textContent = '';
  await loadTasks();
}}

async function loadTasks() {{
  const res = await fetch('/api/tasks');
  if (!res.ok) return;
  const data = await res.json();
  const wrap = document.getElementById('tasks');
  const sel = document.getElementById('task_select');
  const current = sel.value;
  wrap.innerHTML = '';
  sel.innerHTML = '';
  for (const t of data.tasks) {{
    const d = document.createElement('div');
    d.className = 'task';
    d.innerText = `${{t.task_id}} | ${{t.status}} | ${{t.command}} | ${{t.project_dir}}`;
    wrap.appendChild(d);

    const opt = document.createElement('option');
    opt.value = t.task_id;
    opt.text = `${{t.task_id}} (${{t.status}})`;
    sel.appendChild(opt);
  }}
  if (current) sel.value = current;
}}

async function pollLogs() {{
  const taskId = document.getElementById('task_select').value;
  if (!taskId) return;
  const res = await fetch(`/api/tasks/${{taskId}}/logs?offset=${{offset}}`);
  if (!res.ok) return;
  const data = await res.json();
  offset = data.next_offset;
  const logBox = document.getElementById('logs');
  logBox.textContent += data.lines.join('');
  logBox.scrollTop = logBox.scrollHeight;
}}

async function stopTask() {{
  const taskId = document.getElementById('task_select').value;
  if (!taskId) return;
  await fetch(`/api/tasks/${{taskId}}/stop`, {{method: 'POST'}});
  await loadTasks();
}}

function downloadLog() {{
  const taskId = document.getElementById('task_select').value;
  if (!taskId) return;
  window.open(`/api/tasks/${{taskId}}/log-file`, '_blank');
}}

async function loadNovels() {{
  const project_dir = document.getElementById('project_dir').value;
  const res = await fetch(`/api/novels?project_dir=${{encodeURIComponent(project_dir)}}`);
  const sel = document.getElementById('novel_select');
  sel.innerHTML = '';
  if (!res.ok) {{
    sel.innerHTML = '<option value="">(加载失败)</option>';
    return;
  }}
  const data = await res.json();
  if (!data.novels.length) {{
    sel.innerHTML = '<option value="">(未发现小说快照，请先运行生成)</option>';
    document.getElementById('character_select').innerHTML = '';
    return;
  }}
  for (const n of data.novels) {{
    const opt = document.createElement('option');
    opt.value = n.novel_id;
    opt.text = `${{n.novel_title}} [${{n.novel_id}}]`;
    sel.appendChild(opt);
  }}
  await loadCharacters();
}}

async function loadCharacters() {{
  const project_dir = document.getElementById('project_dir').value;
  const novel_id = document.getElementById('novel_select').value;
  const sel = document.getElementById('character_select');
  sel.innerHTML = '';
  if (!novel_id) return;
  const res = await fetch(`/api/novels/${{encodeURIComponent(novel_id)}}/characters?project_dir=${{encodeURIComponent(project_dir)}}`);
  if (!res.ok) return;
  const data = await res.json();
  for (const name of data.characters) {{
    const opt = document.createElement('option');
    opt.value = name;
    opt.text = name;
    sel.appendChild(opt);
  }}
}}

async function generateIp(forceRegenerate) {{
  const project_dir = document.getElementById('project_dir').value;
  const novel_id = document.getElementById('novel_select').value;
  if (!novel_id) {{
    alert('请先选择小说');
    return;
  }}
  const selected = Array.from(document.getElementById('character_select').selectedOptions).map(o => o.value);
  const manualRaw = document.getElementById('character_manual').value || '';
  const manual = manualRaw.split(',').map(s => s.trim()).filter(Boolean);
  const character_ids = Array.from(new Set(selected.concat(manual)));

  if (!character_ids.length) {{
    alert('请至少选择或输入一个人物');
    return;
  }}

  const res = await fetch('/api/ip/generate', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{ project_dir, novel_id, character_ids, force_regenerate: forceRegenerate }})
  }});
  if (!res.ok) {{
    alert(await res.text());
    return;
  }}
  const data = await res.json();
  document.getElementById('ip_result').textContent = JSON.stringify(data, null, 2);
  await loadIpTasks();
}}

async function loadIpTasks() {{
  const res = await fetch('/api/ip/tasks');
  if (!res.ok) return;
  const data = await res.json();
  const wrap = document.getElementById('ip_tasks');
  wrap.innerHTML = '';
  for (const t of data.tasks) {{
    const d = document.createElement('div');
    d.className = 'task';
    d.innerText = `${{t.task_id}} | ${{t.status}} | novel=${{t.novel_id}} | characters=${{(t.character_ids || []).join(',')}}`;
    wrap.appendChild(d);
  }}
}}

setInterval(async () => {{
  await loadTasks();
  await pollLogs();
  await loadIpTasks();
}}, 3000);

loadConfig();
loadTemplates();
loadTasks();
loadNovels();
loadIpTasks();
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


@app.get("/api/novels")
async def list_novels(project_dir: str = Query(..., description="项目目录")) -> dict:
    project_dir = os.path.abspath(project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")
    return {"novels": _discover_novels(project_dir)}


@app.get("/api/novels/{novel_id}/characters")
async def list_novel_characters(
    novel_id: str,
    project_dir: str = Query(..., description="项目目录"),
) -> dict:
    project_dir = os.path.abspath(project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")

    for item in _discover_novels(project_dir):
        if item["novel_id"] == novel_id:
            return {"novel_id": novel_id, "characters": item.get("characters", [])}

    raise HTTPException(status_code=404, detail=f"小说不存在: {novel_id}")


@app.post("/api/ip/generate")
async def generate_ip(req: GenerateIpRequest) -> dict:
    project_dir = os.path.abspath(req.project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")

    character_ids = [c.strip() for c in req.character_ids if c and c.strip()]
    if not character_ids:
        raise HTTPException(status_code=400, detail="character_ids 不能为空")

    if _running_tasks_count() >= MAX_RUNNING_TASKS:
        raise HTTPException(
            status_code=429,
            detail=f"运行中任务已达上限（{MAX_RUNNING_TASKS}），请先停止或等待已有任务结束",
        )

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

    threading.Thread(target=_run_ip_task, args=(task_id,), daemon=True).start()
    return {"ok": True, "task": _ip_task_to_dict(task)}


@app.get("/api/ip/tasks")
async def list_ip_tasks() -> dict:
    with TASK_LOCK:
        tasks = sorted(IP_TASKS.values(), key=lambda x: x.created_at, reverse=True)
        return {"tasks": [_ip_task_to_dict(t) for t in tasks]}


@app.get("/api/ip/tasks/{task_id}")
async def get_ip_task(task_id: str) -> dict:
    task = IP_TASKS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"task": _ip_task_to_dict(task)}


@app.post("/api/tasks/start")
async def start_task(req: StartTaskRequest) -> dict:
    project_dir = os.path.abspath(req.project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")

    command = req.command or DEFAULT_COMMAND

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
    return {"ok": True, "tasks": len(TASKS), "ip_tasks": len(IP_TASKS)}
