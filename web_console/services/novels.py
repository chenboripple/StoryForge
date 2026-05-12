"""小说快照发现与文本切片。"""

from __future__ import annotations

import json
import re
from typing import List

from core.storage import StorageManager


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
