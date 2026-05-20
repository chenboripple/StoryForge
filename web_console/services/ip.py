"""人物 IP 生成业务（章节证据抽取 + 向量库 upsert）。"""

from __future__ import annotations

import json
from typing import List

from core.ip_workflow import build_character_ip_payload, generate_story_bible_for_novel, select_story_bible_characters
from core.model_router.model_router import ModelRouter, TaskType
from stages.ip_generation.ip_generator import IPGenerator

from web_console.dependencies import _new_storage_manager
from web_console.runtime.registry import TaskRegistry
from web_console.services.vector import (
    _hash_vector,
    _ip_asset_dir,
    _upsert_vector_docs,
    _vector_store_file,
)
from web_console.utils import _now, _safe_name


def _build_ip_generator_client():
    try:
        router = ModelRouter()
        routed = router.route(TaskType.REVIEW, agent_name="reviewer")
        return router.get_client(routed.model_name)
    except Exception:
        return None


def _run_ip_task(task_id: str, registry: TaskRegistry) -> None:
    with registry.task_lock:
        task = registry.ip_tasks[task_id]
        if task.started_at is None:
            task.started_at = _now()

    try:
        sm = _new_storage_manager()
        meta = sm.load_novel_meta(task.novel_id)
        if not meta:
            raise RuntimeError(f"未找到小说: {task.novel_id}")
        novel_title = str(meta.novel_title or task.novel_id)
        generator = IPGenerator(llm_client=_build_ip_generator_client())
        bible = generate_story_bible_for_novel(sm, task.novel_id, generator)
        selected_chars = select_story_bible_characters(bible, task.character_ids)

        output_dir = _ip_asset_dir(task.project_dir, task.novel_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        generated_files: List[str] = []
        vector_docs: List[dict] = []

        for char_ip in selected_chars:
            character_name = str(char_ip.name or char_ip.character_id)
            asset_file = output_dir / f"{_safe_name(character_name)}.json"
            if asset_file.exists() and not task.force_regenerate:
                generated_files.append(str(asset_file))
                continue

            payload = build_character_ip_payload(
                novel_id=task.novel_id,
                novel_title=novel_title,
                char_ip=char_ip,
                generated_at=_now(),
            )
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

        with registry.task_lock:
            task.result = {
                "novel_id": task.novel_id,
                "character_count": len(selected_chars),
                "generated_files": generated_files,
                "vector_docs_upserted": upserted,
                "vector_store": str(_vector_store_file(task.project_dir)),
                "story_bible_saved": True,
            }
            task.return_code = 0
            task.status = "success"
            registry._save_state_unlocked()
    except Exception as exc:
        with registry.task_lock:
            task.error = str(exc)
            task.return_code = 1
            task.status = "failed"
            registry._save_state_unlocked()
    finally:
        with registry.task_lock:
            task.finished_at = _now()
            registry._save_state_unlocked()


def register_ip_runner(registry: TaskRegistry) -> None:
    """将 IP 任务执行器注册到指定 TaskRegistry。"""

    def _runner(task_id: str) -> None:
        _run_ip_task(task_id, registry)

    registry.register_runner("ip", _runner)
