"""Progressive disclosure runtime introspection endpoints (v1)."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from web_console.services.progressive import (
    get_novel_context_decisions_payload,
    get_novel_proposals_payload,
)

router = APIRouter(tags=["progressive"])


@router.get("/novels/{novel_id}/proposals")
async def get_novel_proposals(novel_id: str) -> Dict[str, Any]:
    return get_novel_proposals_payload(novel_id)


@router.get("/novels/{novel_id}/context-decisions")
async def get_novel_context_decisions(novel_id: str) -> Dict[str, Any]:
    return get_novel_context_decisions_payload(novel_id)
