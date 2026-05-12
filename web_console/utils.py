"""通用辅助函数（无业务依赖）。"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Deque, List, Optional

from core.config import get_config


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


# 路径安全相关工具
SAFE_NOVEL_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
MAX_NOVEL_ID_LENGTH = 100


def safe_novel_id(novel_id: str) -> str:
    """
    清洗并验证小说 ID，防止路径遍历攻击。

    Args:
        novel_id: 原始小说 ID

    Returns:
        清洗后的安全小说 ID

    Raises:
        ValueError: 如果小说 ID 不安全或无效
    """
    if not novel_id or not isinstance(novel_id, str):
        raise ValueError("小说 ID 不能为空")

    # 移除任何路径分隔符
    cleaned = novel_id.strip()
    cleaned = cleaned.replace("/", "_")
    cleaned = cleaned.replace("\\", "_")
    cleaned = cleaned.replace("..", "_")

    # 如果结果为空，生成一个安全的 ID
    if not cleaned:
        from datetime import datetime

        cleaned = f"novel_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 验证长度
    if len(cleaned) > MAX_NOVEL_ID_LENGTH:
        cleaned = cleaned[:MAX_NOVEL_ID_LENGTH]

    # 最终安全检查 - 确保只包含安全字符
    if not SAFE_NOVEL_ID_PATTERN.match(cleaned):
        # 替换所有不安全字符
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", cleaned)

    return cleaned


def validate_path_safe(base_path: str, target_path: str) -> bool:
    """
    验证目标路径是否在基础路径内，防止路径遍历。

    Args:
        base_path: 基础路径（允许的根目录）
        target_path: 目标路径（需要验证的路径）

    Returns:
        True 如果路径安全，否则 False
    """
    base_path = os.path.abspath(base_path)
    target_path = os.path.abspath(target_path)

    # 确保目标路径是基础路径的子路径
    common = os.path.commonpath([base_path, target_path])
    return common == base_path


def safe_join_path(base_path: str, *paths: str) -> str:
    """
    安全地拼接路径，确保结果在基础路径内。

    Args:
        base_path: 基础路径
        *paths: 要拼接的路径部分

    Returns:
        安全拼接后的路径

    Raises:
        ValueError: 如果结果路径超出基础路径
    """
    joined = os.path.abspath(os.path.join(base_path, *paths))
    if not validate_path_safe(base_path, joined):
        raise ValueError(f"路径不安全: {joined}")
    return joined
