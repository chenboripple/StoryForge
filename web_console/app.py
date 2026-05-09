"""StoryForge 操作页面（MVP）"""

from __future__ import annotations

import asyncio
import hashlib
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
from typing import Any, Deque, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from core.config import get_config
from core.storage import StorageConfig, StorageManager
from core.models import (
    Chapter,
    ChapterStatus,
    NovelMeta,
    PipelineStage,
)
from core.ai_assistant import GenerationRequest, generate_suggestion
from core.models.video_assets import VideoState
from stages.video_script.video_script_generator import VideoScriptGenerator
from stages.video_bible.visual_bible_builder import VisualBibleBuilder
from stages.video_assets.video_asset_generator import VideoAssetGenerator
from core.video import StubImageProvider, StubEmbeddingProvider, VideoConsistencyService

_cfg = get_config()


def _new_storage_manager(cfg=None) -> StorageManager:
    runtime_cfg = cfg or _cfg
    return StorageManager(StorageConfig(data_dir=runtime_cfg.data_dir_abs))


def get_app_config_dep():
    return get_config()


def get_storage_manager_dep(cfg=Depends(get_app_config_dep)) -> StorageManager:
    # 每请求新建 StorageManager，避免跨请求共享缓存状态。
    return _new_storage_manager(cfg)


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


class GenerateVideoScriptRequest(BaseModel):
    project_dir: str
    novel_id: str


class CheckVideoConsistencyRequest(BaseModel):
    project_dir: str
    novel_id: str
    face_consistency_min: float = Field(default=0.82, ge=0.0, le=1.0)
    age_transition_min: float = Field(default=0.58, ge=0.0, le=1.0)
    scene_structure_min: float = Field(default=0.76, ge=0.0, le=1.0)


class AiGenerateRequest(BaseModel):
    prompt: str = ""
    step: str = "concept"
    context: Dict[str, Any] = Field(default_factory=dict)
    temperature: float = 0.7


class CreateNovelRequest(BaseModel):
    novel_id: str
    novel_title: Optional[str] = None
    genre: str = "未分类"
    concept: str = ""
    target_word_count: int = 3000


class SaveImportedRequest(BaseModel):
    novel_id: Optional[str] = None
    title: str = "未命名"
    author: str = ""
    genre: str = "未分类"
    concept: str = ""
    chapters: List[Dict[str, Any]] = Field(default_factory=list)


@dataclass
class QueueTask:
    task_id: str
    task_type: str  # "pipeline" | "ip"


app = FastAPI(title="StoryForge Console", version="0.2.0")
TASKS: Dict[str, TaskRuntime] = {}
IP_TASKS: Dict[str, IpTaskRuntime] = {}
TASK_LOCK = threading.Lock()
TASK_COND = threading.Condition(TASK_LOCK)
TASK_QUEUE: Deque[QueueTask] = deque()
RUNNING_TASK_IDS: set[str] = set()
CANCELLED_TASK_IDS: set[str] = set()
DISPATCHER_STARTED = False
MAX_RUNNING_TASKS = max(1, int(_cfg.console.max_running_tasks))
DEFAULT_COMMAND = _cfg.console.default_command
TEMPLATE_FILE = Path(_cfg.console.template_file_abs)
RUNTIME_STATE_FILE = Path(_cfg.data_dir_abs) / "console" / "runtime_state.json"


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
        return len(RUNNING_TASK_IDS)


def _queue_size() -> int:
    with TASK_LOCK:
        return len(TASK_QUEUE)


def _remove_queued_task_unlocked(task_id: str) -> bool:
    """在持有 TASK_LOCK 时，从队列移除某任务。"""
    for queued in list(TASK_QUEUE):
        if queued.task_id == task_id:
            TASK_QUEUE.remove(queued)
            return True
    return False


def _resolve_debug_output_dir() -> Path:
    debug_dir = Path(_cfg.debug.output_dir).expanduser()
    if debug_dir.is_absolute():
        return debug_dir
    if _cfg.config_path:
        return (Path(_cfg.config_path).parent / debug_dir).resolve()
    return (Path.cwd() / debug_dir).resolve()


def _resolve_project_dir(project_dir: str) -> str:
    return os.path.abspath(project_dir.strip())


def _save_runtime_state_unlocked() -> None:
    """持久化任务与队列状态。调用方必须持有 TASK_LOCK。"""
    payload = {
        "version": 1,
        "updated_at": _now(),
        "tasks": [_task_to_dict(task) for task in TASKS.values()],
        "ip_tasks": [_ip_task_to_dict(task) for task in IP_TASKS.values()],
        "queue": [{"task_id": item.task_id, "task_type": item.task_type} for item in TASK_QUEUE],
    }
    RUNTIME_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_runtime_state() -> None:
    """从磁盘恢复任务和队列状态。"""
    if not RUNTIME_STATE_FILE.exists():
        return

    try:
        payload = json.loads(RUNTIME_STATE_FILE.read_text(encoding="utf-8"))
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
        # 进程重启后 running 无法恢复，标记为 failed。
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

    with TASK_LOCK:
        TASKS.clear()
        TASKS.update(restored_tasks)
        IP_TASKS.clear()
        IP_TASKS.update(restored_ip_tasks)
        TASK_QUEUE.clear()
        TASK_QUEUE.extend(restored_queue)
        RUNNING_TASK_IDS.clear()
        CANCELLED_TASK_IDS.clear()


def _enqueue_task(task: QueueTask) -> int:
    with TASK_COND:
        TASK_QUEUE.append(task)
        queue_position = len(TASK_QUEUE)
        _save_runtime_state_unlocked()
        TASK_COND.notify_all()
        return queue_position


def _mark_task_running(task: QueueTask) -> None:
    if task.task_type == "pipeline":
        runtime = TASKS.get(task.task_id)
    else:
        runtime = IP_TASKS.get(task.task_id)
    if runtime:
        runtime.status = "running"
        if runtime.started_at is None:
            runtime.started_at = _now()


def _finalize_task(task_id: str) -> None:
    with TASK_COND:
        RUNNING_TASK_IDS.discard(task_id)
        _save_runtime_state_unlocked()
        TASK_COND.notify_all()


def _execute_queue_task(task: QueueTask) -> None:
    try:
        if task.task_type == "pipeline":
            _run_task(task.task_id)
        else:
            _run_ip_task(task.task_id)
    finally:
        _finalize_task(task.task_id)


def _dispatcher_loop() -> None:
    while True:
        task_to_run: Optional[QueueTask] = None
        with TASK_COND:
            while not TASK_QUEUE or len(RUNNING_TASK_IDS) >= MAX_RUNNING_TASKS:
                TASK_COND.wait()

            while TASK_QUEUE and task_to_run is None:
                task = TASK_QUEUE.popleft()

                # 被取消的任务不再调度，直接丢弃并清理标记。
                if task.task_id in CANCELLED_TASK_IDS:
                    CANCELLED_TASK_IDS.discard(task.task_id)
                    _save_runtime_state_unlocked()
                    continue

                # 任务对象可能已经被删除，跳过无效任务。
                runtime_exists = task.task_id in TASKS if task.task_type == "pipeline" else task.task_id in IP_TASKS
                if not runtime_exists:
                    continue

                task_to_run = task

            if task_to_run is None:
                continue

            RUNNING_TASK_IDS.add(task_to_run.task_id)
            _mark_task_running(task_to_run)
            _save_runtime_state_unlocked()

        threading.Thread(target=_execute_queue_task, args=(task_to_run,), daemon=True).start()


def _start_dispatcher() -> None:
    global DISPATCHER_STARTED
    with TASK_LOCK:
        if DISPATCHER_STARTED:
            return
        DISPATCHER_STARTED = True
    threading.Thread(target=_dispatcher_loop, daemon=True).start()


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


def _allowed_commands_for_project(project_dir: str) -> set[str]:
    """返回指定项目目录允许执行的命令集合。"""
    allowed: set[str] = {DEFAULT_COMMAND.strip()}
    normalized_project = os.path.abspath(project_dir)

    for template in _load_templates():
        t_project = os.path.abspath(str(template.get("project_dir") or "").strip())
        t_command = str(template.get("command") or "").strip()
        if t_project == normalized_project and t_command:
            allowed.add(t_command)

    return allowed


def _assert_command_allowed(project_dir: str, command: str) -> None:
    """校验命令是否在白名单中。"""
    normalized_command = command.strip()
    allowed = _allowed_commands_for_project(project_dir)

    if normalized_command in allowed:
        return

    raise HTTPException(
        status_code=400,
        detail=(
            "命令不在白名单中。请使用默认命令，或先在“模板”中保存该命令后再启动。"
        ),
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
    content_attr = getattr(chapter_obj, "content", None)
    if isinstance(content_attr, str):
        return content_attr
    return str(chapter_obj)


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[。！？!?\n])", text)
    return [p.strip() for p in parts if p.strip()]


def _discover_novels(project_dir: str, sm: StorageManager) -> List[dict]:
    # project_dir 保留用于接口兼容，小说数据统一从 StorageManager 读取。
    _ = project_dir

    novels: List[dict] = []
    for entry in sm.list_novels():
        novel_id = str(entry.get("novel_id") or "").strip()
        if not novel_id:
            continue

        title = str(entry.get("novel_title") or novel_id)
        chapters = sm.load_chapters(novel_id)

        character_names: List[str] = []
        char_graph = sm.load_characters(novel_id)
        if char_graph and getattr(char_graph, "characters", None):
            character_names = [
                c.name.strip() for c in char_graph.characters
                if getattr(c, "name", "") and c.name.strip()
            ]

        novels.append(
            {
                "novel_id": novel_id,
                "novel_title": title,
                "chapter_count": len(chapters),
                "characters": sorted(list(set(character_names))),
                "updated_at": str(entry.get("updated_at") or ""),
            }
        )

    novels.sort(key=lambda n: n.get("updated_at") or "", reverse=True)
    return novels


def _local_store_dir(project_dir: str) -> Path:
    _ = project_dir
    return Path(_cfg.data_dir_abs) / "local_store"


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
        digest = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:8], "big") % dim
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


def _load_snapshot(project_dir: str, novel_id: str, sm: StorageManager) -> dict:
    _ = project_dir
    meta = sm.load_novel_meta(novel_id)
    if not meta:
        raise RuntimeError(f"未找到小说: {novel_id}")

    chapters = sm.load_chapters(novel_id)
    chapter_payload = {
        str(ch_num): chapter.content
        for ch_num, chapter in chapters.items()
    }

    return {
        "novel_id": novel_id,
        "novel_title": meta.novel_title or novel_id,
        "chapters": chapter_payload,
    }


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
        if task.started_at is None:
            task.started_at = _now()

    try:
        sm = _new_storage_manager()
        snapshot = _load_snapshot(task.project_dir, task.novel_id, sm)
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

        with TASK_LOCK:
            task.result = {
                "novel_id": task.novel_id,
                "character_count": len(task.character_ids),
                "generated_files": generated_files,
                "vector_docs_upserted": upserted,
                "vector_store": str(_vector_store_file(task.project_dir)),
            }
            task.return_code = 0
            task.status = "success"
            _save_runtime_state_unlocked()
    except Exception as exc:
        with TASK_LOCK:
            task.error = str(exc)
            task.return_code = 1
            task.status = "failed"
            _save_runtime_state_unlocked()
    finally:
        with TASK_LOCK:
            task.finished_at = _now()
            _save_runtime_state_unlocked()


def _generate_video_script_assets(project_dir: str, novel_id: str, sm: StorageManager) -> dict:
    _ = project_dir
    meta = sm.load_novel_meta(novel_id)
    if not meta:
        raise RuntimeError(f"未找到小说: {novel_id}")

    chapters = sm.load_chapters(novel_id)
    if not chapters:
        raise RuntimeError(f"小说无章节内容: {novel_id}")

    chars = sm.load_characters(novel_id)

    script_generator = VideoScriptGenerator()
    bible_builder = VisualBibleBuilder()
    asset_generator = VideoAssetGenerator(image_provider=StubImageProvider())

    script = script_generator.generate(
        novel_id=novel_id,
        title=meta.novel_title or novel_id,
        chapters=chapters,
    )
    bible = bible_builder.build(novel_id, script, chars)
    manifest = asset_generator.generate(novel_id, script, bible)

    sm.save_video_script(novel_id, script)
    sm.save_visual_bible(novel_id, bible)
    sm.save_video_manifest(novel_id, manifest)

    state = sm.load_video_state(novel_id) or VideoState(novel_id=novel_id)
    state.script = script
    state.visual_bible = bible
    state.manifest = manifest
    state.status = "asseted"
    state.error_message = ""
    sm.save_video_state(novel_id, state)

    return {
        "novel_id": novel_id,
        "shot_count": len(script.shots),
        "character_profile_count": len(bible.character_profiles),
        "scene_profile_count": len(bible.scene_profiles),
        "asset_count": len(manifest.assets),
    }


def _check_video_consistency(project_dir: str, novel_id: str, thresholds: dict, sm: StorageManager) -> dict:
    _ = project_dir
    bible = sm.load_visual_bible(novel_id)
    manifest = sm.load_video_manifest(novel_id)
    if not bible or not manifest:
        raise RuntimeError("缺少视觉圣经或资产索引，请先生成视频剧本与资产")

    service = VideoConsistencyService(embedding_provider=StubEmbeddingProvider())
    report = service.validate(
        novel_id=novel_id,
        bible=bible,
        manifest=manifest,
        threshold_overrides=thresholds,
    )
    sm.save_video_consistency_report(novel_id, report)

    state = sm.load_video_state(novel_id) or VideoState(novel_id=novel_id)
    state.consistency_report = report
    state.status = "asseted" if report.passed else "failed"
    state.error_message = "\n".join(report.fallback_reasons) if report.fallback_reasons else ""
    sm.save_video_state(novel_id, state)

    return report.to_dict()


def _run_task(task_id: str) -> None:
    with TASK_LOCK:
        task = TASKS[task_id]
        if task.started_at is None:
            task.started_at = _now()

    log_dir = _resolve_debug_output_dir() / "console_runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{task.task_id}.log"

    with TASK_LOCK:
        task.log_file = str(log_file)

    process = subprocess.Popen(
        shlex.split(task.command),
        cwd=task.project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    with TASK_LOCK:
        task.process = process
        task.pid = process.pid
        _save_runtime_state_unlocked()

    with open(log_file, "w", encoding="utf-8") as fout:
        if process.stdout:
            for line in process.stdout:
                with TASK_LOCK:
                    task.logs.append(line)
                fout.write(line)
                fout.flush()

    rc = process.wait()
    with TASK_LOCK:
        task.return_code = rc
        task.finished_at = _now()
        if task.status != "stopped":
            task.status = "success" if rc == 0 else "failed"
        _save_runtime_state_unlocked()


_load_runtime_state()
_start_dispatcher()


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

        <div class="card">
            <h3>视频剧本与一致性检查（骨架）</h3>
            <div class="row">
                <label>目标小说</label><br />
                <select id="video_novel_select"></select>
            </div>
            <div class="row">
                <label>阈值：人脸一致性 (0-1)</label><br />
                <input id="th_face" type="number" step="0.01" min="0" max="1" value="0.82" />
            </div>
            <div class="row">
                <label>阈值：年龄迁移 (0-1)</label><br />
                <input id="th_age" type="number" step="0.01" min="0" max="1" value="0.58" />
            </div>
            <div class="row">
                <label>阈值：场景结构相似度 (0-1)</label><br />
                <input id="th_scene" type="number" step="0.01" min="0" max="1" value="0.76" />
            </div>
            <div>
                <button onclick="generateVideoScript()">生成剧本与资产骨架</button>
                <button onclick="checkVideoConsistency()">执行一致性检查</button>
            </div>
            <pre id="video_result"></pre>
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
    const videoSel = document.getElementById('video_novel_select');
  sel.innerHTML = '';
    videoSel.innerHTML = '';
  if (!res.ok) {{
    sel.innerHTML = '<option value="">(加载失败)</option>';
        videoSel.innerHTML = '<option value="">(加载失败)</option>';
    return;
  }}
  const data = await res.json();
  if (!data.novels.length) {{
    sel.innerHTML = '<option value="">(未发现小说快照，请先运行生成)</option>';
    document.getElementById('character_select').innerHTML = '';
        videoSel.innerHTML = '<option value="">(未发现小说)</option>';
    return;
  }}
  for (const n of data.novels) {{
    const opt = document.createElement('option');
    opt.value = n.novel_id;
    opt.text = `${{n.novel_title}} [${{n.novel_id}}]`;
    sel.appendChild(opt);

        const vopt = document.createElement('option');
        vopt.value = n.novel_id;
        vopt.text = `${{n.novel_title}} [${{n.novel_id}}]`;
        videoSel.appendChild(vopt);
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

async function generateVideoScript() {{
    const project_dir = document.getElementById('project_dir').value;
    const novel_id = document.getElementById('video_novel_select').value;
    if (!novel_id) {{
        alert('请先选择小说');
        return;
    }}

    const res = await fetch('/api/video/script/generate', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{ project_dir, novel_id }})
    }});
    if (!res.ok) {{
        alert(await res.text());
        return;
    }}

    const data = await res.json();
    document.getElementById('video_result').textContent = JSON.stringify(data, null, 2);
}}

async function checkVideoConsistency() {{
    const project_dir = document.getElementById('project_dir').value;
    const novel_id = document.getElementById('video_novel_select').value;
    if (!novel_id) {{
        alert('请先选择小说');
        return;
    }}

    const face_consistency_min = Number(document.getElementById('th_face').value || 0.82);
    const age_transition_min = Number(document.getElementById('th_age').value || 0.58);
    const scene_structure_min = Number(document.getElementById('th_scene').value || 0.76);

    const res = await fetch('/api/video/consistency/check', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{
            project_dir,
            novel_id,
            face_consistency_min,
            age_transition_min,
            scene_structure_min
        }})
    }});
    if (!res.ok) {{
        alert(await res.text());
        return;
    }}

    const data = await res.json();
    document.getElementById('video_result').textContent = JSON.stringify(data, null, 2);
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
async def get_console_config() -> dict:
    return {
        "max_running_tasks": MAX_RUNNING_TASKS,
        "configured_max_running_tasks": _cfg.console.max_running_tasks,
        "running_tasks": _running_tasks_count(),
        "queued_tasks": _queue_size(),
    }


@app.get("/api/health")
async def api_health(cfg=Depends(get_app_config_dep)) -> dict:
    return {
        "status": "ok",
        "config_path": cfg.config_path,
        "data_dir": cfg.data_dir_abs,
    }


@app.post("/api/ai/generate")
async def ai_generate(req: AiGenerateRequest) -> dict:
    payload = GenerationRequest(
        prompt=req.prompt,
        step=req.step,
        context=req.context,
        temperature=req.temperature,
    )
    resp = generate_suggestion(payload)
    if not resp.success:
        raise HTTPException(status_code=500, detail=resp.error or "生成失败")
    return {
        "success": True,
        "content": resp.content,
        "suggestions": resp.suggestions,
    }


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
async def list_novels(
    project_dir: Optional[str] = Query(None, description="项目目录（console模式可选）"),
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> Any:
    # 兼容 backend 行为：不传 project_dir 时返回索引列表。
    if project_dir is None or not project_dir.strip():
        return sm.list_novels()

    project_dir = _resolve_project_dir(project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")
    return {"novels": _discover_novels(project_dir, sm)}


@app.post("/api/novels")
async def create_novel(
    req: CreateNovelRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    novel_id = req.novel_id.strip()
    if not novel_id:
        raise HTTPException(status_code=400, detail="缺少小说ID")
    if sm.novel_exists(novel_id):
        raise HTTPException(status_code=409, detail=f"小说已存在: {novel_id}")

    meta = NovelMeta(
        novel_id=novel_id,
        novel_title=(req.novel_title or novel_id).strip(),
        genre=req.genre,
        concept=req.concept,
        target_word_count=req.target_word_count,
        current_stage=PipelineStage.CREATION,
        current_chapter=1,
        total_chapters=0,
        approved_chapters=0,
    )
    sm.save_novel_meta(novel_id, meta)
    sm.rebuild_index()
    return {"success": True, "novel_id": novel_id, "novel_title": meta.novel_title}


@app.get("/api/novels/{novel_id}")
async def get_novel(
    novel_id: str,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    result = meta.to_index_entry()
    characters_list: List[Dict[str, Any]] = []
    try:
        char_graph = sm.load_characters(novel_id)
        if char_graph and getattr(char_graph, "characters", None):
            for char in char_graph.characters:
                char_dict: Dict[str, Any] = {}
                if hasattr(char, "to_dict"):
                    try:
                        char_dict = char.to_dict()
                    except Exception:
                        char_dict = {}
                if not char_dict:
                    char_dict = {
                        "id": getattr(char, "character_id", getattr(char, "id", "")),
                        "character_id": getattr(char, "character_id", ""),
                        "name": getattr(char, "name", ""),
                        "description": getattr(char, "description", ""),
                        "personality": getattr(char, "personality", ""),
                        "background": getattr(char, "background", ""),
                        "age": getattr(char, "age", None),
                        "gender": getattr(char, "gender", ""),
                    }
                characters_list.append(char_dict)
    except Exception:
        pass

    result["characters"] = characters_list
    return result


@app.get("/api/novels/{novel_id}/chapters")
async def list_chapters(
    novel_id: str,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    chapters = sm.load_chapters(novel_id)
    reviews = sm.load_reviews(novel_id)

    result = []
    for num in sorted(chapters.keys()):
        ch = chapters[num]
        review = reviews.get(num)
        latest = review.get_latest() if review else None
        result.append(
            {
                "chapter_num": num,
                "title": ch.title,
                "status": ch.status.value,
                "word_count": ch.word_count,
                "preview": ch.get_preview(),
                "review_rounds": len(review.records) if review else 0,
                "latest_score": latest.total_score if latest else None,
                "latest_passed": latest.passed if latest else None,
            }
        )

    return {
        "novel_id": novel_id,
        "current_chapter": meta.current_chapter,
        "total_chapters": meta.total_chapters,
        "chapters": result,
    }


@app.get("/api/novels/{novel_id}/chapters/{chapter_num}")
async def get_chapter(
    novel_id: str,
    chapter_num: int,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"novel not found: {novel_id}")

    chapters = sm.load_chapters(novel_id)
    ch = chapters.get(chapter_num)
    if ch is None:
        raise HTTPException(status_code=404, detail=f"chapter not found: {chapter_num}")

    reviews = sm.load_reviews(novel_id)
    review = reviews.get(chapter_num)
    proofreads = sm.load_proofreads(novel_id)
    proofread = proofreads.get(chapter_num)

    return {
        "novel_id": novel_id,
        "chapter_num": chapter_num,
        "title": ch.title,
        "status": ch.status.value,
        "content": ch.content,
        "word_count": ch.word_count,
        "reviews": [r.to_dict() for r in (review.records if review else [])],
        "proofread_records": [p.to_dict() for p in (proofread.records if proofread else [])],
    }


@app.get("/api/import/formats")
async def list_import_formats() -> dict:
    return {
        "formats": [
            {
                "type": "text",
                "name": "纯文本",
                "extensions": ["txt", "md", "markdown", "html", "htm", "rst", "org"],
                "description": "直接读取纯文本内容，支持自动章节识别",
            },
            {
                "type": "epub",
                "name": "EPUB 电子书",
                "extensions": ["epub"],
                "description": "解析 EPUB 章节结构和元数据",
            },
            {
                "type": "pdf",
                "name": "PDF 文档",
                "extensions": ["pdf"],
                "description": "提取 PDF 文字内容，扫描件建议使用图片导入",
            },
            {
                "type": "image",
                "name": "图片（OCR）",
                "extensions": ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "tif", "webp"],
                "description": "通过 OCR 识别图片中的文字",
            },
        ]
    }


@app.post("/api/import/upload")
async def upload_file(
    file: UploadFile = File(...),
    chapter_pattern: Optional[str] = Form(None),
    ocr_language: Optional[str] = Form(None),
    merge_chapters: Optional[bool] = Form(None),
) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    import tempfile

    upload_dir = os.path.join(tempfile.gettempdir(), "storyforge_uploads")
    os.makedirs(upload_dir, exist_ok=True)
    safe_filename = os.path.basename(file.filename)
    filepath = os.path.join(upload_dir, safe_filename)

    content = await file.read()
    with open(filepath, "wb") as fout:
        fout.write(content)

    options: Dict[str, Any] = {}
    if chapter_pattern:
        options["chapter_pattern"] = chapter_pattern
    if ocr_language:
        options["ocr_language"] = ocr_language
    if merge_chapters is not None:
        options["merge_chapters"] = merge_chapters

    from stages.importer.novel_importer import NovelImporter

    importer = NovelImporter()
    result = importer.parse(filepath, **options)

    try:
        os.unlink(filepath)
    except Exception:
        pass

    if not result.success:
        raise HTTPException(
            status_code=422,
            detail={
                "success": False,
                "errors": result.errors,
                "warnings": result.warnings,
            },
        )

    return {
        "success": True,
        "preview": {
            "title": result.novel_title,
            "author": result.author,
            "genre": result.genre,
            "total_chapters": result.total_chapters,
            "total_word_count": result.total_word_count,
            "chapters": [
                {
                    "chapter_num": ch.chapter_num,
                    "title": ch.title,
                    "word_count": ch.word_count,
                    "preview": ch.content[:200] if ch.content else "",
                }
                for ch in result.chapters[:10]
            ],
        },
        "warnings": result.warnings,
        "full_result": {
            "chapters": [
                {
                    "chapter_num": ch.chapter_num,
                    "title": ch.title,
                    "content": ch.content,
                    "word_count": ch.word_count,
                }
                for ch in result.chapters
            ],
            "metadata": result.metadata,
        },
    }


@app.post("/api/import/save")
async def save_imported(
    req: SaveImportedRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    if not req.chapters:
        raise HTTPException(status_code=400, detail="缺少章节数据")

    novel_id = (req.novel_id or "").strip()
    if not novel_id:
        from datetime import datetime

        safe_title = "".join(c for c in req.title if c.isalnum() or c == "_")
        novel_id = f"{safe_title or 'imported'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    meta = NovelMeta(
        novel_id=novel_id,
        novel_title=req.title,
        genre=req.genre,
        concept=req.concept,
        target_word_count=max(
            sum(len(ch.get("content", "")) for ch in req.chapters) // max(len(req.chapters), 1),
            3000,
        ),
        current_stage=PipelineStage.CREATION,
    )
    sm.save_novel_meta(novel_id, meta)

    chapters: Dict[int, Chapter] = {}
    for ch in req.chapters:
        num = int(ch.get("chapter_num", 1))
        chapters[num] = Chapter(
            novel_id=novel_id,
            chapter_num=num,
            title=str(ch.get("title", "")),
            content=str(ch.get("content", "")),
            status=ChapterStatus.DRAFT,
        )
    sm.save_chapters(novel_id, chapters)

    meta.total_chapters = len(chapters)
    meta.draft_chapters = len(chapters)
    sm.save_novel_meta(novel_id, meta)

    return {
        "success": True,
        "novel_id": novel_id,
        "title": req.title,
        "chapter_count": len(chapters),
    }


@app.get("/api/novels/{novel_id}/characters")
async def list_novel_characters(
    novel_id: str,
    project_dir: str = Query(..., description="项目目录"),
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    project_dir = _resolve_project_dir(project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")

    for item in _discover_novels(project_dir, sm):
        if item["novel_id"] == novel_id:
            return {"novel_id": novel_id, "characters": item.get("characters", [])}

    raise HTTPException(status_code=404, detail=f"小说不存在: {novel_id}")


@app.post("/api/ip/generate")
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


@app.post("/api/video/script/generate")
async def generate_video_script(
    req: GenerateVideoScriptRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    project_dir = _resolve_project_dir(req.project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")

    novel_id = req.novel_id.strip()
    if not novel_id:
        raise HTTPException(status_code=400, detail="novel_id 不能为空")

    try:
        result = _generate_video_script_assets(project_dir, novel_id, sm)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"ok": True, "result": result}


@app.post("/api/video/consistency/check")
async def check_video_consistency(
    req: CheckVideoConsistencyRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    project_dir = _resolve_project_dir(req.project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")

    novel_id = req.novel_id.strip()
    if not novel_id:
        raise HTTPException(status_code=400, detail="novel_id 不能为空")

    try:
        report = _check_video_consistency(
            project_dir,
            novel_id,
            thresholds={
                "face_consistency_min": req.face_consistency_min,
                "age_transition_min": req.age_transition_min,
                "scene_structure_min": req.scene_structure_min,
            },
            sm=sm,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {"ok": True, "report": report}


@app.get("/api/video/consistency/{novel_id}")
async def get_video_consistency(
    novel_id: str,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    report = sm.load_video_consistency_report(novel_id)
    if not report:
        raise HTTPException(status_code=404, detail="未找到一致性报告")
    return {"ok": True, "report": report.to_dict()}


@app.get("/api/ip/tasks")
async def list_ip_tasks() -> dict:
    with TASK_LOCK:
        tasks = sorted(IP_TASKS.values(), key=lambda x: x.created_at, reverse=True)
        return {"tasks": [_ip_task_to_dict(t) for t in tasks]}


@app.get("/api/ip/tasks/{task_id}")
async def get_ip_task(task_id: str) -> dict:
    with TASK_LOCK:
        task = IP_TASKS.get(task_id)
        task_payload = _ip_task_to_dict(task) if task else None
    if not task_payload:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"task": task_payload}


@app.post("/api/tasks/start")
async def start_task(req: StartTaskRequest) -> dict:
    project_dir = _resolve_project_dir(req.project_dir)
    if not os.path.isdir(project_dir):
        raise HTTPException(status_code=400, detail=f"目录不存在: {project_dir}")

    command = (req.command or DEFAULT_COMMAND).strip()
    _assert_command_allowed(project_dir, command)

    task_id = uuid.uuid4().hex[:12]
    task = TaskRuntime(
        task_id=task_id,
        project_dir=project_dir,
        command=command,
        created_at=_now(),
    )

    with TASK_LOCK:
        TASKS[task_id] = task
        _save_runtime_state_unlocked()
    queue_position = _enqueue_task(QueueTask(task_id=task_id, task_type="pipeline"))

    return {"ok": True, "task": _task_to_dict(task), "queue_position": queue_position}


@app.get("/api/tasks")
async def list_tasks() -> dict:
    with TASK_LOCK:
        tasks = sorted(TASKS.values(), key=lambda x: x.created_at, reverse=True)
        return {"tasks": [_task_to_dict(t) for t in tasks]}


@app.get("/api/tasks/{task_id}/logs")
async def get_logs(task_id: str, offset: int = 0) -> dict:
    with TASK_LOCK:
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
    with TASK_LOCK:
        task = TASKS.get(task_id)
        log_file = task.log_file if task else None
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not log_file or not os.path.exists(log_file):
        raise HTTPException(status_code=404, detail="日志文件不存在")
    return FileResponse(log_file, filename=f"{task_id}.log", media_type="text/plain")


@app.post("/api/tasks/{task_id}/stop")
async def stop_task(task_id: str) -> dict:
    with TASK_LOCK:
        task = TASKS.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")

        removed = _remove_queued_task_unlocked(task_id)
        if removed:
            CANCELLED_TASK_IDS.add(task_id)
            task.status = "stopped"
            task.finished_at = _now()
            _save_runtime_state_unlocked()
            TASK_COND.notify_all()
            return {"ok": True, "task": _task_to_dict(task)}

        if task.status == "queued":
            # queued 但不在队列中（可能已被调度线程取走），仍视为停止。
            CANCELLED_TASK_IDS.add(task_id)
            task.status = "stopped"
            task.finished_at = _now()
            _save_runtime_state_unlocked()
            TASK_COND.notify_all()
            return {"ok": True, "task": _task_to_dict(task)}

        proc = task.process

    if proc and proc.poll() is None:
        proc.terminate()
        await asyncio.sleep(0.2)
        if proc.poll() is None:
            proc.kill()
        with TASK_LOCK:
            task.status = "stopped"
            task.finished_at = _now()
            _save_runtime_state_unlocked()

    with TASK_LOCK:
        payload = _task_to_dict(task)
    return {"ok": True, "task": payload}


@app.get("/health")
async def health() -> dict:
    with TASK_LOCK:
        return {
            "ok": True,
            "tasks": len(TASKS),
            "ip_tasks": len(IP_TASKS),
            "running_tasks": len(RUNNING_TASK_IDS),
            "queued_tasks": len(TASK_QUEUE),
        }
