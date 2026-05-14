"""AI 辅助生成（创意/概念/章节建议等）。"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.ai_assistant import GenerationRequest, generate_suggestion

router = APIRouter()


class AiGenerateRequest(BaseModel):
    prompt: str = ""
    step: str = "concept"
    context: Dict[str, Any] = Field(default_factory=dict)
    temperature: float = 0.7


@router.post("/ai/generate")
async def ai_generate(req: AiGenerateRequest) -> dict:
    payload = GenerationRequest(
        prompt=req.prompt,
        step=req.step,
        context=req.context,
        temperature=req.temperature,
    )
    resp = generate_suggestion(payload)
    if not resp.success:
        raise HTTPException(status_code=500, detail=resp.error or "生成失败")
    return {
        "success": True,
        "content": resp.content,
        "suggestions": resp.suggestions,
    }
