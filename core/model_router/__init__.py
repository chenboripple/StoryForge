"""
StoryForge - 模型路由层

职责：
1. 根据任务类型自动选择最合适的模型
2. 支持模型故障自动切换
3. 统一管理多个 LLM Provider
"""

from .model_router import ModelRouter, TaskType, ModelProvider

__all__ = ["ModelRouter", "TaskType", "ModelProvider"]
