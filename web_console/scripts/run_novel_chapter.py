"""Run one chapter generation for a stored novel."""

from __future__ import annotations

import argparse
from datetime import datetime

from core.config import get_config
from core.llm_factory import create_llm_client
from core.models import Chapter, ChapterStatus, PipelineStage, Proofread, ProofreadRecord, Review, ReviewRecord
from core.state import CharacterInfo, NovelState
from core.storage import StorageConfig, StorageManager
from pipeline.novel_pipeline import create_pipeline


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


def _extract_text(chapter_obj) -> str:
    if chapter_obj is None:
        return ""
    if hasattr(chapter_obj, "text"):
        return str(getattr(chapter_obj, "text") or "")
    return str(chapter_obj)


def _persist_result(sm: StorageManager, state: NovelState, chapter_num: int) -> None:
    text = _extract_text(state.chapters.get(chapter_num))

    chapters = sm.load_chapters(state.novel_id)
    chapters[chapter_num] = Chapter(
        novel_id=state.novel_id,
        chapter_num=chapter_num,
        title=f"第{chapter_num}章",
        content=text,
        status=state.chapter_status.get(chapter_num, ChapterStatus.DRAFT),
        word_count=len(text),
        generated_by="writer",
        review_round=max(0, int(state.review_round or 0)),
        updated_at=datetime.now().isoformat(),
    )
    sm.save_chapters(state.novel_id, chapters)

    reviews_src = list(state.structured_reviews.get(chapter_num) or [])
    if reviews_src:
        review = Review(novel_id=state.novel_id, chapter_num=chapter_num)
        for idx, item in enumerate(reviews_src, start=1):
            review.add_record(
                ReviewRecord(
                    novel_id=state.novel_id,
                    chapter_num=chapter_num,
                    round=idx,
                    reviewer="青锋",
                    total_score=int(getattr(item, "total_score", 0) or 0),
                    dimensions=list(getattr(item, "dimensions", []) or []),
                    issues=list(getattr(item, "issues", []) or []),
                    verdict=getattr(item, "verdict", None),
                    summary=str(getattr(item, "summary", "") or ""),
                    passed=bool(str(getattr(item, "verdict", "")).lower().endswith("pass")),
                    timestamp=datetime.now().isoformat(),
                )
            )
        reviews = sm.load_reviews(state.novel_id)
        reviews[chapter_num] = review
        sm.save_reviews(state.novel_id, reviews)

    proof_src = list(state.proofread_results.get(chapter_num) or [])
    if proof_src:
        proofread = Proofread(novel_id=state.novel_id, chapter_num=chapter_num)
        for idx, item in enumerate(proof_src, start=1):
            proofread.add_record(
                ProofreadRecord(
                    novel_id=state.novel_id,
                    chapter_num=chapter_num,
                    round=idx,
                    proofreader="砚清",
                    issues=list(getattr(item, "issues", []) or []),
                    passed=bool(getattr(item, "passed", False)),
                    summary=str(getattr(item, "summary", "") or ""),
                    timestamp=datetime.now().isoformat(),
                )
            )
        proofreads = sm.load_proofreads(state.novel_id)
        proofreads[chapter_num] = proofread
        sm.save_proofreads(state.novel_id, proofreads)

    meta = sm.load_novel_meta(state.novel_id)
    if meta:
        meta.current_stage = PipelineStage.CREATION
        meta.current_chapter = max(int(meta.current_chapter or 1), chapter_num + 1)
        meta.total_chapters = max(int(meta.total_chapters or 0), chapter_num)
        approved = sum(1 for ch in chapters.values() if ch.status == ChapterStatus.APPROVED)
        meta.approved_chapters = approved
        sm.save_novel_meta(state.novel_id, meta)


def run_once(novel_id: str, chapter: int) -> None:
    sm = _new_storage_manager()
    meta = sm.load_novel_meta(novel_id)
    if not meta:
        raise ValueError(f"novel not found: {novel_id}")

    outline = sm.load_outline(novel_id)

    initial_state = NovelState(
        novel_id=novel_id,
        novel_title=meta.novel_title,
        genre=meta.genre,
        concept=meta.concept,
        outline=(outline.overall_outline if outline else "") or meta.concept,
        target_word_count=meta.target_word_count,
        current_stage=PipelineStage.CREATION,
        current_chapter=chapter,
        max_review_rounds=get_config().pipeline.max_review_rounds,
        characters=_to_character_infos(sm, novel_id),
    )

    llm_client = create_llm_client(get_config().llm)
    pipeline = create_pipeline(llm_client=llm_client)
    result = pipeline.run(initial_state)
    _persist_result(sm, result, chapter)

def main() -> int:
    parser = argparse.ArgumentParser(description="Run one chapter generation for a novel")
    parser.add_argument("--novel-id", required=True)
    parser.add_argument("--chapter", type=int, required=True)
    args = parser.parse_args()

    if args.chapter <= 0:
        raise ValueError("chapter must be > 0")

    run_once(novel_id=args.novel_id, chapter=args.chapter)
    print(f"done: novel={args.novel_id}, chapter={args.chapter}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
