"""
基础模型类
定义所有模型的公共接口和序列化能力
"""
from abc import ABC
from dataclasses import dataclass, field, asdict, MISSING, fields
from datetime import datetime
from typing import Any, Dict, Optional, Type, TypeVar, get_type_hints, get_origin, get_args, Union
import inspect
import json
from enum import Enum

T = TypeVar('T', bound='BaseModel')


@dataclass
class TimestampMixin:
    """时间戳混入"""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def touch(self):
        """更新时间戳"""
        self.updated_at = datetime.now().isoformat()


class JSONSerializable(ABC):
    """可序列化为 JSON 的接口"""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 JSON 序列化）"""
        raise NotImplementedError

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """从字典构造对象"""
        raise NotImplementedError

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON 字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        """从 JSON 字符串构造对象"""
        return cls.from_dict(json.loads(json_str))


@dataclass
class BaseModel(JSONSerializable, TimestampMixin):
    """所有模型的基类"""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典，处理嵌套的 BaseModel 和枚举"""
        def _convert_value(v):
            if isinstance(v, JSONSerializable):
                return v.to_dict()
            if isinstance(v, list):
                return [_convert_value(item) for item in v]
            if isinstance(v, dict):
                return {k: _convert_value(val) for k, val in v.items()}
            if isinstance(v, Enum):
                return v.value
            return v

        result = {}
        for k, v in asdict(self).items():
            result[k] = _convert_value(v)
        return result

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """
        从字典构造，自动处理嵌套 BaseModel 和枚举。

        子类如果包含复杂的嵌套结构（如 dict[str, Model]），
        可以重写此方法。
        """
        if not isinstance(data, dict):
            return data

        init_kwargs = {}
        type_hints = get_type_hints(cls)

        for field_name in type_hints:
            if field_name not in data:
                continue
            raw_value = data[field_name]
            field_type = type_hints[field_name]
            init_kwargs[field_name] = cls._deserialize_value(raw_value, field_type)

        return cls(**init_kwargs)

    @classmethod
    def _deserialize_value(cls, value, target_type):
        """根据目标类型反序列化单个值"""
        if value is None:
            return None

        # 处理 Union（如 Optional[X]）
        origin = get_origin(target_type)
        if origin is Union:
            args = get_args(target_type)
            # 通常是 Optional[X] = Union[X, None]
            if len(args) == 2 and type(None) in args:
                inner_type = args[0] if args[1] is type(None) else args[1]
                return cls._deserialize_value(value, inner_type)
            return value

        # 处理 List
        if origin is list or origin is list or str(getattr(origin, '__name__', None)) == 'List':
            if not isinstance(value, list):
                return value
            args = get_args(target_type)
            if not args:
                return value
            item_type = args[0]
            return [cls._deserialize_value(item, item_type) for item in value]

        # 处理 Dict
        if origin is dict or origin is dict or str(getattr(origin, '__name__', None)) == 'Dict':
            if not isinstance(value, dict):
                return value
            args = get_args(target_type)
            if len(args) != 2:
                return value
            key_type, val_type = args
            result = {}
            for k, v in value.items():
                # 尝试转换 key
                try:
                    if key_type is int:
                        k = int(k)
                except (ValueError, TypeError):
                    pass
                result[k] = cls._deserialize_value(v, val_type)
            return result

        # 处理枚举
        if isinstance(target_type, type) and issubclass(target_type, Enum):
            if isinstance(value, target_type):
                return value
            try:
                return target_type(value)
            except (ValueError, TypeError):
                return value

        # 处理 BaseModel 子类
        if isinstance(target_type, type) and issubclass(target_type, BaseModel):
            if isinstance(value, dict):
                return target_type.from_dict(value)
            return value

        return value

    def copy(self: T) -> T:
        """深拷贝对象"""
        return self.__class__.from_dict(self.to_dict())
