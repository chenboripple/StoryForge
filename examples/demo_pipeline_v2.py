"""
StoryForge - V2 示例：运行重构后的 Pipeline
改进点：
1. 使用结构化输出（JSON）
2. 展示记忆系统
3. 错误处理
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import NovelState, CharacterInfo
from pipeline.novel_pipeline_v2 import create_pipeline_v2
from core.memory import StoryMemory


def mock_llm_json(prompt: str, temperature: float = None) -> str:
    """
    Mock LLM - 模拟结构化输出
    """
    import json
    
    # 先判断任务类型，看 prompt 的后半部分
    if "审稿" in prompt or "维度评分" in prompt:
        return json.dumps({
            "total_score": 88,
            "dimensions": [
                {"name": "叙事结构", "score": 90, "weight": 0.3, "comment": "开头即冲突，节奏紧凑"},
                {"name": "人物一致性", "score": 85, "weight": 0.3, "comment": "林晚果断、陈默冷峻，性格鲜明"},
                {"name": "文学性", "score": 88, "weight": 0.3, "comment": "细节到位（92式手枪、血红色天空）"},
                {"name": "市场潜力", "score": 90, "weight": 0.1, "comment": "末日+悬疑，有爆款潜质"}
            ],
            "issues": [
                {"severity": "improvement", "location": "第3段", "description": "'血红色的天空'出现两次", "suggestion": "第二次可改为'猩红色的天幕'"},
                {"severity": "improvement", "location": "第15段", "description": "R-07协议揭示可以更震撼", "suggestion": "增加林晚的生理反应（如耳鸣、眩晕）"},
                {"severity": "highlight", "location": "第7段", "description": "'如果这个词在末日还有意义'——金句", "suggestion": "保持"}
            ],
            "verdict": "pass",
            "summary": "整体质量优秀，人物鲜明，冲突强烈。两个小优化建议，不影响通过。"
        }, ensure_ascii=False)
    
    elif "最终校对" in prompt or "检查错别字" in prompt or "一致性问题" in prompt:
        return json.dumps({
            "passed": True,
            "issues": [],
            "summary": "无错误，通过。"
        }, ensure_ascii=False)
    
    elif "修改" in prompt or "审稿意见" in prompt:
        return """
林晚站在观测塔的废墟上，夜风裹挟着辐射尘拍打她的面罩。面罩上凝结的水珠被吹成一道道细线，像泪痕。

三小时前，这里还是"新上海"最高的建筑。现在，它只是一根断裂的钢筋，指向被晚霞浸透的天空——那种红不是夕阳的红，是辐射云特有的、令人不安的猩红。

"第7次了。"她低声说，声音在头盔里产生轻微的回音，像在对另一个自己说话。

身后传来脚步声。不用回头，她知道是谁——在这个半径500米的废墟里，只有两个人还站着。

"你早就知道会这样。"陈默的声音比辐射尘还冷。

林晚转过身。她的前男友——如果这个词在末日还有意义——正用枪指着她。不是那种制式的电磁枪，是一把老旧的92式，枪身刻着"公安"两个字，来自一百年前的博物馆。枪管上有锈迹，但撞针肯定是好的。

"我知道的是，"林晚缓缓举起双手，动作很慢，让陈默能看清她每个指节，"如果我不按下那个按钮，死的人会多一百倍。"

"但你按了。"

"我按了。"

陈默的手指扣在扳机上。林晚注意到他在颤抖——不是害怕，是愤怒。那种被背叛的愤怒，她在三天前的自己身上也见过，当时她站在同样的位置，用同样的姿势举着枪。

"R-07协议，"陈默说，"你父亲签的字。"

林晚的瞳孔收缩。这是她第一次听到这个代号。她感觉后颈的汗毛竖了起来，不是因为风。

"什么？"

"别装了。"陈默从口袋里掏出一个数据芯片，金属外壳上有一道明显的划痕，"观测塔地下三层，冷冻舱里躺着的那些人——你以为他们是志愿者？"

风突然停了。猩红色的天空下，两个持枪的人，一个比末日更冷的秘密。林晚注意到陈默的枪口垂下了半寸——不是因为她的话，是因为他也在害怕那个答案。

林晚放下手。

"带我去。"她说。

"凭什么？"

"凭我知道冷冻舱的供电密码。"林晚露出一个疲惫的笑，嘴角扯动面罩的边缘，"而且凭你不敢开枪。你从来不敢。"

陈默的枪口又垂下了半寸。

这是他今天第二次输给她。也许也是这辈子最后一次赢的机会。
"""
    
    elif "创作" in prompt or "写作" in prompt:
        return """
林晚站在观测塔的废墟上，夜风裹挟着辐射尘拍打她的面罩。

三小时前，这里还是"新上海"最高的建筑。现在，它只是一根断裂的钢筋，指向血红色的天空。

"第7次了。"她低声说，声音在头盔里产生轻微的回音。

身后传来脚步声。不用回头，她知道是谁——在这个半径500米的废墟里，只有两个人还站着。

"你早就知道会这样。"陈默的声音比辐射尘还冷。

林晚转过身。她的前男友——如果这个词在末日还有意义——正用枪指着她。不是那种制式的电磁枪，是一把老旧的92式，枪身刻着"公安"两个字，来自一百年前的博物馆。

"我知道的是，"林晚缓缓举起双手，"如果我不按下那个按钮，死的人会多一百倍。"

"但你按了。"

"我按了。"

陈默的手指扣在扳机上。林晚注意到他在颤抖——不是害怕，是愤怒。那种被背叛的愤怒，她在三天前的自己身上也见过。

"R-07协议，"陈默说，"你父亲签的字。"

林晚的瞳孔收缩。这是她第一次听到这个代号。

"什么？"

"别装了。"陈默从口袋里掏出一个数据芯片，"观测塔地下三层，冷冻舱里躺着的那些人——你以为他们是志愿者？"

夜风突然停了。血红色的天空下，两个持枪的人，一个比末日更冷的秘密。

林晚放下手。

"带我去。"她说。

"凭什么？"

"凭我知道冷冻舱的供电密码。"林晚露出一个疲惫的笑，"而且凭你不敢开枪。"

陈默的枪口垂下了半寸。

这是他今天第二次输给她。
"""
    
    else:
        # 默认返回创作内容（用于 writer 节点）
        return """
林晚站在观测塔的废墟上，夜风裹挟着辐射尘拍打她的面罩。

三小时前，这里还是"新上海"最高的建筑。现在，它只是一根断裂的钢筋，指向血红色的天空。

"第7次了。"她低声说，声音在头盔里产生轻微的回音。

身后传来脚步声。不用回头，她知道是谁——在这个半径500米的废墟里，只有两个人还站着。

"你早就知道会这样。"陈默的声音比辐射尘还冷。

林晚转过身。她的前男友——如果这个词在末日还有意义——正用枪指着她。不是那种制式的电磁枪，是一把老旧的92式，枪身刻着"公安"两个字，来自一百年前的博物馆。

"我知道的是，"林晚缓缓举起双手，"如果我不按下那个按钮，死的人会多一百倍。"

"但你按了。"

"我按了。"

陈默的手指扣在扳机上。林晚注意到他在颤抖——不是害怕，是愤怒。那种被背叛的愤怒，她在三天前的自己身上也见过。

"R-07协议，"陈默说，"你父亲签的字。"

林晚的瞳孔收缩。这是她第一次听到这个代号。

"什么？"

"别装了。"陈默从口袋里掏出一个数据芯片，"观测塔地下三层，冷冻舱里躺着的那些人——你以为他们是志愿者？"

夜风突然停了。血红色的天空下，两个持枪的人，一个比末日更冷的秘密。

林晚放下手。

"带我去。"她说。

"凭什么？"

"凭我知道冷冻舱的供电密码。"林晚露出一个疲惫的笑，"而且凭你不敢开枪。"

陈默的枪口垂下了半寸。

这是他今天第二次输给她。
"""


def main():
    """运行 V2 示例"""
    
    print("=" * 60)
    print("StoryForge Pipeline V2 - 演示")
    print("=" * 60)
    
    # 1. 准备初始状态
    state = NovelState(
        novel_id="demo_002",
        novel_title="熵塔",
        genre="科幻末日",
        target_word_count=3000,
        current_chapter=1,
        concept="末日后的世界，主角发现父亲参与的禁忌实验",
        outline="""
第一卷：崩塌
第1章：观测塔废墟 - 林晚和陈默的相遇，R-07协议的首次提及
第2章：地下三层 - 发现冷冻舱，真相初现
第3章：逃亡 - 组织追杀，两人被迫合作
...""",
        characters=[
            CharacterInfo(
                name="林晚",
                age=28,
                appearance="短发，面罩下有一道旧伤疤，眼神疲惫但锐利",
                personality="理性、果断、内心有负罪感",
                background="前物理学家，因实验事故转行遗迹探索者",
                goals=["找到父亲死亡的真相", "赎清自己的罪"],
                relationships={"陈默": "前男友，因误会分手"}
            ),
            CharacterInfo(
                name="陈默",
                age=30,
                appearance="高瘦，总是穿旧款风衣，右手有烧伤疤痕",
                personality="冷峻、偏执、对背叛零容忍",
                background="前安全局特工，因任务失败被除名",
                goals=["揭露R-07协议的真相", "为死去的同事报仇"],
                relationships={"林晚": "前女友，复杂的感情"}
            )
        ]
    )
    
    # 2. 创建 Pipeline V2（启用记忆系统）
    pipeline = create_pipeline_v2(
        llm_client=mock_llm_json,
        use_memory=True
    )
    
    # 3. 可视化
    print("\n" + "=" * 60)
    print("Pipeline 图结构（Mermaid 语法）：")
    print("=" * 60)
    print(pipeline.visualize())
    
    # 4. 执行
    print("\n" + "=" * 60)
    print("开始执行 Pipeline V2")
    print("=" * 60)
    
    result = pipeline.run(state)
    
    # 5. 查看结果
    print("\n" + "=" * 60)
    print("最终结果")
    print("=" * 60)
    print(f"章节状态：{result.chapter_status.get(1)}")
    print(f"审稿轮次：{result.review_round}")
    print(f"最终阶段：{result.current_stage.value}")
    
    # 6. 查看记忆系统
    if pipeline.memory:
        print("\n" + "=" * 60)
        print("记忆系统状态")
        print("=" * 60)
        memory_dict = pipeline.memory.to_dict()
        print(f"记录事件数：{len(memory_dict['events'])}")
        print(f"追踪角色数：{len(memory_dict['character_arcs'])}")
        for name, arc in memory_dict['character_arcs'].items():
            print(f"  - {name}：{arc['current']}")
    
    # 7. 查看结构化审稿结果
    if hasattr(result, 'structured_reviews') and result.structured_reviews:
        print("\n" + "=" * 60)
        print("结构化审稿结果")
        print("=" * 60)
        for chapter, reviews in result.structured_reviews.items():
            for review in reviews:
                print(f"\n第{chapter}章 - 评分：{review.total_score}分")
                print(f"结论：{review.verdict.value}")
                print(f"评语：{review.summary}")
                print("\n维度评分：")
                for dim in review.dimensions:
                    print(f"  - {dim.name}：{dim.score}分（权重{dim.weight}）")
                print("\n问题列表：")
                for issue in review.issues:
                    print(f"  [{issue.severity}] {issue.location}：{issue.description}")
                    if issue.suggestion:
                        print(f"    建议：{issue.suggestion}")
    
    if 1 in result.chapters:
        print(f"\n章节预览（前200字）：")
        print(result.chapters[1][:200] + "...")
    
    if 1 in result.reviews:
        print(f"\n审稿记录：")
        for r in result.reviews[1]:
            print(f"  第{r.round}轮 - {r.reviewer}: {r.score}分 {'✅' if r.passed else '❌'}")


if __name__ == "__main__":
    main()
