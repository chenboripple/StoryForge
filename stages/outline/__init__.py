"""
StoryForge - 大纲生成阶段
基于核心设定自动生成：
1. 全书大纲
2. 卷级大纲
3. 章级写作计划
"""

from .outline_generator import OutlineGenerator

__all__ = ["OutlineGenerator"]
