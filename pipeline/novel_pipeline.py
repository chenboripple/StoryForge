"""
NovelForge - LangGraph Pipeline 定义
核心：图结构 + 状态机 + 循环控制
"""

from langgraph.graph import StateGraph, END
from typing import Dict, Callable

from core.state import NovelState, ChapterStatus, PipelineStage
from agents.creation_agents import WriterAgent, ReviewerAgent, ReviserAgent, ProofreaderAgent


class NovelPipeline:
    """
    小说创作 Pipeline
    
    图结构：
    
    [outline] → [write] → [review] → {通过?} → [proofread] → {通过?} → [END]
                         ↓ 否           ↓ 否
                       [revise] ←──── [revise]
                         ↓
                       [review] (循环)
    
    面试重点：
    1. 用图结构表达复杂流程（vs 线性链）
    2. 循环边实现审稿闭环
    3. 条件边实现动态路由
    """
    
    def __init__(self, llm_client: Callable = None):
        self.llm_client = llm_client
        self.workflow = None
        self._build()
    
    def _build(self):
        """构建 LangGraph 工作流"""
        
        # 初始化 Agent
        writer = WriterAgent(self.llm_client)
        reviewer = ReviewerAgent(self.llm_client)
        reviser = ReviserAgent(self.llm_client)
        proofreader = ProofreaderAgent(self.llm_client)
        
        # 创建图
        workflow = StateGraph(NovelState)
        
        # ========== 添加节点 ==========
        
        # 创作层节点
        workflow.add_node("writer", writer.invoke)
        workflow.add_node("reviewer", reviewer.invoke)
        workflow.add_node("reviser", reviser.invoke)
        workflow.add_node("proofreader", proofreader.invoke)
        
        # 萃取层节点（占位，后续实现）
        workflow.add_node("knowledge_extractor", self._knowledge_extractor)
        
        # IP 生成层节点（占位，后续实现）
        workflow.add_node("ip_designer", self._ip_designer)
        
        # ========== 添加边 ==========
        
        # 1. 写作 → 审稿
        workflow.add_edge("writer", "reviewer")
        
        # 2. 审稿 → 条件路由
        workflow.add_conditional_edges(
            "reviewer",
            self._review_router,
            {
                "approve": "proofreader",      # 高分→校对
                "revise": "reviser",           # 需修改→修改
                "rewrite": "writer",           # 太低→重写
                "max_retries": "proofreader"   # 超次数→强制进入校对
            }
        )
        
        # 3. 修改 → 重新审稿（循环边！）
        workflow.add_edge("reviser", "reviewer")
        
        # 4. 校对 → 条件路由
        workflow.add_conditional_edges(
            "proofreader",
            self._proofread_router,
            {
                "pass": "knowledge_extractor",  # 通过→进入萃取
                "fail": "reviser"               # 失败→修改
            }
        )
        
        # 5. 萃取 → IP 生成
        workflow.add_edge("knowledge_extractor", "ip_designer")
        
        # 6. IP 生成 → 结束
        workflow.add_edge("ip_designer", END)
        
        # 设置入口
        workflow.set_entry_point("writer")
        
        # 编译
        self.workflow = workflow.compile()
    
    # ========== 路由函数 ==========
    
    def _review_router(self, state: NovelState) -> str:
        """
        审稿后路由决策
        
        策略：
        - ≥85分：进入校对
        - 60-84分：修改后再审
        - <60分：重写
        - 超过最大轮次：强制进入校对（避免死循环）
        """
        latest = state.get_latest_review()
        
        if not latest:
            return "revise"
        
        # 检查是否超过最大审稿轮次
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
        """校对后路由决策"""
        status = state.get_current_chapter_status()
        
        if status == ChapterStatus.APPROVED:
            print(f"✅ 第{state.current_chapter}章校对通过，进入萃取阶段")
            return "pass"
        elif state.review_round >= state.max_review_rounds + 2:
            # 校对也超次了，强制通过避免死循环
            print(f"⚠️ 第{state.current_chapter}章校对多次未通过，强制进入萃取阶段")
            return "pass"
        else:
            print(f"📝 第{state.current_chapter}章校对发现问题，返回修改")
            return "fail"
    
    # ========== 占位节点（后续实现） ==========
    
    def _knowledge_extractor(self, state: NovelState) -> NovelState:
        """知识萃取（阶段二）"""
        print(f"🔍 萃取第{state.current_chapter}章知识...")
        # TODO: 实现知识萃取逻辑
        state.current_stage = PipelineStage.EXTRACTION
        return state
    
    def _ip_designer(self, state: NovelState) -> NovelState:
        """IP 生成（阶段三）"""
        print(f"🎨 生成 IP 资产...")
        # TODO: 实现 IP 生成逻辑
        state.current_stage = PipelineStage.IP_GENERATION
        return state
    
    # ========== 公共接口 ==========
    
    def run(self, initial_state: NovelState) -> NovelState:
        """
        运行 Pipeline
        
        Args:
            initial_state: 初始状态（至少包含 novel_title, outline, characters）
            
        Returns:
            最终状态
        """
        print(f"🚀 启动 NovelForge Pipeline")
        print(f"📚 小说：{initial_state.novel_title or '未命名'}")
        print(f"🎯 目标：创作第{initial_state.current_chapter}章\n")
        
        # LangGraph 的 invoke 可能返回 dict，需要转换
        result = self.workflow.invoke(initial_state)
        
        # 如果返回的是 dict，转换回 NovelState
        if isinstance(result, dict):
            result = NovelState(**result)
        
        print(f"\n✨ Pipeline 完成！")
        print(f"📊 最终状态：{result.current_stage.value}")
        
        return result
    
    def run_batch(self, state: NovelState, chapters: list) -> Dict[int, NovelState]:
        """
        批量创作多章
        
        Args:
            state: 基础状态
            chapters: 章节号列表
            
        Returns:
            各章结果
        """
        results = {}
        for chapter_num in chapters:
            state.current_chapter = chapter_num
            state.chapter_status[chapter_num] = ChapterStatus.PENDING
            results[chapter_num] = self.run(state)
        return results
    
    def visualize(self):
        """可视化图结构（需要安装 graphviz）"""
        try:
            return self.workflow.get_graph().draw_mermaid()
        except:
            return "可视化需要安装 graphviz"


# ==================== 便捷函数 ====================

def create_pipeline(llm_client: Callable = None) -> NovelPipeline:
    """创建 Pipeline 工厂函数"""
    return NovelPipeline(llm_client)
