"""Progressive runtime introspection helpers for v1 routes."""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import HTTPException


def checkpoint_dir() -> Path:
    return Path(".checkpoints")


def latest_checkpoint_for_novel(novel_id: str) -> Path | None:
    pattern = str(checkpoint_dir() / f"pipeline_{novel_id}_ch*.json")
    matches = sorted(glob.glob(pattern))
    if not matches:
        return None
    return Path(matches[-1])


def load_checkpoint(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"无法读取检查点: {exc}") from exc


def get_novel_proposals_payload(novel_id: str) -> Dict[str, Any]:
    ckpt = latest_checkpoint_for_novel(novel_id)
    if not ckpt:
        raise HTTPException(status_code=404, detail=f"未找到小说检查点: {novel_id}")

    payload = load_checkpoint(ckpt)
    proposals: List[Dict[str, Any]] = list(payload.get("proposals", []) or [])
    return {
        "novel_id": novel_id,
        "checkpoint": str(ckpt),
        "count": len(proposals),
        "proposals": proposals,
    }


def get_novel_context_decisions_payload(novel_id: str) -> Dict[str, Any]:
    ckpt = latest_checkpoint_for_novel(novel_id)
    if not ckpt:
        raise HTTPException(status_code=404, detail=f"未找到小说检查点: {novel_id}")

    payload = load_checkpoint(ckpt)
    decisions: List[Dict[str, Any]] = list(payload.get("context_decisions", []) or [])
    return {
        "novel_id": novel_id,
        "checkpoint": str(ckpt),
        "count": len(decisions),
        "context_decisions": decisions,
    }
