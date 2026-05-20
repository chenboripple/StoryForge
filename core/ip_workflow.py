"""IP 生成共享 workflow。"""

from __future__ import annotations

from typing import Iterable, List

from core.models.ip import CharacterIP, StoryBible
from core.storage import StorageManager
from stages.ip_generation.ip_generator import IPGenerator


def generate_story_bible_for_novel(
    sm: StorageManager,
    novel_id: str,
    generator: IPGenerator,
) -> StoryBible:
    meta = sm.load_novel_meta(novel_id)
    if not meta:
        raise RuntimeError(f"未找到小说: {novel_id}")

    chapters = sm.load_chapters(novel_id)
    analyses = sm.load_analyses(novel_id)
    bible = generator.generate(
        title=meta.novel_title if meta else novel_id,
        chapters=chapters,
        chapter_analyses=analyses,
    )
    sm.save_story_bible(novel_id, bible)
    return bible


def select_story_bible_characters(bible: StoryBible, character_ids: Iterable[str]) -> List[CharacterIP]:
    ids = [str(x or "").strip() for x in character_ids if str(x or "").strip()]
    if not ids:
        return list(bible.characters or [])

    selected: List[CharacterIP] = []
    seen = set()
    for cid in ids:
        char = bible.get_character(cid) or bible.get_character_by_name(cid)
        if not char:
            continue
        key = char.character_id or char.name
        if not key or key in seen:
            continue
        selected.append(char)
        seen.add(key)
    return selected


def build_character_ip_payload(novel_id: str, novel_title: str, char_ip: CharacterIP, generated_at: str) -> dict:
    evidence = [
        {
            "chapter": str(item.get("chapter") or ""),
            "quote": str(item.get("description") or "").strip()[:200],
        }
        for item in (char_ip.key_scenes or [])
        if isinstance(item, dict) and (item.get("chapter") or item.get("description"))
    ]

    tags = ", ".join([str(x).strip() for x in (char_ip.tags or []) if str(x).strip()][:6])
    role = str(char_ip.role or "supporting")
    background = str(char_ip.background or "").strip()
    summary_parts = [f"角色 {char_ip.name or char_ip.character_id} 的定位是 {role}。"]
    if background:
        summary_parts.append(background[:180])
    if tags:
        summary_parts.append(f"标签：{tags}。")

    return {
        "novel_id": novel_id,
        "novel_title": novel_title,
        "character_id": char_ip.character_id,
        "character_name": char_ip.name or char_ip.character_id,
        "generated_at": generated_at,
        "summary": " ".join(summary_parts).strip(),
        "evidence": evidence,
        "version": generated_at,
        "story_bible_character": char_ip.to_dict(),
    }