"""
兼容层 - Agent 通信模型
新代码请使用: from core.models.agent import AgentMessage, RoutingSuggestion
"""
from __future__ import annotations

from core.models.agent.agent_comm import (
    AgentMessage,
    RoutingSuggestion,
)

__all__ = ["AgentMessage", "RoutingSuggestion"]
