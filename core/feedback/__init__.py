"""
StoryForge - 人类反馈学习机制

职责：
1. 收集用户对生成内容的修改意见
2. 将反馈转化为 Prompt 优化规则
3. 定期更新模型的系统提示词
"""

from .feedback_learner import FeedbackLearner, FeedbackRecord, PromptRule

__all__ = ["FeedbackLearner", "FeedbackRecord", "PromptRule"]
