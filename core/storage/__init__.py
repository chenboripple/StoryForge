"""
StoryForge - 存储层（Storage Layer）

负责模型对象与磁盘 JSON 文件之间的映射。

设计原则：
1. 每个模型类型对应一个独立文件（细粒度存储）
2. 增量 IO：只写变更的文件
3. 统一入口：StorageManager 管理所有 IO
4. 向后兼容：支持从旧版单文件迁移
"""
from .base import ModelStorage, StorageConfig
from .manager import StorageManager, get_storage_manager

__all__ = [
    'ModelStorage',
    'StorageConfig',
    'StorageManager',
    'get_storage_manager',
]
