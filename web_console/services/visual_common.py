"""视觉相关公共 helper。"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from core.model_router.model_router import ModelRouter, TaskType


def build_generated_media_url(local_path: str) -> str:
    filename = os.path.basename(str(local_path or "").strip())
    if not filename:
        return ""
    return f"/api/v1/media/generated/{quote(filename)}"


def attach_local_url(image: Any) -> Any:
    if not isinstance(image, dict):
        return image
    local_path = str(image.get("local_path") or "").strip()
    if local_path:
        image["local_url"] = build_generated_media_url(local_path)
    return image


def build_prompt_optimizer_client():
    try:
        router = ModelRouter()
        routed = router.route(TaskType.REVIEW, agent_name="reviewer")
        return router.get_client(routed.model_name)
    except Exception:
        return None