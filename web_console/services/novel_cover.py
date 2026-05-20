"""小说封面服务：读取/生成/保存封面资料。"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

from agents.character_visual_agent import CharacterVisualAgent
from core.storage import StorageManager
from web_console.utils import _now
from web_console.services.visual_common import attach_local_url, build_prompt_optimizer_client
from web_console.services.visual_prompting import generate_cover_prompt

COVER_FILENAME = "novel_cover.json"


def _cover_path(sm: StorageManager, novel_id: str) -> str:
    return sm.config.path_for(novel_id, COVER_FILENAME)


def _empty_cover(novel_id: str, novel_title: str) -> Dict[str, Any]:
    return {
        "novel_id": novel_id,
        "novel_title": novel_title,
        "cover_image": None,
        "created_at": _now(),
        "updated_at": _now(),
        "history": [],
    }


def get_novel_cover(sm: StorageManager, novel_id: str) -> Dict[str, Any]:
    meta = sm.load_novel_meta(novel_id)
    novel_title = meta.novel_title if meta else novel_id

    path = _cover_path(sm, novel_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                data["cover_image"] = attach_local_url(data.get("cover_image"))
                return data
    except FileNotFoundError:
        pass
    except Exception:
        pass

    return _empty_cover(novel_id, novel_title)


def generate_novel_cover(
    sm: StorageManager,
    novel_id: str,
    prompt: str,
    style: str = "",
    image_preset: str = "720p",
    aspect_ratio: str = "16:9",
) -> Dict[str, Any]:
    meta = sm.load_novel_meta(novel_id)
    if meta is None:
        raise ValueError(f"novel not found: {novel_id}")

    cover = get_novel_cover(sm, novel_id)
    novel_title = meta.novel_title or novel_id
    prompt_client = build_prompt_optimizer_client()
    final_prompt = generate_cover_prompt(
        sm=sm,
        novel_id=novel_id,
        user_prompt=prompt,
        style=style,
        llm_client=prompt_client,
    )

    agent = CharacterVisualAgent(llm_client=prompt_client)
    generated = agent.invoke(
        {
            "novel_id": novel_id,
            "character_id": "__novel_cover__",
            "character_name": novel_title,
            "slot_type": "main",
            "prompt": final_prompt,
            "style": style,
            "image_preset": image_preset,
            "aspect_ratio": aspect_ratio,
        }
    )

    cover["novel_title"] = novel_title
    cover["cover_image"] = attach_local_url(generated)
    cover["updated_at"] = _now()
    cover.setdefault("history", []).append(
        {
            "action": "generate_cover",
            "prompt": final_prompt,
            "style": style,
            "image_preset": image_preset,
            "aspect_ratio": aspect_ratio,
            "generated_id": generated.get("id"),
            "at": _now(),
        }
    )

    os.makedirs(sm.config.novel_dir(novel_id), exist_ok=True)
    with open(_cover_path(sm, novel_id), "w", encoding="utf-8") as f:
        json.dump(cover, f, ensure_ascii=False, indent=2)

    return {
        "novel_id": novel_id,
        "cover_image": generated,
        "cover": cover,
    }
