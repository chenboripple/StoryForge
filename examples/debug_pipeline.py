#!/usr/bin/env python3
"""
StoryForge - 调试脚本
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.state import NovelState, CharacterInfo
from pipeline.novel_pipeline import create_pipeline
from core.memory import StoryMemory
from core.prompt_assembler import PromptAssembler
from core.config import get_config


config = get_config()
DEBUG_DIR = config.debug.output_dir
os.makedirs(DEBUG_DIR, exist_ok=True)


class DebugLLM:
    """
    调试用 LLM Client
    """
    
    def __init__(self, save_prompts: bool = True, verbose: bool = True):
        self.save_prompts = save_prompts
        self.verbose = verbose
        self.call_count = 0
        self.prompts = []
    
    def __call__(self, prompt: str, temperature: float = None) -> str:
        self.call_count += 1
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        if self.verbose:
            print(f"\n{'='*80}")
            print(f"[Debug LLM] Call #{self.call_count}")
            print(f"{'='*80}")
            preview = prompt[:300] if len(prompt) > 300 else prompt
            print(f"Prompt preview:\n{preview}")
            if len(prompt) > 300:
                print("...")
        
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
            preview = result[:300] if len(result) > 300 else result
            print(f"\nResponse preview:\n{preview}")
            if len(result) > 300:
                print("...")
        
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
        
        if "最终校对" in prompt or "错别字" in prompt:
            return json.dumps({
                "passed": True,
                "verdict": "可发布",
                "issues": [],
                "summary": "无错误，通过。"
            }, ensure_ascii=False)
        
        elif "审稿" in prompt or "维度评分" in prompt:
            return json.dumps({
                "total_score": 88,
                "dimensions": [
                    {"name": "叙事结构", "score": 90, "weight": 0.3, "comment": "开头即冲突，节奏紧凑"},
                    {"name": "人物一致性", "score": 85, "weight": 0.3, "comment": "林晚果断、陈默冷峻，性格鲜明"},
                    {"name": "文学性", "score": 88, "weight": 0.3, "comment": "细节到位（92式手枪、血红色天空）"},
                    {"name": "市场潜力", "score": 90, "weight": 0.1, "comment": "末日+悬疑，有爆款潜质"}
                ],
                "ai_flavor": {
                    "score": 3,
                    "level": "low"
                },
                "issues": [
                    {"severity": "B", "location": "第3段", "type": "常见比喻", "description": "'血红色的天空'出现两次", "suggestion": "第二次可改为'猩红色的天幕'"}
                ],
                "human_highlights": [
                    {"point": "微动作链完整", "example": "林晚举起双手→陈默扣动扳机→枪口垂下"}
                ],
                "location_check": {
                    "passed": True,
                    "issues": []
                },
                "meta_issues": [],
                "verdict": "pass",
                "summary": "整体质量优秀，人物鲜明，冲突强烈。AI味低，轻微优化即可。"
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

林晚的瞳孔收缩。这是她第一次听到这个代号。她感觉后颈汗毛竖了起来，不是因为风。

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
            return """
林晚站在观测塔的废墟上，夜风裹挟着辐射尘拍打她的面罩。
"""
    
    def save_prompts_to_json(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = os.path.join(DEBUG_DIR, f"prompts_history_{timestamp}.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(self.prompts, f, ensure_ascii=False, indent=2)
        print(f"\n[Debug] Prompt history saved to: {json_file}")


def save_state_to_json(state, filename: str = None):
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"state_final_{timestamp}.json"
    
    json_file = os.path.join(DEBUG_DIR, filename)
    
    def _serialize_chapter(ch):
        if isinstance(ch, dict):
            return ch
        if hasattr(ch, "__dict__"):
            return {
                k: (v.value if hasattr(v, "value") else v)
                for k, v in ch.__dict__.items()
            }
        return str(ch)

    state_dict = {
        "novel_id": state.novel_id,
        "novel_title": state.novel_title,
        "genre": state.genre,
        "current_chapter": state.current_chapter,
        "current_stage": state.current_stage.value if hasattr(state, 'current_stage') else None,
        "chapter_status": {k: v.value if hasattr(v, 'value') else v for k, v in state.chapter_status.items()},
        "review_round": state.review_round,
        "max_review_rounds": state.max_review_rounds,
        "chapters": {k: _serialize_chapter(v) for k, v in state.chapters.items()}
    }
    
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(state_dict, f, ensure_ascii=False, indent=2)
    
    print(f"[Debug] State saved to: {json_file}")
    return json_file


def main():
    """运行调试脚本"""
    
    print("=" * 80)
    print("StoryForge Pipeline - 调试模式")
    print("=" * 80)
    print(f"Debug output directory: {os.path.abspath(DEBUG_DIR)}")
    print()
    
    # 清理旧的调试文件
    for item in os.listdir(DEBUG_DIR):
        item_path = os.path.join(DEBUG_DIR, item)
        if os.path.isfile(item_path):
            try:
                os.unlink(item_path)
            except:
                pass
    
    # 1. 准备初始状态
    print("[Debug] 准备初始状态...")
    state = NovelState(
        novel_id="debug_001",
        novel_title="熵塔",
        genre="科幻末日",
        target_word_count=config.pipeline.default_target_word_count,
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
    
    # 2. 创建调试用 LLM Client
    debug_llm = DebugLLM(save_prompts=True, verbose=True)
    
    # 3. 创建 Pipeline
    print("\n[Debug] 创建 Pipeline...")
    pipeline = create_pipeline(
        llm_client=debug_llm,
        use_memory=True,
        use_outline_refinement=True
    )
    
    # 4. 可视化
    print("\n" + "=" * 80)
    print("Pipeline 图结构（Mermaid 语法）")
    print("=" * 80)
    print(pipeline.visualize())
    
    # 5. 保存初始状态
    print("\n[Debug] 保存初始状态...")
    save_state_to_json(state, "state_initial.json")
    
    # 6. 执行
    print("\n" + "=" * 80)
    print("开始执行 Pipeline")
    print("=" * 80)
    
    try:
        result = pipeline.run(state)
        
        # 7. 保存最终状态
        print("\n[Debug] 保存最终状态...")
        save_state_to_json(result)
        
        # 8. 保存 prompt 历史
        debug_llm.save_prompts_to_json()
        
        # 9. 显示结果
        print("\n" + "=" * 80)
        print("执行完成")
        print("=" * 80)
        print(f"LLM 调用次数：{debug_llm.call_count}")
        print(f"章节状态：{result.chapter_status.get(1)}")
        print(f"审稿轮次：{result.review_round}")
        print(f"最终阶段：{result.current_stage.value}")
        
        # 显示 AI味等级
        if hasattr(result, 'structured_reviews') and 1 in result.structured_reviews:
            last_review = result.structured_reviews[1][-1]
            ai_flavor_level = getattr(last_review, 'ai_flavor_level', 'unknown')
            ai_flavor_score = getattr(last_review, 'ai_flavor_score', '?')
            print(f"AI味等级：{ai_flavor_level} ({ai_flavor_score}/10)")
        
        # 10. 显示记忆系统状态
        if pipeline.memory:
            print("\n" + "=" * 80)
            print("记忆系统状态")
            print("=" * 80)
            memory_dict = pipeline.memory.to_dict()
            print(f"记录事件数：{len(memory_dict['events'])}")
            print(f"追踪角色数：{len(memory_dict['character_arcs'])}")
            for name, arc in memory_dict['character_arcs'].items():
                print(f"  - {name}：{arc.get('current', '')}")
        
        if 1 in result.chapters:
            print(f"\n章节预览（前300字）：")
            chapter_obj = result.chapters[1]
            if hasattr(chapter_obj, "content"):
                preview = chapter_obj.content[:300]
            elif isinstance(chapter_obj, str):
                preview = chapter_obj[:300]
            else:
                preview = str(chapter_obj)[:300]
            print(preview + "...")
        
        if 1 in result.reviews:
            print(f"\n审稿记录：")
            for r in result.reviews[1]:
                print(f"  第{r.round}轮 - {r.reviewer}: {r.total_score}分 {'✅' if r.passed else '❌'}")
        
        print(f"\n所有调试文件已保存到：{os.path.abspath(DEBUG_DIR)}")
        print()
        
    except Exception as e:
        print(f"\n[Error] 执行失败：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
