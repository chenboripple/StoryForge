"""
StoryForge - 存储层（新版格式）

提供与 StorageManager 的简单集成。
"""

import json
import os
from typing import List, Optional, Dict, Any

# 解决从仓库根目录运行时的 import 问题
import sys
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_THIS_DIR)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from core.config import get_config  # noqa: E402
from core.storage import StorageManager, StorageConfig  # noqa: E402


def _get_sm() -> StorageManager:
    """获取存储管理器实例。"""
    config = get_config()
    storage_config = StorageConfig(data_dir=config.data_dir_abs)
    return StorageManager(storage_config)


def list_novels() -> List[Dict[str, Any]]:
    """返回小说清单（来自 index.json）。"""
    return _get_sm().list_novels()


def create_novel(novel_id: str, title: str, genre: str, concept: str, target_word_count: int = 3000):
    """创建新小说。"""
    return _get_sm().create_novel(novel_id, title, genre, concept, target_word_count)


def delete_novel(novel_id: str) -> bool:
    """删除小说。"""
    return _get_sm().delete_novel(novel_id)


def rebuild_index() -> int:
    """重建索引。"""
    return _get_sm().rebuild_index()


def get_storage_manager() -> StorageManager:
    """获取存储管理器（直接使用）。"""
    return _get_sm()


# ===== 向后兼容的接口（用于旧代码过渡） =====

def save_novel(state) -> None:
    """保存小说（仅用于过渡，建议直接使用 StorageManager）。"""
    raise NotImplementedError("请直接使用 StorageManager")


def load_novel(novel_id: str) -> Optional[object]:
    """加载小说（仅用于过渡，建议直接使用 StorageManager）。"""
    raise NotImplementedError("请直接使用 StorageManager")


def update_novel_index(state) -> None:
    """更新索引（仅用于过渡，建议直接使用 StorageManager）。"""
    raise NotImplementedError("请直接使用 StorageManager")
