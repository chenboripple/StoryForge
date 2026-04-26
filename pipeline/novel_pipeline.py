"""
StoryForge - Pipeline
大纲细化 → 写作 → 审稿 → 修改 → 校对 → 萃取 → IP 生成
"""

from langgraph.graph import StateGraph, END
from typing import Dict, Callable, Any, Optional

from core.state import NovelState, ChapterStatus, PipelineStage
from core.schema import ReviewVerdict
from core.memory import StoryMemory
from core.prompt_assembler import PromptAssembler
from core.outline import OutlineGenerator, ChapterPlan
from core.utils.errors import ErrorHandler
from agents.creation_agents import (
    WriterAgent, ReviewerAgent, ReviserAgent, ProofreaderAgent
)


class NovelPipeline:
    """
    StoryForge Pipeline
    
    阶段：
    1. 大纲细化 → 生成章级细纲
    2. 写作 → 基于细纲写作
    3. Review → 结构化审稿（AI味评估）
    4. 修订 → 基于Review修改
    5. Re-Review → 复审（AI味再检查）
    6. Proofread → 结构化校对（终审判定）
    7. Extraction → 知识萃取
    8. IP Generation → IP生成
    """
    
    def __init__(
        self,
        llm_client: Callable = None,
        use_memory: bool = True,
        use_outline_refinement: bool = True
    ):
        self.llm_client = llm_client
        self.use_memory = use_memory
        self.use_outline_refinement = use_outline_refinement
        self.memory: Optional[StoryMemory] = None
        self.prompt_assembler: Optional[PromptAssembler] = None
        self.outline_generator: Optional[OutlineGenerator] = None
        self.error_handler: Optional[ErrorHandler] = None
        self.workflow = None
        
        self._initialize_components()
        self._build()
    
    def _initialize_components(self):
        """初始化组件"""
        if self.use_memory:
            self.memory = StoryMemory()
        
        self.prompt_assembler = PromptAssembler()
        self.outline_generator = OutlineGenerator(self.llm_client)
        self.error_handler = ErrorHandler()
    
    def _build(self):
        """构建 LangGraph 工作流"""
        
        # 初始化 Agent
        writer = WriterAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler,
            prompt_assembler=self.prompt_assembler
        )
        reviewer = ReviewerAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler,
            prompt_assembler=self.prompt_assembler
        )
        reviser = ReviserAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler,
            prompt_assembler=self.prompt_assembler
        )
        proofreader = ProofreaderAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler,
            prompt_assembler=self.prompt_assembler
        )
        
        # 创建图
        workflow = StateGraph(NovelState)
        
        # ========== 添加节点 ==========
        
        # 大纲细化阶段
        if self.use_outline_refinement:
            workflow.add_node("outline_refiner", self._outline_refiner)
        
        # 创作层节点
        workflow.add_node("writer", writer.invoke)
        workflow.add_node("reviewer", reviewer.invoke)
        workflow.add_node("reviser", reviser.invoke)
        workflow.add_node("proofreader", proofreader.invoke)
        
        # 萃取层节点
        workflow.add_node("knowledge_extractor", self._knowledge_extractor)
        
        # IP生成层节点
        workflow.add_node("ip_designer", self._ip_designer)
        
        # ========== 添加边 ==========
        
        # 1. 大纲细化 → 写作
        if self.use_outline_refinement:
            workflow.set_entry_point("outline_refiner")
            workflow.add_edge("outline_refiner", "writer")
        else:
            workflow.set_entry_point("writer")
        
        # 2. 写作 → 审稿
        workflow.add_edge("writer", "reviewer")
        
        # 3. 审稿 → 条件路由
        workflow.add_conditional_edges(
            "reviewer",
            self._review_router,
            {
                "approve": "proofreader",
                "revise": "reviser",
                "rewrite": "writer",
                "max_retries": "proofreader"
            }
        )
        
        # 4. 修改 → 审稿
        workflow.add_edge("reviser", "reviewer")
        
        # 5. Proofread → 条件路由
        workflow.add_conditional_edges(
            "proofreader",
            self._proofread_router,
            {
                "pass": "knowledge_extractor",
                "fail": "reviser"
            }
        )
        
        # 6. Extraction → IP Generation
        workflow.add_edge("knowledge_extractor", "ip_designer")
        
        # 7. IP Generation → END
        workflow.add_edge("ip_designer", END)
        
        self.workflow = workflow.compile()
    
    def _outline_refiner(self, state: NovelState) -> NovelState:
        """大纲细化阶段（如果启用）"""
        print(f"📝 大纲细化阶段：第{state.current_chapter}章")
        
        # TODO: 调用 OutlineGenerator 生成章级细纲
        # 这里先占位
        state.creation = getattr(state, 'creation', {})
        state.creation['chapter_outlines'] = {}
        
        return state
    
    def _review_router(self, state: NovelState) -> str:
        """审稿路由（检查 AI味等级）"""
        if state.error_message:
            print(f"❌ 错误：{state.error_message}")
            return "max_retries"
        
        latest = state.get_latest_review()
        if not latest:
            return "revise"
        
        # 检查审稿轮次
        if state.review_round >= state.max_review_rounds:
            print(f"⚠️ 第{state.current_chapter}章审稿{state.review_round}轮未通过，强制进入校对")
            return "max_retries"
        
        # 获取结构化审稿结果
        ai_flavor_level = "medium"
        verdict = None

        if hasattr(state, 'structured_reviews') and state.current_chapter in state.structured_reviews:
            review = state.structured_reviews[state.current_chapter][-1]
            ai_flavor_level = getattr(review, 'ai_flavor_level', "medium")
            verdict = getattr(review, 'verdict', None)

        # 如果 AI味等级是 high，要求重写
        if ai_flavor_level == "high":
            print(f"🔄 AI味过重（{ai_flavor_level}），要求重写")
            return "rewrite"

        # 使用 verdict 决定路由（统一归一化到字符串）
        if isinstance(verdict, ReviewVerdict):
            verdict_value = verdict.value
        elif hasattr(verdict, 'value'):
            verdict_value = verdict.value
        elif isinstance(verdict, str):
            verdict_value = verdict.strip().lower()
        else:
            verdict_value = None

        if verdict_value == "pass":
            print(f"✅ 第{state.current_chapter}章审稿通过，进入校对")
            return "approve"
        if verdict_value == "rewrite":
            print(f"🔄 第{state.current_chapter}章需要重写")
            return "rewrite"
        if verdict_value == "revise":
            print(f"📝 第{state.current_chapter}章需要修改，第{state.review_round + 1}轮修改")
            return "revise"
        
        # 回退到原逻辑（分数）
        score = latest.score
        if score >= 85:
            print(f"✅ 第{state.current_chapter}章审稿通过（{score}分），进入校对")
            return "approve"
        elif score >= 60:
            print(f"📝 第{state.current_chapter}章需要修改（{score}分），第{state.review_round + 1}轮修改")
            return "revise"
        else:
            print(f"❌ 第{state.current_chapter}章评分过低（{score}分），要求重写")
            return "rewrite"
    
    def _proofread_router(self, state: NovelState) -> str:
        """校对路由（检查终审判定）"""
        status = state.get_current_chapter_status()

        # 获取结构化校对结果（专用容器，避免与审稿结果混用）
        verdict = None
        chapter_results = getattr(state, 'proofread_results', {}).get(state.current_chapter, [])
        if chapter_results:
            latest = chapter_results[-1]
            verdict = getattr(latest, 'verdict', None)
            if hasattr(verdict, 'value'):
                verdict = verdict.value
            if isinstance(verdict, str):
                verdict = verdict.strip()

        if verdict == "需返修":
            print(f"📝 第{state.current_chapter}章需要返修")
            return "fail"

        if verdict in {"可发布", "可交付"}:
            print(f"✅ 第{state.current_chapter}章校对通过，进入萃取阶段")
            return "pass"

        if status == ChapterStatus.APPROVED:
            print(f"✅ 第{state.current_chapter}章校对通过，进入萃取阶段")
            return "pass"

        if state.review_round >= state.max_review_rounds + 2:
            print(f"⚠️ 第{state.current_chapter}章校对多次未通过，强制进入萃取阶段")
            return "pass"

        print(f"📝 第{state.current_chapter}章校对发现问题，返回修改")
        return "fail"
    
    def _knowledge_extractor(self, state: NovelState) -> NovelState:
        """知识萃取（阶段二）"""
        print(f"🔍 萃取第{state.current_chapter}章知识...")
        
        # TODO: 实现知识萃取逻辑
        # - 提取新人物
        # - 提取新伏笔
        # - 提取新地点
        # - 更新记忆
        
        state.current_stage = PipelineStage.EXTRACTION
        return state
    
    def _ip_designer(self, state: NovelState) -> NovelState:
        """IP生成（阶段三）"""
        print(f"🎨 生成 IP 资产...")
        
        # TODO: 实现 IP 生成逻辑
        
        state.current_stage = PipelineStage.IP_GENERATION
        return state
    
    def run(self, initial_state: NovelState) -> NovelState:
        """运行 Pipeline"""
        print(f"🚀 启动 StoryForge Pipeline")
        print(f"📚 小说：{initial_state.novel_title or '未命名'}")
        print(f"🎯 目标：创作第{initial_state.current_chapter}章")
        
        # 初始化记忆
        if self.memory and initial_state.characters:
            self.memory.initialize_from_outline(
                characters=initial_state.characters,
                world_setting=getattr(initial_state, 'world_setting', None)
            )
        
        result = self.workflow.invoke(initial_state)
        
        if isinstance(result, dict):
            result = NovelState(**result)
        
        print(f"\n✨ Pipeline 完成！")
        print(f"📊 最终状态：{result.current_stage.value}")
        
        return result
    
    def run_batch(self, state: NovelState, chapters: list) -> Dict[int, NovelState]:
        """批量创作多章"""
        results = {}
        for chapter_num in chapters:
            state.current_chapter = chapter_num
            state.chapter_status[chapter_num] = ChapterStatus.PENDING
            results[chapter_num] = self.run(state)
        return results
    
    def visualize(self):
        """可视化"""
        try:
            return self.workflow.get_graph().draw_mermaid()
        except:
            return "可视化需要安装 graphviz"


# ==================== 便捷函数 ====================

def create_pipeline(
    llm_client: Callable = None,
    use_memory: bool = True,
    use_outline_refinement: bool = True
) -> NovelPipeline:
    """创建 Pipeline"""
    return NovelPipeline(
        llm_client=llm_client,
        use_memory=use_memory,
        use_outline_refinement=use_outline_refinement
    )
