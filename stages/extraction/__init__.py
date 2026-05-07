"""
StoryForge - 知识萃取阶段
自动从生成的章节中提取：
1. 新人物
2. 新伏笔
3. 新地点
4. 更新角色状态
5. 记录关键事件
"""

from .knowledge_extractor import KnowledgeExtractor

__all__ = ["KnowledgeExtractor"]
