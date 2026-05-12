"""
Storage Base - 存储基类

提供通用的 JSON 文件读写能力。
"""
import json
import os
import re
from typing import TypeVar, Type, Optional, Any
from dataclasses import dataclass

from core.models.base import BaseModel

T = TypeVar('T', bound='BaseModel')

# 安全验证相关
SAFE_NOVEL_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
MAX_NOVEL_ID_LENGTH = 100


def _safe_novel_id(novel_id: str) -> str:
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


def _validate_path_safe(base_path: str, target_path: str) -> bool:
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


@dataclass
class StorageConfig:
    """存储配置"""
    data_dir: str = ""
    indent: int = 2
    encoding: str = "utf-8"
    ensure_ascii: bool = False

    @property
    def novels_dir(self) -> str:
        return os.path.join(self.data_dir, "novels")

    def novel_dir(self, novel_id: str) -> str:
        """单个小说的目录（分文件存储时）"""
        safe_id = _safe_novel_id(novel_id)
        return os.path.join(self.novels_dir, safe_id)

    @property
    def index_file(self) -> str:
        return os.path.join(self.data_dir, "index.json")

    def path_for(self, novel_id: str, filename: str) -> str:
        """
        获取某个小说下某个文件的完整路径（安全版本）

        Args:
            novel_id: 小说 ID（会被清洗）
            filename: 文件名（不能包含路径分隔符）

        Returns:
            安全的文件路径

        Raises:
            ValueError: 如果文件名包含路径分隔符
        """
        # 验证文件名不包含路径分隔符
        if "/" in filename or "\\" in filename or ".." in filename:
            raise ValueError(f"文件名不能包含路径分隔符: {filename}")

        safe_id = _safe_novel_id(novel_id)
        novel_dir = os.path.join(self.novels_dir, safe_id)
        full_path = os.path.abspath(os.path.join(novel_dir, filename))

        # 验证最终路径在小说目录内
        if not _validate_path_safe(novel_dir, full_path):
            raise ValueError(f"路径不安全: {filename}")

        return full_path


class ModelStorage:
    """
    单个模型类型的存储器

    负责读写一类模型到独立 JSON 文件。
    例如：ChapterStorage 管理 chapters/<num>.json
    """

    def __init__(self, config: StorageConfig, model_class: Type[T], filename: str):
        self.config = config
        self.model_class = model_class
        self.filename = filename

    def _path(self, novel_id: str) -> str:
        return self.config.path_for(novel_id, self.filename)

    def _ensure_dir(self, novel_id: str):
        novel_dir = self.config.novel_dir(novel_id)
        os.makedirs(novel_dir, exist_ok=True)

    def save(self, novel_id: str, model: T):
        """保存模型到文件"""
        self._ensure_dir(novel_id)
        path = self._path(novel_id)
        with open(path, "w", encoding=self.config.encoding) as f:
            json.dump(
                model.to_dict(),
                f,
                ensure_ascii=self.config.ensure_ascii,
                indent=self.config.indent,
            )

    def load(self, novel_id: str) -> Optional[T]:
        """从文件加载模型"""
        path = self._path(novel_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding=self.config.encoding) as f:
            data = json.load(f)
        return self.model_class.from_dict(data)

    def exists(self, novel_id: str) -> bool:
        """检查文件是否存在"""
        return os.path.exists(self._path(novel_id))

    def delete(self, novel_id: str) -> bool:
        """删除文件，返回是否成功删除"""
        path = self._path(novel_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False


class ListModelStorage(ModelStorage):
    """
    列表型模型的存储器
    例如：List[Chapter], List[ReviewRecord]
    """

    def __init__(self, config: StorageConfig, item_class: Type[T], filename: str):
        super().__init__(config, item_class, filename)
        self.item_class = item_class

    def save_list(self, novel_id: str, items: list):
        """保存列表"""
        self._ensure_dir(novel_id)
        path = self._path(novel_id)
        with open(path, "w", encoding=self.config.encoding) as f:
            json.dump(
                [item.to_dict() for item in items],
                f,
                ensure_ascii=self.config.ensure_ascii,
                indent=self.config.indent,
            )

    def load_list(self, novel_id: str) -> list:
        """加载列表"""
        path = self._path(novel_id)
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding=self.config.encoding) as f:
            data = json.load(f)
        return [self.item_class.from_dict(item) for item in data]


class DictModelStorage(ModelStorage):
    """
    字典型模型的存储器（key -> model）
    例如：Dict[int, Chapter], Dict[str, Character]
    """

    def __init__(self, config: StorageConfig, item_class: Type[T], filename: str):
        super().__init__(config, item_class, filename)
        self.item_class = item_class

    def save_dict(self, novel_id: str, items: dict):
        """保存字典"""
        self._ensure_dir(novel_id)
        path = self._path(novel_id)
        # 序列化时保持 key 为字符串（JSON 要求）
        payload = {}
        for k, v in items.items():
            payload[str(k)] = v.to_dict()
        with open(path, "w", encoding=self.config.encoding) as f:
            json.dump(payload, f, ensure_ascii=self.config.ensure_ascii, indent=self.config.indent)

    def load_dict(self, novel_id: str) -> dict:
        """加载字典"""
        path = self._path(novel_id)
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding=self.config.encoding) as f:
            data = json.load(f)
        result = {}
        for k, v in data.items():
            # 尝试将 key 转回 int（如果看起来像数字）
            try:
                key = int(k)
            except ValueError:
                key = k
            result[key] = self.item_class.from_dict(v)
        return result
