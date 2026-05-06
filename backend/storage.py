"""
StoryForge - JSON 文件存储层

负责将 NovelState 对象与磁盘上的 JSON 文件之间互相转换。

存储位置由 .storyforge/storyforge.yaml 中 storage.data_dir 决定。

目录约定：
    <data_dir>/
        index.json          # 小说清单（轻量索引）
        novels/
            <novel_id>.json # 单个小说的完整状态
"""

import json
import os
from typing import List, Optional

# 解决从仓库根目录运行时的 import 问题
import sys
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_THIS_DIR)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from core.state import NovelState  # noqa: E402
from core.config import get_config  # noqa: E402


def _data_dir() -> str:
    """返回当前数据目录（每次调用都从配置读取，便于运行时改配置）。"""
    return get_config().data_dir_abs


def _novels_dir() -> str:
    return os.path.join(_data_dir(), "novels")


def _index_file() -> str:
    return os.path.join(_data_dir(), "index.json")


def _ensure_dirs() -> None:
    """确保存储目录存在"""
    os.makedirs(_novels_dir(), exist_ok=True)


def _novel_path(novel_id: str) -> str:
    if not novel_id or "/" in novel_id or ".." in novel_id:
        raise ValueError(f"非法的 novel_id: {novel_id!r}")
    return os.path.join(_novels_dir(), f"{novel_id}.json")


def save_novel(state: NovelState) -> None:
    """保存单个小说状态到 <data_dir>/novels/<id>.json，并更新索引。"""
    if not state.novel_id:
        raise ValueError("NovelState.novel_id 不能为空")

    _ensure_dirs()
    path = _novel_path(state.novel_id)

    payload = state.to_dict()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    update_novel_index(state)


def load_novel(novel_id: str) -> Optional[NovelState]:
    """加载单个小说状态。不存在则返回 None。"""
    path = _novel_path(novel_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return NovelState.from_dict(data)


def list_novels() -> List[dict]:
    """返回小说清单（来自 index.json）。"""
    index_path = _index_file()
    if not os.path.exists(index_path):
        return []
    with open(index_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []
    return data


def update_novel_index(state: NovelState) -> None:
    """根据 state 更新 index.json 中对应条目（按 novel_id 去重）。"""
    _ensure_dirs()

    entries = list_novels()
    entry = state.to_index_entry()

    found = False
    for i, item in enumerate(entries):
        if item.get("novel_id") == state.novel_id:
            entries[i] = entry
            found = True
            break
    if not found:
        entries.append(entry)

    with open(_index_file(), "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def delete_novel(novel_id: str) -> bool:
    """删除小说（同时从索引移除）。返回是否删除成功。"""
    path = _novel_path(novel_id)
    removed = False
    if os.path.exists(path):
        os.remove(path)
        removed = True

    entries = list_novels()
    new_entries = [e for e in entries if e.get("novel_id") != novel_id]
    if len(new_entries) != len(entries):
        with open(_index_file(), "w", encoding="utf-8") as f:
            json.dump(new_entries, f, ensure_ascii=False, indent=2)
        removed = True

    return removed


def rebuild_index() -> int:
    """扫描 novels/ 目录，重建 index.json。返回重建的条目数。"""
    _ensure_dirs()
    entries = []
    novels_dir = _novels_dir()
    if os.path.isdir(novels_dir):
        for filename in sorted(os.listdir(novels_dir)):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(novels_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                state = NovelState.from_dict(data)
                entries.append(state.to_index_entry())
            except (json.JSONDecodeError, ValueError, TypeError):
                continue

    with open(_index_file(), "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    return len(entries)
