"""
StoryForge - Pipeline
大纲细化 → 写作 → 审稿 → 修改 → 校对 → 萃取 → IP 生成
"""

from langgraph.graph import StateGraph, END
from typing import Dict, Callable, Any, Optional
import json
import os

from core.state import NovelState, ChapterStatus, PipelineStage
from core.schema import ReviewVerdict
from core.memory import StoryMemory
from core.prompt_assembler import PromptAssembler
from core.utils.errors import ErrorHandler
from agents.creation_agents import (
    WriterAgent, ReviewerAgent, ReviserAgent, ProofreaderAgent
)
from stages.extraction.knowledge_extractor import KnowledgeExtractor
from stages.ip_generation.ip_generator import IPGenerator
from stages.outline.outline_generator import OutlineGenerator


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
        use_outline_refinement: bool = True,
        use_extraction: bool = True,
        use_ip_generation: bool = True,
        checkpoint_dir: Optional[str] = None,  # 断点续跑检查点目录
        ip_output_dir: str = "./ip_assets"
    ):
        self.llm_client = llm_client
        self.use_memory = use_memory
        self.use_outline_refinement = use_outline_refinement
        self.use_extraction = use_extraction
        self.use_ip_generation = use_ip_generation
        self.checkpoint_dir = checkpoint_dir or ".checkpoints"
        self.ip_output_dir = ip_output_dir
        self.memory: Optional[StoryMemory] = None
        self.prompt_assembler: Optional[PromptAssembler] = None
        self.outline_generator: Optional[OutlineGenerator] = None
        self.knowledge_extractor: Optional[KnowledgeExtractor] = None
        self.ip_generator: Optional[IPGenerator] = None
        self.error_handler: Optional[ErrorHandler] = None
        self.workflow = None
        self._last_node: Optional[str] = None  # 上一个执行节点
        
        # Agent 引用（用于断点续跑）
        self._writer_agent = None
        self._reviewer_agent = None
        self._reviser_agent = None
        self._proofreader_agent = None
        
        # 确保检查点目录存在
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        
        self._initialize_components()
        self._build()
    
    def _initialize_components(self):
        """初始化组件"""
        if self.use_memory:
            self.memory = StoryMemory()
        
        self.prompt_assembler = PromptAssembler()
        self.outline_generator = OutlineGenerator(self.llm_client)
        self.error_handler = ErrorHandler()
        
        if self.use_extraction:
            self.knowledge_extractor = KnowledgeExtractor(
                llm_client=self.llm_client,
                memory=self.memory
            )
        
        if self.use_ip_generation:
            self.ip_generator = IPGenerator(
                llm_client=self.llm_client,
                output_dir=self.ip_output_dir
            )
    
    def _build(self):
        """构建 LangGraph 工作流"""
        
        # 初始化 Agent（保存引用用于断点续跑）
        self._writer_agent = WriterAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler,
            prompt_assembler=self.prompt_assembler
        )
        self._reviewer_agent = ReviewerAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler,
            prompt_assembler=self.prompt_assembler
        )
        self._reviser_agent = ReviserAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler,
            prompt_assembler=self.prompt_assembler
        )
        self._proofreader_agent = ProofreaderAgent(
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
        workflow.add_node("writer", self._writer_agent.invoke)
        workflow.add_node("reviewer", self._reviewer_agent.invoke)
        workflow.add_node("reviser", self._reviser_agent.invoke)
        workflow.add_node("proofreader", self._proofreader_agent.invoke)
        
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
        """大纲细化阶段：生成章级细纲"""
        print(f"📝 大纲细化阶段：第{state.current_chapter}章")
        
        # 确保 creation 容器存在
        if not isinstance(state.creation, dict):
            state.creation = {}
        
        # 初始化 chapter_outlines（如果还没有）
        if 'chapter_outlines' not in state.creation:
            state.creation['chapter_outlines'] = {}
        
        # 已经有细纲则跳过
        if state.current_chapter in state.creation['chapter_outlines']:
            print(f"  ⏭️ 第{state.current_chapter}章细纲已存在，跳过")
            return state
        
        # 检查依赖：需要大纲生成器、小说标题、卷纲
        if not self.outline_generator:
            print(f"  ⚠️ OutlineGenerator 未初始化，跳过细纲生成")
            state.creation['chapter_outlines'][state.current_chapter] = None
            return state
        
        if not state.novel_title:
            print(f"  ⚠️ 小说标题未设置，跳过细纲生成")
            state.creation['chapter_outlines'][state.current_chapter] = None
            return state
        
        # 获取当前卷号（每10章一卷，向上取整）
        volume_num = (state.current_chapter - 1) // 10
        volume_outline = state.volume_outline.get(volume_num, "")
        
        if not volume_outline and state.outline:
            # 如果没有卷纲，使用整体大纲作为后备
            volume_outline = state.outline[:500]  # 取前500字符作为上下文
        
        try:
            # 调用 OutlineGenerator 生成章级细纲
            chapter_outline = self.outline_generator.generate_chapter_outline(
                novel_title=state.novel_title,
                volume_outline=volume_outline,
                current_chapter=state.current_chapter,
                characters=state.characters,
                target_words=state.target_word_count
            )
            
            state.creation['chapter_outlines'][state.current_chapter] = chapter_outline
            print(f"  ✅ 第{state.current_chapter}章细纲生成完成")
            
        except Exception as e:
            print(f"  ❌ 细纲生成失败：{e}")
            # 失败时不阻塞流程，记录None继续
            state.creation['chapter_outlines'][state.current_chapter] = None
            state.error_message = f"大纲细化失败：{str(e)}"
        
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
        
        if not self.knowledge_extractor:
            state.current_stage = PipelineStage.EXTRACTION
            return state
        
        # 获取章节内容
        chapter_content = state.chapters.get(state.current_chapter, "")
        if not chapter_content:
            print(f"  ⚠️ 第{state.current_chapter}章没有内容，跳过萃取")
            state.current_stage = PipelineStage.EXTRACTION
            return state
        
        try:
            # 执行知识萃取
            analysis = self.knowledge_extractor.extract(
                chapter=state.current_chapter,
                chapter_content=chapter_content
            )
            
            # 保存分析结果到 state
            if not hasattr(state, 'chapter_analyses'):
                state.chapter_analyses = {}
            state.chapter_analyses[state.current_chapter] = analysis
            
            print(f"  ✅ 第{state.current_chapter}章知识萃取完成: "
                  f"{len(analysis.events)}个事件, "
                  f"{len(analysis.new_characters)}个新人物, "
                  f"{len(analysis.new_foreshadowings)}个新伏笔")
            
        except Exception as e:
            print(f"  ⚠️ 知识萃取失败: {e}")
        
        state.current_stage = PipelineStage.EXTRACTION
        return state
    
    def _ip_designer(self, state: NovelState) -> NovelState:
        """IP生成（阶段三）"""
        print(f"🎨 生成 IP 资产...")
        
        if not self.ip_generator:
            state.current_stage = PipelineStage.IP_GENERATION
            return state
        
        # 获取已完成章节
        completed_chapters = {
            ch: content
            for ch, content in state.chapters.items()
            if content and len(content) > 100
        }
        
        if not completed_chapters:
            print(f"  ⚠️ 没有足够的已完成章节，跳过 IP 生成")
            state.current_stage = PipelineStage.IP_GENERATION
            return state
        
        try:
            # 获取章节分析结果
            chapter_analyses = getattr(state, 'chapter_analyses', None)
            
            # 执行 IP 生成
            bible = self.ip_generator.generate(
                title=state.novel_title or "未命名小说",
                chapters=completed_chapters,
                chapter_analyses=chapter_analyses
            )
            
            # 保存 Story Bible 到 state
            state.story_bible = bible
            
            print(f"  ✅ IP 生成完成: {len(bible.characters)} 个人物, "
                  f"{len(bible.key_scenes)} 个场景, "
                  f"{len(bible.derived_settings)} 个衍生设定")
            
        except Exception as e:
            print(f"  ⚠️ IP 生成失败: {e}")
        
        state.current_stage = PipelineStage.IP_GENERATION
        return state
    
    def _save_checkpoint(self, state: NovelState, node_name: str):
        """保存检查点（每完成一个节点调用）"""
        checkpoint_path = os.path.join(
            self.checkpoint_dir,
            f"checkpoint_{state.novel_id or 'unknown'}_ch{state.current_chapter}.json"
        )
        
        checkpoint = {
            "novel_id": state.novel_id,
            "current_chapter": state.current_chapter,
            "current_stage": state.current_stage.value,
            "last_node": node_name,
            "chapter_status": {k: v.value for k, v in state.chapter_status.items()},
            "review_round": state.review_round,
            "chapters": {str(k): v for k, v in state.chapters.items()},
            "creation": state.creation,
            "reviews": {str(k): [
                {"round": r.round, "reviewer": r.reviewer, "score": r.score,
                 "comments": r.comments, "passed": r.passed}
                for r in v
            ] for k, v in state.reviews.items()},
            "structured_reviews": {str(k): [
                self._review_to_dict(r) for r in v
            ] for k, v in state.structured_reviews.items()},
            "proofread_results": {str(k): [
                self._proofread_to_dict(r) for r in v
            ] for k, v in state.proofread_results.items()},
            "error_message": state.error_message,
            "timestamp": datetime.now().isoformat() if hasattr(datetime, 'now') else ""
        }
        
        try:
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint, f, ensure_ascii=False, indent=2)
            print(f"💾 检查点已保存: {checkpoint_path}")
        except Exception as e:
            print(f"⚠️ 保存检查点失败: {e}")
    
    def _review_to_dict(self, review) -> dict:
        """将审稿结果转为字典"""
        if hasattr(review, '__dict__'):
            return review.__dict__
        elif isinstance(review, dict):
            return review
        return {"raw": str(review)}
    
    def _proofread_to_dict(self, proofread) -> dict:
        """将校对结果转为字典"""
        if hasattr(proofread, '__dict__'):
            return proofread.__dict__
        elif isinstance(proofread, dict):
            return proofread
        return {"raw": str(proofread)}
    
    def load_checkpoint(self, novel_id: str, chapter: int) -> Optional[NovelState]:
        """从检查点恢复状态"""
        checkpoint_path = os.path.join(
            self.checkpoint_dir,
            f"checkpoint_{novel_id}_ch{chapter}.json"
        )
        
        if not os.path.exists(checkpoint_path):
            print(f"⚠️ 检查点不存在: {checkpoint_path}")
            return None
        
        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                checkpoint = json.load(f)
            
            state = NovelState(
                novel_id=checkpoint.get("novel_id", ""),
                current_chapter=checkpoint.get("current_chapter", 1),
                current_stage=PipelineStage(checkpoint.get("current_stage", "creation")),
                chapter_status={int(k): ChapterStatus(v) for k, v in checkpoint.get("chapter_status", {}).items()},
                review_round=checkpoint.get("review_round", 0),
                chapters={int(k): v for k, v in checkpoint.get("chapters", {}).items()},
                creation=checkpoint.get("creation", {}),
                error_message=checkpoint.get("error_message", "")
            )
            
            self._last_node = checkpoint.get("last_node")
            print(f"✅ 检查点已恢复: 第{chapter}章, 最后节点: {self._last_node}")
            return state
            
        except Exception as e:
            print(f"❌ 恢复检查点失败: {e}")
            return None
    
    def resume(self, novel_id: str, chapter: int, from_node: Optional[str] = None) -> NovelState:
        """
        从检查点恢复并继续执行
        
        Args:
            novel_id: 小说ID
            chapter: 章节号
            from_node: 从指定节点重新开始（覆盖检查点记录）
        """
        state = self.load_checkpoint(novel_id, chapter)
        if not state:
            raise ValueError(f"无法恢复检查点: {novel_id} 第{chapter}章")
        
        # 确定从哪个节点继续
        resume_node = from_node or self._last_node
        if not resume_node:
            print("⚠️ 未指定恢复节点，从头开始")
            return self.run(state)
        
        print(f"🔄 从节点 '{resume_node}' 恢复执行")
        
        # 使用已保存的 Agent 引用
        node_map = {
            "outline_refiner": self._outline_refiner,
            "writer": self._writer_agent.invoke if self._writer_agent else lambda s: s,
            "reviewer": self._reviewer_agent.invoke if self._reviewer_agent else lambda s: s,
            "reviser": self._reviser_agent.invoke if self._reviser_agent else lambda s: s,
            "proofreader": self._proofreader_agent.invoke if self._proofreader_agent else lambda s: s,
            "knowledge_extractor": self._knowledge_extractor,
            "ip_designer": self._ip_designer
        }
        
        if resume_node not in node_map:
            print(f"⚠️ 未知节点 '{resume_node}'，从头开始")
            return self.run(state)
        
        # 手动执行后续节点
        current_state = state
        nodes_to_run = list(node_map.keys())
        start_idx = nodes_to_run.index(resume_node)
        
        for node_name in nodes_to_run[start_idx:]:
            print(f"▶️ 执行节点: {node_name}")
            try:
                current_state = node_map[node_name](current_state)
                self._save_checkpoint(current_state, node_name)
            except Exception as e:
                print(f"❌ 节点 {node_name} 执行失败: {e}")
                current_state.error_message = f"节点 {node_name} 失败: {str(e)}"
                break
        
        return current_state
    
    def _get_agent(self, name: str) -> Callable:
        """获取已初始化的 Agent（兼容旧代码）"""
        agent_map = {
            "writer": self._writer_agent,
            "reviewer": self._reviewer_agent,
            "reviser": self._reviser_agent,
            "proofreader": self._proofreader_agent
        }
        agent = agent_map.get(name)
        if agent:
            return agent.invoke
        return lambda s: s
    
    def list_checkpoints(self, novel_id: Optional[str] = None) -> list:
        """列出所有可用的检查点"""
        if not os.path.exists(self.checkpoint_dir):
            return []
        
        checkpoints = []
        for fname in os.listdir(self.checkpoint_dir):
            if fname.startswith('checkpoint_') and fname.endswith('.json'):
                if novel_id and novel_id not in fname:
                    continue
                checkpoints.append(fname)
        
        return sorted(checkpoints)
    
    def run(self, initial_state: NovelState) -> NovelState:
        """运行 Pipeline（支持断点保存）"""
        print(f"🚀 启动 StoryForge Pipeline")
        print(f"📚 小说：{initial_state.novel_title or '未命名'}")
        print(f"🎯 目标：创作第{initial_state.current_chapter}章")
        
        # 初始化记忆
        if self.memory and initial_state.characters:
            self.memory.initialize_from_outline(
                characters=initial_state.characters,
                world_setting=getattr(initial_state, 'world_setting', None)
            )
        
        # 使用 LangGraph 的 checkpoint 功能（如果支持）
        # 或者手动包装每个节点调用
        result = self.workflow.invoke(initial_state)
        
        if isinstance(result, dict):
            result = NovelState(**result)
        
        # 保存最终检查点
        self._save_checkpoint(result, "completed")
        
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
