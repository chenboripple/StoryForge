"""安全相关工具函数。"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional, List, Set, Tuple

from core.config import (
    ALLOWED_UPLOAD_TYPES,
    DEFAULT_MAX_UPLOAD_SIZE,
    get_config,
)


# -----------------------------------------------------------------------------
# 路径安全
# -----------------------------------------------------------------------------

SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
MAX_ID_LENGTH = 100


def safe_novel_id(novel_id: str) -> str:
    """清洗并验证小说ID，防止路径遍历攻击。

    Args:
        novel_id: 原始小说ID

    Returns:
        清洗后的安全小说ID

    Raises:
        ValueError: 如果小说ID无效
    """
    if not novel_id or not isinstance(novel_id, str):
        raise ValueError("小说ID不能为空")

    # 移除任何路径分隔符
    cleaned = novel_id.strip()
    cleaned = cleaned.replace("/", "_")
    cleaned = cleaned.replace("\\", "_")
    cleaned = cleaned.replace("..", "_")

    # 如果结果为空，生成一个安全的ID
    if not cleaned:
        from datetime import datetime
        cleaned = f"novel_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 验证长度
    if len(cleaned) > MAX_ID_LENGTH:
        cleaned = cleaned[:MAX_ID_LENGTH]

    # 最终安全检查 - 确保只包含安全字符
    if not SAFE_ID_PATTERN.match(cleaned):
        cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", cleaned)

    return cleaned


def validate_path_safe(base_path: Path, target_path: Path) -> bool:
    """验证目标路径在基础路径内，防止路径遍历。

    Args:
        base_path: 允许的根目录
        target_path: 需要验证的路径

    Returns:
        True如果路径安全
    """
    base_path = base_path.resolve()
    target_path = target_path.resolve()

    # 确保目标路径是基础路径的子路径
    try:
        target_path.relative_to(base_path)
        return True
    except ValueError:
        return False


def safe_join_path(base_path: Path, *paths: str) -> Path:
    """安全拼接路径，确保结果在基础路径内。

    Args:
        base_path: 基础路径
        *paths: 需要拼接的路径部分

    Returns:
        安全拼接后的路径

    Raises:
        ValueError: 如果结果路径超出基础路径
    """
    joined = (base_path / Path(*paths)).resolve()
    if not validate_path_safe(base_path, joined):
        raise ValueError(f"路径不安全: {'/'.join(paths)}")
    return joined


# -----------------------------------------------------------------------------
# 文件上传安全
# -----------------------------------------------------------------------------


def get_allowed_extensions(upload_type: Optional[str] = None) -> List[str]:
    """获取允许的文件扩展名列表。

    Args:
        upload_type: 上传类型（text/epub/pdf/image），None表示所有类型

    Returns:
        允许的扩展名列表（小写，带点）
    """
    cfg = get_config()
    if cfg.security.allowed_upload_extensions:
        return [ext.lower() for ext in cfg.security.allowed_upload_extensions]

    if upload_type is None:
        # 返回所有类型
        all_exts = []
        for exts in ALLOWED_UPLOAD_TYPES.values():
            all_exts.extend(exts)
        return list(set(all_exts))

    return ALLOWED_UPLOAD_TYPES.get(upload_type, [])


def validate_file_extension(filename: str, upload_type: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """验证文件扩展名是否允许。

    Args:
        filename: 文件名
        upload_type: 上传类型（可选）

    Returns:
        (是否允许, 扩展名)
    """
    _, ext = os.path.splitext(filename.lower())
    allowed = get_allowed_extensions(upload_type)
    return (ext in allowed if allowed else True), ext


def validate_file_size(size: int) -> bool:
    """验证文件大小是否在限制范围内。

    Args:
        size: 文件大小（字节）

    Returns:
        True如果大小允许
    """
    cfg = get_config()
    max_size = cfg.security.max_upload_size or DEFAULT_MAX_UPLOAD_SIZE
    return size <= max_size


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除危险字符。

    Args:
        filename: 原始文件名

    Returns:
        安全的文件名
    """
    # 移除路径部分
    filename = os.path.basename(filename)

    # 移除或替换危险字符
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)

    # 移除控制字符
    filename = re.sub(r'[\x00-\x1F\x7F]', "", filename)

    # 确保非空
    if not filename or filename == ".":
        filename = "unnamed_file"

    return filename


def get_upload_type(filename: str) -> Optional[str]:
    """根据文件名判断上传类型。

    Args:
        filename: 文件名

    Returns:
        上传类型（text/epub/pdf/image）或None
    """
    _, ext = os.path.splitext(filename.lower())
    for upload_type, extensions in ALLOWED_UPLOAD_TYPES.items():
        if ext in extensions:
            return upload_type
    return None
