"""
Agent Communication - Agent 通信数据
Agent 间消息、路由建议
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime

from ..base import BaseModel


@dataclass
class AgentMessage(BaseModel):
    """Agent 间消息"""
    sender: str = ""                    # 发送者名称
    msg_type: str = ""                  # 消息类型：issue / suggestion / info / warning / routing_suggestion
    content: str = ""                   # 消息内容
    target: Optional[str] = None        # 目标 Agent（None 表示广播）
    chapter: Optional[int] = None       # 相关章节
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    priority: str = "normal"            # low / normal / high / urgent

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "sender": self.sender,
            "msg_type": self.msg_type,
            "content": self.content,
            "target": self.target,
            "chapter": self.chapter,
            "timestamp": self.timestamp,
            "priority": self.priority,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentMessage":
        """从字典构造"""
        return cls(**data)


@dataclass
class RoutingSuggestion(BaseModel):
    """Agent 路由建议"""
    suggested_by: str = ""              # 建议者
    suggested_node: str = ""            # 建议的 Pipeline 节点
    reason: str = ""
    confidence: float = 0.8
    chapter: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggested_by": self.suggested_by,
            "suggested_node": self.suggested_node,
            "reason": self.reason,
            "confidence": self.confidence,
            "chapter": self.chapter,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoutingSuggestion":
        return cls(**data)
