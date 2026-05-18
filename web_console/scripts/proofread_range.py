"""Run proofread for a selected chapter scope and persist results."""

from __future__ import annotations

import argparse
from datetime import datetime
from typing import List

from agents.creation_agents import ProofreaderAgent
from core.config import get_config
from core.llm_factory import create_llm_client
from core.models import ChapterStatus, PipelineStage, Proofread, ProofreadRecord
from core.schema import ChapterContent
from core.state import CharacterInfo, NovelState
from core.storage import StorageConfig, StorageManager


def _new_storage_manager() -> StorageManager:
    cfg = get_config()
    return StorageManager(StorageConfig(data_dir=cfg.data_dir_abs))


def _to_character_infos(sm: StorageManager, novel_id: str) -> list[CharacterInfo]:
    graph = sm.load_characters(novel_id)
    if not graph:
        return []
    items: list[CharacterInfo] = []
    for c in graph.characters:
        items.append(
            CharacterInfo(
                name=c.name or c.character_id,
                age=c.age,
                appearance=c.appearance,
                personality=c.personality,
                background=c.background,
                goals=list(c.goals or []),
            )
        )
    return items


def _resolve_chapters(scope: str, chapter: int | None, volume: int | None, available: List[int]) -> List[int]:
    if not available:
        return []
    ordered = sorted(set(int(x) for x in available if int(x) > 0))

    if scope == "book":
        return ordered

    if scope == "volume":
        v = volume
        if not v and chapter and chapter > 0:
            v = ((chapter - 1) // 10) + 1
        if not v or v <= 0:
            return []
        start = (v - 1) * 10 + 1
        end = start + 9
        return [x for x in ordered if start <= x <= end]

    # chapter scope
    if chapter and chapter > 0:
        return [chapter] if chapter in ordered else []
    return [ordered[-1]]


def run_proofread(novel_id: str, scope: str, chapter: int | None, volume: int | None) -> dict:
    sm = _new_storage_manager()
    meta = sm.load_novel_meta(novel_id)
    if not meta:
        raise ValueError(f"novel not found: {novel_id}")

    chapters = sm.load_chapters(novel_id)
    chapter_nums = _resolve_chapters(scope, chapter, volume, list(chapters.keys()))
    if not chapter_nums:
        raise ValueError("未找到可校对章节，请先生成章节")

    llm_client = create_llm_client(get_config().llm)
    proofreader = ProofreaderAgent(llm_client=llm_client)
    chars = _to_character_infos(sm, novel_id)
    world = sm.load_world(novel_id)

    proofreads = sm.load_proofreads(novel_id)
    now = datetime.now().isoformat()

    passed_count = 0
    for ch_num in chapter_nums:
        ch = chapters.get(ch_num)
        if ch is None or not (ch.content or "").strip():
            continue

        state = NovelState(
            novel_id=novel_id,
            novel_title=meta.novel_title,
            genre=meta.genre,
            concept=meta.concept,
            current_stage=PipelineStage.CREATION,
            current_chapter=ch_num,
            characters=chars,
            proofread_scope=scope,
            proofread_context={
                "world_setting": world.to_dict() if world else None,
            },
        )
        state.chapters[ch_num] = ChapterContent(text=ch.content)
        state.chapter_status[ch_num] = ch.status

        state = proofreader.invoke(state)

        latest_result = (state.proofread_results.get(ch_num) or [])[-1]
        aggregate = proofreads.get(ch_num) or Proofread(novel_id=novel_id, chapter_num=ch_num)
        aggregate.add_record(
            ProofreadRecord(
                novel_id=novel_id,
                chapter_num=ch_num,
                round=len(aggregate.records) + 1,
                proofreader="砚清",
                issues=list(getattr(latest_result, "issues", []) or []),
                passed=bool(getattr(latest_result, "passed", False)),
                summary=str(getattr(latest_result, "summary", "") or ""),
                scope=scope,
                timestamp=now,
            )
        )
        proofreads[ch_num] = aggregate

        new_status = state.chapter_status.get(ch_num)
        if isinstance(new_status, ChapterStatus):
            ch.status = new_status
        ch.updated_at = now
        chapters[ch_num] = ch

        if ch.status == ChapterStatus.APPROVED:
            passed_count += 1

    sm.save_proofreads(novel_id, proofreads)
    sm.save_chapters(novel_id, chapters)

    meta = sm.load_novel_meta(novel_id)
    if meta:
        meta.current_stage = PipelineStage.CREATION
        meta.approved_chapters = sum(1 for x in chapters.values() if x.status == ChapterStatus.APPROVED)
        sm.save_novel_meta(novel_id, meta)

    return {
        "novel_id": novel_id,
        "scope": scope,
        "chapters": chapter_nums,
        "passed": passed_count,
        "total": len(chapter_nums),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Proofread chapters by scope")
    parser.add_argument("--novel-id", required=True)
    parser.add_argument("--scope", default="chapter", choices=["chapter", "volume", "book"])
    parser.add_argument("--chapter", type=int, default=None)
    parser.add_argument("--volume", type=int, default=None)
    args = parser.parse_args()

    result = run_proofread(
        novel_id=args.novel_id,
        scope=args.scope,
        chapter=args.chapter,
        volume=args.volume,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
