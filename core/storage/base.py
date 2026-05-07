"""
Storage Base - 存储基类

提供通用的 JSON 文件读写能力。
"""
import json
import os
from typing import TypeVar, Type, Optional, Any
from dataclasses import dataclass

from core.models.base import BaseModel

T = TypeVar('T', bound=BaseModel)


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
        return os.path.join(self.novels_dir, novel_id)

    @property
    def index_file(self) -> str:
        return os.path.join(self.data_dir, "index.json")

    def path_for(self, novel_id: str, filename: str) -> str:
        """获取某个小说下某个文件的完整路径"""
        return os.path.join(self.novel_dir(novel_id), filename)


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
                indent=self.config.indent
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
                indent=self.config.indent
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
