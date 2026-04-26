#!/usr/bin/env python3
"""
StoryForge - 本地调试脚本
支持：
1. 保存 prompt 到文件
2. 保存完整状态到 JSON
3. 单步调试模式
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import NovelState, CharacterInfo
from pipeline.novel_pipeline_v2 import create_pipeline_v2
from core.memory import StoryMemory


DEBUG_DIR = "debug_output"
os.makedirs(DEBUG_DIR, exist_ok=True)


class DebugLLM:
    """
    调试用 LLM Client：
    1. 保存所有 prompt 到文件
    2. 打印详细的调用信息
    3. 返回 mock 输出
    """
    
    def __init__(self, save_prompts=True, verbose=True):
        self.save_prompts = save_prompts
        self.verbose = verbose
        self.call_count = 0
        self.prompts = []
    
    def __call__(self, prompt: str, temperature: float = None) -> str:
        self.call_count += 1
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if self.verbose:
            print(f"\n{'=' * 80}")
            print(f"[DEBUG LLM] Call #{self.call_count} (temp: {temperature})")
            print(f"{'=' * 80}")
            print(f"Prompt preview (first 300 chars):\n{prompt[:300]}...")
        
        if self.save_prompts:
            prompt_file = os.path.join(DEBUG_DIR, f"prompt_{timestamp}_{self.call_count}.txt")
            with open(prompt_file, "w", encoding="utf-8") as f:
                f.write(f"Temperature: {temperature}\n\n")
                f.write(f"Timestamp: {timestamp}\n\n")
                f.write(f"{prompt}")
            if self.verbose:
                print(f"Prompt saved to: {prompt_file}")
        
        result = self._mock_response(prompt, temperature)
        
        if self.verbose:
            print(f"\nResponse preview (first 300 chars):\n{result[:300]}...")
        
        self.prompts.append({
            "call": self.call_count,
            "timestamp": timestamp,
            "prompt": prompt,
            "response": result
        })
        
        return result
    
    def _mock_response(self, prompt: str, temperature: float = None) -> str:
        """根据 prompt 内容返回合适的 mock 输出"""
        import json
        
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
        
        else:
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
    
    def save_prompts_to_json(self):
        """保存所有 prompt 调用历史"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = os.path.join(DEBUG_DIR, f"prompts_history_{timestamp}.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.prompts, f, ensure_ascii=False, indent=2)
        print(f"\n[DEBUG] Prompt history saved to: {json_file}")


def save_state_to_json(state, filename=None):
    """保存完整状态到 JSON"""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"state_{timestamp}.json"
    
    json_file = os.path.join(DEBUG_DIR, filename)
    
    # 转换状态为可序列化 dict
    state_dict = {
        "novel_id": state.novel_id,
        "novel_title": state.novel_title,
        "genre": state.genre,
        "current_chapter": state.current_chapter,
        "current_stage": state.current_stage.value if state.current_stage else None,
        "chapter_status": {k: v.value if hasattr(v, "value") else v for k, v in state.chapter_status.items()},
        "review_round": state.review_round,
        "max_review_rounds": state.max_review_rounds,
        "chapters": state.chapters,
        "reviews": {
            k: [{
                "round": r.round,
                "reviewer": r.reviewer,
                "score": r.score,
                "comments": r.comments,
                "passed": r.passed,
                "timestamp": r.timestamp
            } for r in v] for k, v in state.reviews.items()
        }
    }
    
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(state_dict, f, ensure_ascii=False, indent=2)
    
    print(f"[DEBUG] State saved to: {json_file}")
    return json_file


def main():
    """运行调试模式"""
    
    print("=" * 80)
    print("StoryForge Pipeline - 本地调试模式")
    print("=" * 80)
    print(f"Debug output directory: {os.path.abspath(DEBUG_DIR)}")
    print()
    
    # 1. 清理之前的调试文件
    import shutil
    for item in os.listdir(DEBUG_DIR):
        if item.endswith(".txt") or item.endswith(".json"):
            os.remove(os.path.join(DEBUG_DIR, item))
    
    # 2. 准备初始状态
    print("[DEBUG] 准备初始状态...")
    state = NovelState(
        novel_id="debug_001",
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
    
    # 3. 创建调试用 LLM Client
    debug_llm = DebugLLM(save_prompts=True, verbose=True)
    
    # 4. 创建 Pipeline
    print("\n[DEBUG] 创建 Pipeline V2...")
    pipeline = create_pipeline_v2(
        llm_client=debug_llm,
        use_memory=True
    )
    
    # 5. 可视化
    print("\n" + "=" * 80)
    print("Pipeline 图结构（Mermaid 语法）")
    print("=" * 80)
    print(pipeline.visualize())
    
    # 6. 保存初始状态
    print("\n[DEBUG] 保存初始状态...")
    save_state_to_json(state, "state_initial.json")
    
    # 7. 执行
    print("\n" + "=" * 80)
    print("开始执行 Pipeline")
    print("=" * 80)
    
    try:
        result = pipeline.run(state)
        
        # 8. 保存最终状态
        print("\n[DEBUG] 保存最终状态...")
        save_state_to_json(result, "state_final.json")
        
        # 9. 保存 prompt 历史
        debug_llm.save_prompts_to_json()
        
        # 10. 显示结果
        print("\n" + "=" * 80)
        print("执行完成")
        print("=" * 80)
        print(f"LLM 调用次数：{debug_llm.call_count}")
        print(f"章节状态：{result.chapter_status.get(1)}")
        print(f"审稿轮次：{result.review_round}")
        print(f"最终阶段：{result.current_stage.value}")
        
        if 1 in result.chapters:
            print(f"\n章节预览（前300字）：")
            print(result.chapters[1][:300] + "...")
        
        print(f"\n所有调试文件已保存到：{os.path.abspath(DEBUG_DIR)}")
        print()
        
    except Exception as e:
        print(f"\n[ERROR] 执行失败：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
