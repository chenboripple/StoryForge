"""命令模板（保存/列出）。"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from web_console.runtime.templates import _load_templates, _save_templates

router = APIRouter()


class SaveTemplateRequest(BaseModel):
    name: str
    project_dir: str
    command: str


@router.get("/templates")
async def list_templates() -> dict:
    return {"templates": _load_templates()}


@router.post("/templates")
async def save_template(req: SaveTemplateRequest) -> dict:
    item = {
        "name": req.name.strip(),
        "project_dir": os.path.abspath(req.project_dir.strip()),
        "command": req.command.strip(),
    }
    if not item["name"] or not item["project_dir"] or not item["command"]:
        raise HTTPException(status_code=400, detail="模板字段不能为空")

    templates = _load_templates()
    replaced = False
    for i, t in enumerate(templates):
        if t.get("name") == item["name"]:
            templates[i] = item
            replaced = True
            break
    if not replaced:
        templates.append(item)

    _save_templates(templates)
    return {"ok": True, "template": item}
