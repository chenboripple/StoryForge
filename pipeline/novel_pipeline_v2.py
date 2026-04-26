"""
StoryForge - 重构后的 Pipeline 入口
改进点：
1. 使用新 Agent（JSON mode + 记忆系统）
2. 支持结构化输出
3. 错误处理
4. 向后兼容
"""

from langgraph.graph import StateGraph, END
from typing import Dict, Callable, Any, Optional

from core.state import NovelState, NovelStateV2, ChapterStatus, PipelineStage
from core.memory import StoryMemory
from core.utils.errors import ErrorHandler
from agents.creation_agents_v2 import (
    WriterAgent, ReviewerAgent, ReviserAgent, ProofreaderAgent
)


class NovelPipelineV2:
    """
    重构后的 Pipeline
    
    改进：
    1. 集成记忆系统
    2. 结构化输出（JSON）
    3. 错误处理
    4. 向后兼容旧状态
    """
    
    def __init__(
        self,
        llm_client: Callable = None,
        use_memory: bool = True,
        error_handler: ErrorHandler = None
    ):
        self.llm_client = llm_client
        self.use_memory = use_memory
        self.error_handler = error_handler or ErrorHandler()
        self.memory: Optional[StoryMemory] = None
        self.workflow = None
        self._build()
    
    def _build(self):
        """构建 LangGraph 工作流"""
        
        # 初始化记忆系统
        if self.use_memory:
            self.memory = StoryMemory()
        
        # 初始化 Agent（新版本）
        writer = WriterAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler
        )
        reviewer = ReviewerAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler
        )
        reviser = ReviserAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler
        )
        proofreader = ProofreaderAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler
        )
        
        # 创建图
        workflow = StateGraph(NovelState)
        
        # 添加节点
        workflow.add_node("writer", writer.invoke)
        workflow.add_node("reviewer", reviewer.invoke)
        workflow.add_node("reviser", reviser.invoke)
        workflow.add_node("proofreader", proofreader.invoke)
        workflow.add_node("knowledge_extractor", self._knowledge_extractor)
        workflow.add_node("ip_designer", self._ip_designer)
        
        # 添加边
        workflow.add_edge("writer", "reviewer")
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
        workflow.add_edge("reviser", "reviewer")
        workflow.add_conditional_edges(
            "proofreader",
            self._proofread_router,
            {
                "pass": "knowledge_extractor",
                "fail": "reviser"
            }
        )
        workflow.add_edge("knowledge_extractor", "ip_designer")
        workflow.add_edge("ip_designer", END)
        
        workflow.set_entry_point("writer")
        
        self.workflow = workflow.compile()
    
    def _review_router(self, state: NovelState) -> str:
        """审稿后路由"""
        # 检查是否有错误
        if state.error_message:
            print(f"❌ 错误：{state.error_message}")
            return "max_retries"  # 强制结束
        
        latest = state.get_latest_review()
        
        if not latest:
            return "revise"
        
        if state.review_round >= state.max_review_rounds:
            print(f"⚠️ 第{state.current_chapter}章审稿{state.review_round}轮未通过，强制进入校对")
            return "max_retries"
        
        score = latest.score
        
        if score >= 85:
            print(f"✅ 第{state.current_chapter}章审稿通过（{score}分），进入校对")
            return "approve"
        elif score >= 60:
            print(f"📝 第{state.current_chapter}章需修改（{score}分），第{state.review_round + 1}轮修改")
            return "revise"
        else:
            print(f"❌ 第{state.current_chapter}章评分过低（{score}分），要求重写")
            return "rewrite"
    
    def _proofread_router(self, state: NovelState) -> str:
        """校对后路由"""
        status = state.get_current_chapter_status()
        
        if status == ChapterStatus.APPROVED:
            print(f"✅ 第{state.current_chapter}章校对通过，进入萃取阶段")
            return "pass"
        elif state.review_round >= state.max_review_rounds + 2:
            print(f"⚠️ 第{state.current_chapter}章校对多次未通过，强制进入萃取阶段")
            return "pass"
        else:
            print(f"📝 第{state.current_chapter}章校对发现问题，返回修改")
            return "fail"
    
    def _knowledge_extractor(self, state: NovelState) -> NovelState:
        """知识萃取"""
        print(f"🔍 萃取第{state.current_chapter}章知识...")
        state.current_stage = PipelineStage.EXTRACTION
        return state
    
    def _ip_designer(self, state: NovelState) -> NovelState:
        """IP 生成"""
        print(f"🎨 生成 IP 资产...")
        state.current_stage = PipelineStage.IP_GENERATION
        return state
    
    def run(self, initial_state: NovelState) -> NovelState:
        """运行 Pipeline"""
        print(f"🚀 启动 StoryForge Pipeline V2")
        print(f"📚 小说：{initial_state.novel_title or '未命名'}")
        print(f"🎯 目标：创作第{initial_state.current_chapter}章\n")
        
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
        """批量创作"""
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

def create_pipeline_v2(
    llm_client: Callable = None,
    use_memory: bool = True
) -> NovelPipelineV2:
    """创建 Pipeline V2"""
    return NovelPipelineV2(
        llm_client=llm_client,
        use_memory=use_memory
    )
