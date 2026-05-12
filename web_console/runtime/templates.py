"""命令模板存取与白名单校验。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List

from fastapi import HTTPException

from core.config import get_config

_cfg = get_config()
# TODO(A3): 模块顶层 capture，未来切到请求范围 DI。
DEFAULT_COMMAND = _cfg.console.default_command
TEMPLATE_FILE = Path(_cfg.console.template_file_abs)


def _load_templates() -> List[dict]:
    if not TEMPLATE_FILE.exists():
        return []
    try:
        data = json.loads(TEMPLATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _save_templates(templates: List[dict]) -> None:
    TEMPLATE_FILE.write_text(
        json.dumps(templates, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _allowed_commands_for_project(project_dir: str) -> set[str]:
    """返回指定项目目录允许执行的命令集合。"""
    allowed: set[str] = {DEFAULT_COMMAND.strip()}
    normalized_project = os.path.abspath(project_dir)

    for template in _load_templates():
        t_project = os.path.abspath(str(template.get("project_dir") or "").strip())
        t_command = str(template.get("command") or "").strip()
        if t_project == normalized_project and t_command:
            allowed.add(t_command)

    return allowed


def _assert_command_allowed(project_dir: str, command: str) -> None:
    """校验命令是否在白名单中。"""
    normalized_command = command.strip()
    allowed = _allowed_commands_for_project(project_dir)

    if normalized_command in allowed:
        return

    raise HTTPException(
        status_code=400,
        detail=(
            "命令不在白名单中。请使用默认命令，或先在“模板”中保存该命令后再启动。"
        ),
    )
