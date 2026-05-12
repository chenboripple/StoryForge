"""人物 IP 生成业务（章节证据抽取 + 向量库 upsert）。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import List

from core.storage import StorageManager

from web_console.dependencies import _new_storage_manager
from web_console.runtime.queue import (
    IP_TASKS,
    TASK_LOCK,
    _save_runtime_state_unlocked,
    register_runner,
)
from web_console.services.novels import _extract_chapter_text, _split_sentences
from web_console.services.vector import (
    _hash_vector,
    _ip_asset_dir,
    _upsert_vector_docs,
    _vector_store_file,
)
from web_console.utils import _now, _safe_name


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


register_runner("ip", _run_ip_task)
