"""
StoryForge - Multi-Agent 演示
展示 MessageBus + Agent 自主路由 功能

运行方式:
    python examples/multi_agent_demo.py --agent-routing
    python examples/multi_agent_demo.py --no-agent-routing
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import NovelState, CharacterInfo
from pipeline.novel_pipeline import create_pipeline


def mock_llm(prompt: str, temperature=None):
    """模拟 LLM 客户端（用于演示）"""

    if "审稿" in prompt and "结构化" in prompt:
        # 审稿 Agent 返回结构化 JSON
        return """{
            "total_score": 88,
            "dimensions": [
                {"name": "叙事结构", "score": 85, "comment": "结构清晰"},
                {"name": "人物一致性", "score": 90, "comment": "人物性格稳定"}
            ],
            "issues": [
                {"severity": "B", "location": "第3段", "description": "此处节奏稍慢", "suggestion": "加快节奏"}
            ],
            "verdict": "pass",
            "summary": "整体质量良好，有少量节奏问题",
            "ai_flavor": {"score": 3, "level": "low"}
        }"""

    if "校对" in prompt and "终审" in prompt:
        # 校对 Agent 返回结构化 JSON
        return """{
            "passed": true,
            "issues": [
                {"level": "warning", "category": "typo", "location": "第1段", "description": "细微措辞问题", "fix": "微调"}
            ],
            "summary": "整体质量合格，仅有细微问题",
            "verdict": "可交付"
        }"""

    if "写作" in prompt or "创作" in prompt:
        return '林晚站在观测塔的废墟上，夕阳把钢铁残骸染成血色。\n\n这是末日后的第47天。她还是习惯性望向天际线——那里曾经是城市最繁华的CBD。\n\n"又在发呆？"身后传来脚步声。\n\n林晚没有回头，她知道是谁："你来得正好。我找到信号源了。"\n\n"你确定？"\n\n"不确定。"她转过身，脸上带着一种近乎偏执的冷静，"但至少有方向了。"\n\n两人沉默对视。风从破碎的玻璃幕墙间穿过，发出呜咽般的声音。\n\n"走吧。"她说，"趁天还没黑。"'

    if "修改" in prompt or "编辑意见" in prompt:
        return '林晚站在观测塔的废墟上，血色夕阳正缓缓沉入地平线。\n\n末日后的第47天，她仍望向天际线——那里曾是城市最繁华的CBD，如今只剩扭曲的钢筋和坍塌的混凝土。\n\n"又在发呆？"陈锐的脚步声从身后传来，靴子踩在碎玻璃上发出细碎的声响。\n\n林晚没有回头，指尖攥紧了手中的信号仪："你来得正好。我找到信号源了。"\n\n"你确定？"\n\n"不确定。"她转过身，眼睛里燃着某种偏执的光芒，"但至少有方向了。"\n\n沉默在废墟间蔓延。风穿过破碎的玻璃幕墙，发出空洞的呜咽。\n\n"走吧。"她率先迈步，"趁天还没黑。"'

    if "大纲" in prompt:
        return """{
            "chapter_id": 1,
            "title": "废墟中的信号",
            "scenes": [
                {"scene_id": 1, "description": "林晚在观测塔废墟搜索", "words": 800},
                {"scene_id": 2, "description": "与陈锐汇合，讨论信号源", "words": 700},
                {"scene_id": 3, "description": "决定出发寻找", "words": 500}
            ],
            "foreshadowing": ["信号源的真正含义"],
            "characters": ["林晚", "陈锐"],
            "target_words": 3000
        }"""

    if "知识萃取" in prompt or "extract" in prompt.lower():
        return "提取了3个事件、2个人物、1个伏笔"

    if "IP" in prompt or "story bible" in prompt.lower():
        return "生成了 Story Bible"

    return "这是模拟的 LLM 输出"


def run_demo(use_agent_routing=False):
    """运行 multi-agent 演示"""

    mode_str = "Agent 自主路由" if use_agent_routing else "传统 Pipeline 路由"
    print("=" * 60)
    print(f"  StoryForge Multi-Agent 演示 - {mode_str}")
    print("=" * 60)

    # 创建 Pipeline（启用 MessageBus）
    pipeline = create_pipeline(
        llm_client=mock_llm,
        use_memory=True,
        use_outline_refinement=True,
        use_message_bus=True,
        use_agent_routing=use_agent_routing,
        use_extraction=False,
        use_ip_generation=False,
        checkpoint_dir=".checkpoints_demo"
    )

    # 构建初始状态
    state = NovelState(
        novel_id="demo_multi_agent",
        novel_title="熵塔",
        genre="科幻末日",
        target_word_count=3000,
        current_chapter=1,
        concept="末日后的世界，寻找最后的希望信号",
        outline="""第一卷：信号

末日后的世界，林晚在废墟中发现了一个神秘信号源。
她和同伴陈锐决定出发寻找信号的来源，
途中遭遇各种危险，但也逐渐发现信号背后隐藏的真相...""",
        characters=[
            CharacterInfo(
                name="林晚",
                age=28,
                personality="冷峻、偏执、理性",
                background="理论物理学博士，末日幸存者"
            ),
            CharacterInfo(
                name="陈锐",
                age=32,
                personality="沉稳、内敛",
                background="前军人，末日后成为流浪者"
            )
        ]
    )

    # 运行 Pipeline
    print(f"\n{'=' * 60}")
    result = pipeline.run(state)

    # 打印消息总线日志
    print(f"\n{'=' * 60}")
    print("  Agent 间消息日志")
    print("=" * 60)
    if result.agent_messages:
        for msg in result.agent_messages:
            target_str = f" -> {msg['target']}" if msg['target'] else " (广播)"
            print(f"  [{msg['sender']}] {msg['msg_type']}{target_str}: {msg['content']}")
    else:
        print("  无消息")

    # 打印路由建议
    print(f"\n{'=' * 60}")
    print("  Agent 路由建议")
    print("=" * 60)
    if result.routing_suggestions:
        for suggestion in result.routing_suggestions:
            print(f"  [{suggestion['suggested_by']}] 建议: {suggestion['suggested_node']}")
            print(f"    原因: {suggestion['reason']}")
            print(f"    置信度: {suggestion['confidence']:.2f}")
            print()
    else:
        print("  无路由建议")

    # 打印最终结果
    print(f"{'=' * 60}")
    print("  最终结果")
    print("=" * 60)
    print(f"  章节状态: {result.get_current_chapter_status().value}")
    print(f"  审稿轮次: {result.review_round}")

    if result.reviews.get(1):
        review = result.reviews[1][-1]
        print(f"  最新评分: {review.total_score}分")
        print(f"  是否通过: {'是' if review.passed else '否'}")

    print(f"\n{'=' * 60}")
    if use_agent_routing:
        print("  Agent 自主路由已启用！")
        print("  Reviewer/Proofreader 的路由建议已存入 state")
        print("  Pipeline 路由时会优先参考这些建议")
    else:
        print("  Agent 自主路由未启用（传统模式）")
        print("  路由建议仍会被生成和存储，但 Pipeline 不使用它们")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="StoryForge Multi-Agent 演示")
    parser.add_argument(
        "--agent-routing",
        action="store_true",
        default=False,
        help="启用 Agent 自主路由（默认关闭，渐进式开启）"
    )
    args = parser.parse_args()

    run_demo(use_agent_routing=args.agent_routing)
