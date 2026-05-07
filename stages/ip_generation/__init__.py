"""
StoryForge - IP 生成阶段
基于已完成的内容生成完整的 IP 资产：
1. 人物 IP 档案（含外貌描述、性格分析、经典语录）
2. 关系图谱
3. 场景设定集
4. 衍生设定（如道具、法术、势力）
"""

from .ip_generator import IPGenerator

__all__ = ["IPGenerator"]
