"""通用辅助函数（无业务依赖）。"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Deque, List, Optional

from core.config import get_config
from web_console import security as security_utils


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_name(raw: str) -> str:
    cleaned = re.sub(r"[^\w一-龥\-]+", "_", raw.strip())
    return cleaned.strip("_") or "unknown"


def _tail_logs(logs: Deque[str], offset: int) -> List[str]:
    data = list(logs)
    if offset < 0:
        offset = 0
    return data[offset:]


def _resolve_project_dir(project_dir: Optional[str]) -> str:
    if not project_dir:
        return os.getcwd()
    return os.path.abspath(os.path.expanduser(project_dir.strip()))


def _resolve_debug_output_dir() -> Path:
    cfg = get_config()
    debug_dir = Path(cfg.debug.output_dir).expanduser()
    if debug_dir.is_absolute():
        return debug_dir
    if cfg.config_path:
        return (Path(cfg.config_path).parent / debug_dir).resolve()
    return (Path.cwd() / debug_dir).resolve()


def safe_novel_id(novel_id: str) -> str:
    """兼容导出：委托给 web_console.security.safe_novel_id。"""
    return security_utils.safe_novel_id(novel_id)


def validate_path_safe(base_path: str, target_path: str) -> bool:
    """兼容导出：委托给 web_console.security.validate_path_safe。"""
    return security_utils.validate_path_safe(Path(base_path), Path(target_path))


def safe_join_path(base_path: str, *paths: str) -> str:
    """兼容导出：委托给 web_console.security.safe_join_path。"""
    return str(security_utils.safe_join_path(Path(base_path), *paths))
