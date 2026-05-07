"""
StoryForge - 批量生成模块

职责：
1. 支持多章并行生成（无剧情依赖的章节）
2. 支持批量审核
3. 支持批量校对
4. 依赖关系分析和执行顺序调度
"""

from .batch_generator import BatchGenerator, BatchJob, JobStatus

__all__ = ["BatchGenerator", "BatchJob", "JobStatus"]
