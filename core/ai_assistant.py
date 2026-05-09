#!/usr/bin/env python3
"""
简单的 AI 创作助手
提供创作建议、角色生成、大纲优化等功能
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional


@dataclass
class GenerationRequest:
    prompt: str
    step: str
    context: Dict[str, Any] = field(default_factory=dict)
    temperature: float = 0.7


@dataclass
class GenerationResponse:
    success: bool
    content: str = ""
    suggestions: List[str] = field(default_factory=list)
    error: str = ""


def get_mock_suggestion(step: str, context: Dict[str, Any]) -> str:
    """模拟 AI 生成的建议"""
    
    if step == "concept":
        title = context.get("title", "")
        genre = context.get("genre", "")
        return f"""好的，让我帮你构思一个精彩的 {genre or '小说'} 故事！

关于《{title or '你的小说'}》的概念构思：

✨ 核心主题建议
- 探讨现代社会中个体与集体的关系
- 思考技术发展带来的人性变化
- 寻找传统与创新的平衡点

🎭 故事驱动力
- 主角内心的挣扎与成长
- 不同价值观的碰撞与融合
- 改变命运的关键时刻

建议你从以下角度继续深化：
1. 主角最核心的欲望是什么？
2. 这个故事最想探讨的主题是什么？
3. 读者读完后最应该记住的是什么？

你想先从哪个角度开始深入讨论？"""

    elif step == "outline":
        return """很棒的概念！让我帮你设计故事大纲：

📖 三幕式结构建议

第一幕：铺垫（第1-5章）
- 展示主角的日常生活和状态
- 引入世界观和核心设定
- 铺垫矛盾和伏笔
- 引发改变的触发事件

第二幕：冲突（第6-25章）
- 主角的探索和尝试
- 遇到的困难和障碍
- 人际关系的发展
- 世界观的逐步揭示

第三幕：高潮（第26-35章）
- 所有矛盾汇聚爆发
- 主角面临最终选择
- 高潮事件和结局
- 结尾的收尾和升华

需要我帮你细化某个部分吗？"""

    elif step == "characters":
        return """让我帮你设计角色！

👤 主角设计建议

[主角1]
- 姓名建议：[具体名字]
- 核心性格：[性格描述]
- 背景故事：[身世背景]
- 核心矛盾：内心的冲突
- 成长弧线：从开始到结尾的变化

👥 配角设定
- 导师/助手型角色：帮助主角成长
- 对立/竞争型角色：推动情节发展
- 神秘/引导型角色：揭示世界观

需要我帮你生成某个角色的详细画像吗？"""

    elif step == "world":
        return """让我帮你构建世界观！

🌍 世界观设计建议

1. 地理设定
- 世界的基本格局
- 重要地点和场景
- 环境特色和氛围

2. 社会结构
- 权力体系和组织
- 社会阶层和关系
- 文化和传统

3. 特殊设定
- 独特的世界观元素
- 力量/技术体系
- 世界观历史

4. 关键规则
- 世界观的基本规则
- 对人物和故事的影响
- 与主题的呼应

你想先从哪个部分开始构建？"""

    return """让我们继续完善你的小说创作！

有什么具体想深入讨论的内容吗？我可以帮你：
- 构思情节发展
- 设计人物对话
- 优化场景描写
- 梳理故事逻辑
- 检查伏笔布局

请告诉我你的想法！"""


def generate_suggestion(request: GenerationRequest) -> GenerationResponse:
    """生成创作建议"""
    
    try:
        content = get_mock_suggestion(request.step, request.context)
        
        suggestions = [
            "继续深入讨论这个想法...",
            "让我帮你从另一个角度分析...",
            "需要修改或调整某个部分吗？",
        ]
        
        return GenerationResponse(
            success=True,
            content=content,
            suggestions=suggestions,
        )
        
    except Exception as e:
        return GenerationResponse(
            success=False,
            error=str(e),
        )


# 简单的测试
if __name__ == "__main__":
    req = GenerationRequest(
        prompt="帮我构思故事",
        step="concept",
        context={"title": "测试小说", "genre": "科幻"},
    )
    
    resp = generate_suggestion(req)
    print(json.dumps(asdict(resp), ensure_ascii=False, indent=2))
