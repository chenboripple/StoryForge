"""
StoryForge - Pipeline
大纲细化 → 写作 → 审稿 → 修订 → 校对 → 萃取 → IP 生成
"""

from langgraph.graph import StateGraph, END
from typing import Dict, Callable, Any, Optional
import json
import os
from collections import Counter

from core.models import (
    NovelMeta, PipelineStage, Chapter, ChapterStatus,
    Review, ReviewRecord, Proofread,
    AgentMessage, RoutingSuggestion
)
from core.memory import StoryMemory
from core.prompt_assembler import PromptAssembler
from core.utils.errors import ErrorHandler
from core.agent import MessageBus
from core.config import get_config
from core.storage import get_storage_manager
from agents.creation_agents import (
    WriterAgent, ReviewerAgent, ReviserAgent, ProofreaderAgent
)
from stages.extraction.knowledge_extractor import KnowledgeExtractor
from stages.ip_generation.ip_generator import IPGenerator
from stages.outline.outline_generator import OutlineGenerator


@dataclass
class PipelineState:
    """Pipeline 轻量运行时状态 - 不持久化，只用于节点间传递控制信息"""
    novel_id: str = ""
    current_chapter: int = 1
    review_round: int = 0
    max_review_rounds: int = 3
    error_message: str = ""
    human_feedback: Optional[str] = None
    should_pause: bool = False
    last_node: str = ""


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
    8. IP Generation → IP 生成
    """

    def __init__(
        self,
        llm_client: Callable = None,
        use_memory: bool = True,
        use_outline_refinement: bool = True,
        use_extraction: bool = True,
        use_ip_generation: bool = True,
        use_message_bus: bool = True,
        use_agent_routing: bool = False,
        checkpoint_dir: Optional[str] = None,
        ip_output_dir: str = "./ip_assets",
    ):
        self.llm_client = llm_client
        self.use_memory = use_memory
        self.use_outline_refinement = use_outline_refinement
        self.use_extraction = use_extraction
        self.use_ip_generation = use_ip_generation
        self.use_message_bus = use_message_bus
        self.use_agent_routing = use_agent_routing
        self.checkpoint_dir = checkpoint_dir or ".checkpoints"
        self.ip_output_dir = ip_output_dir
        self.memory: Optional[StoryMemory] = None
        self.prompt_assembler: Optional[PromptAssembler] = None
        self.outline_generator: Optional[OutlineGenerator] = None
        self.knowledge_extractor: Optional[KnowledgeExtractor] = None
        self.ip_generator: Optional[IPGenerator] = None
        self.error_handler: Optional[ErrorHandler] = None
        self.message_bus: Optional[MessageBus] = None
        self.workflow = None
        self._last_node: Optional[str] = None

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

        if self.use_message_bus:
            self.message_bus = MessageBus()

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

        self._writer_agent = WriterAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler,
            prompt_assembler=self.prompt_assembler,
            message_bus=self.message_bus
        )
        self._reviewer_agent = ReviewerAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler,
            prompt_assembler=self.prompt_assembler,
            message_bus=self.message_bus
        )
        self._reviser_agent = ReviserAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler,
            prompt_assembler=self.prompt_assembler,
            message_bus=self.message_bus
        )
        self._proofreader_agent = ProofreaderAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            error_handler=self.error_handler,
            prompt_assembler=self.prompt_assembler,
            message_bus=self.message_bus
        )

        workflow = StateGraph(PipelineState)

        if self.use_outline_refinement:
            workflow.add_node("outline_refiner", self._outline_refiner)

        workflow.add_node("writer", self._wrap_agent_invoke(self._writer_agent, "writer"))
        workflow.add_node("reviewer", self._wrap_agent_invoke(self._reviewer_agent, "reviewer"))
        workflow.add_node("reviser", self._wrap_agent_invoke(self._reviser_agent, "reviser"))
        workflow.add_node("proofreader", self._wrap_agent_invoke(self._proofreader_agent, "proofreader"))
        workflow.add_node("knowledge_extractor", self._knowledge_extractor)
        workflow.add_node("ip_designer", self._ip_designer)

        if self.use_outline_refinement:
            workflow.set_entry_point("outline_refiner")
            workflow.add_edge("outline_refiner", "writer")
        else:
            workflow.set_entry_point("writer")

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

        self.workflow = workflow.compile()

    def _wrap_agent_invoke(self, agent, node_name: str):
        """包装 Agent.invoke（当前 Agents 仍使用旧 NovelState，后续逐步迁移）"""
        def invoke(state: PipelineState) -> PipelineState:
            agent.state = state
            agent._current_chapter = state.current_chapter

            try:
                result = agent.invoke(state)
            except Exception as e:
                print(f"  ❌ {node_name} 执行失败: {e}")
                state.error_message = f"{node_name} 失败: {str(e)}"
                return state

            self._save_checkpoint(result, node_name)
            self._last_node = node_name

            return result
        return invoke

    def _outline_refiner(self, state: PipelineState) -> PipelineState:
        """大纲细化阶段：生成章级细纲"""
        print(f"📝 大纲细化阶段：第{state.current_chapter}章")

        sm = get_storage_manager()
        meta = sm.load_novel_meta(state.novel_id)
        outline = sm.load_outline(state.novel_id)

        if not meta:
            print(f"  ⚠️ 小说不存在: {state.novel_id}")
            state.error_message = f"小说不存在: {state.novel_id}"
            return state

        if not self.outline_generator or not meta.novel_title:
            print(f"  ⚠️ 跳过细纲生成")
            return state

        try:
            from core.models.outline import ChapterOutline
            chapter_outline = self.outline_generator.generate_chapter_outline(
                novel_title=meta.novel_title,
                volume_outline=getattr(outline, 'volumes', {}).get((state.current_chapter-1)//10, ''),
                current_chapter=state.current_chapter,
                characters=None,
                target_words=meta.target_word_count
            )

            if not outline:
                from core.models.outline import Outline
                outline = Outline(novel_id=state.novel_id)

            if not hasattr(outline, 'chapter_outlines'):
                outline.chapter_outlines = {}
            outline.chapter_outlines[state.current_chapter] = chapter_outline
            sm.save_outline(state.novel_id, outline)

            print(f"  ✅ 第{state.current_chapter}章细纲生成完成")

        except Exception as e:
            print(f"  ❌ 细纲生成失败：{e}")
            state.error_message = f"大纲细化失败：{str(e)}"

        return state

    def _review_router(self, state: PipelineState) -> str:
        """审稿路由"""
        if state.error_message:
            print(f"❌ 错误：{state.error_message}")
            return "max_retries"

        sm = get_storage_manager()
        reviews = sm.load_reviews(state.novel_id)
        review = reviews.get(state.current_chapter)
        latest = review.get_latest() if review else None

        if state.review_round >= state.max_review_rounds:
            print(f"⚠️ 第{state.current_chapter}章审稿{state.review_round}轮未通过，强制进入校对")
            return "max_retries"

        if latest and hasattr(latest, 'verdict'):
            verdict = latest.verdict
            if hasattr(verdict, 'value'):
                verdict = verdict.value
            verdict = str(verdict).lower()

            if verdict == 'pass':
                print(f"✅ 第{state.current_chapter}章审稿通过，进入校对")
                return "approve"
            elif verdict == 'rewrite':
                print(f"🔄 第{state.current_chapter}章需要重写")
                return "rewrite"
            elif verdict == 'revise':
                print(f"📝 第{state.current_chapter}章需要修改，第{state.review_round + 1}轮")
                return "revise"

        if latest and hasattr(latest, 'total_score') and latest.total_score >= 85:
            print(f"✅ 第{state.current_chapter}章审稿通过（{latest.total_score}分），进入校对")
            return "approve"

        return "revise"

    def _proofread_router(self, state: PipelineState) -> str:
        """校对路由"""
        sm = get_storage_manager()
        proofreads = sm.load_proofreads(state.novel_id)
        proofread = proofreads.get(state.current_chapter)
        latest = proofread.get_latest() if proofread else None

        if latest and latest.passed:
            print(f"✅ 第{state.current_chapter}章校对通过，进入萃取阶段")
            return "pass"

        if state.review_round >= state.max_review_rounds + 2:
            print(f"⚠️ 第{state.current_chapter}章校对多次未通过，强制进入萃取阶段")
            return "pass"

        print(f"📝 第{state.current_chapter}章校对发现问题，返回修改")
        return "fail"

    def _knowledge_extractor(self, state: PipelineState) -> PipelineState:
        """知识萃取（阶段二）"""
        print(f"🔍 萃取第{state.current_chapter}章知识...")

        if not self.knowledge_extractor:
            state.current_stage = PipelineStage.EXTRACTION
            return state

        sm = get_storage_manager()
        chapters = sm.load_chapters(state.novel_id)
        chapter = chapters.get(state.current_chapter)

        if not chapter or not chapter.content:
            print(f"  ⚠️ 第{state.current_chapter}章没有内容，跳过萃取")
            state.current_stage = PipelineStage.EXTRACTION
            return state

        try:
            analysis = self.knowledge_extractor.extract(
                chapter=state.current_chapter,
                chapter_content=chapter.content
            )

            analyses = sm.load_analyses(state.novel_id)
            analyses[state.current_chapter] = analysis
            sm.save_analyses(state.novel_id, analyses)

            print(f"  ✅ 第{state.current_chapter}章知识萃取完成")

        except Exception as e:
            print(f"  ⚠️ 知识萃取失败: {e}")

        state.current_stage = PipelineStage.EXTRACTION
        return state

    def _ip_designer(self, state: PipelineState) -> PipelineState:
        """IP生成（阶段三）"""
        print(f"🎨 生成 IP 资产...")

        if not self.ip_generator:
            state.current_stage = PipelineStage.IP_GENERATION
            return state

        sm = get_storage_manager()
        chapters = sm.load_chapters(state.novel_id)
        analyses = sm.load_analyses(state.novel_id)
        meta = sm.load_novel_meta(state.novel_id)

        try:
            bible = self.ip_generator.generate(
                title=meta.novel_title if meta else "未命名小说",
                chapters=chapters,
                chapter_analyses=analyses
            )

            sm.save_story_bible(state.novel_id, bible)

            print(f"  ✅ IP 生成完成")

        except Exception as e:
            print(f"  ⚠️ IP 生成失败: {e}")

        state.current_stage = PipelineStage.IP_GENERATION
        return state

    def _save_checkpoint(self, state: PipelineState, node_name: str):
        """保存检查点（只通过 StorageManager 保存，不写旧格式）"""
        sm = get_storage_manager()
        meta = sm.load_novel_meta(state.novel_id)
        if meta:
            meta.current_chapter = state.current_chapter
            sm.save_novel_meta(state.novel_id, meta)
        state.last_node = node_name

        # 保存轻量运行时状态到独立文件（用于恢复）
        checkpoint_path = os.path.join(
            self.checkpoint_dir,
            f"pipeline_{state.novel_id}_ch{state.current_chapter}.json"
        )
        checkpoint = {
            "novel_id": state.novel_id,
            "current_chapter": state.current_chapter,
            "review_round": state.review_round,
            "max_review_rounds": state.max_review_rounds,
            "error_message": state.error_message,
            "should_pause": state.should_pause,
            "last_node": node_name,
        }
        try:
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint, f, ensure_ascii=False, indent=2)
            print(f"💾 Pipeline 检查点保存: {node_name}")
        except Exception as e:
            print(f"⚠️ 保存 pipeline 检查点失败: {e}")

    def load_checkpoint(self, novel_id: str, chapter: int) -> Optional[PipelineState]:
        """从 StorageManager 恢复状态"""
        sm = get_storage_manager()
        meta = sm.load_novel_meta(novel_id)
        if not meta:
            return None

        state = PipelineState(
            novel_id=novel_id,
            current_chapter=chapter,
        )

        checkpoint_path = os.path.join(
            self.checkpoint_dir,
            f"pipeline_{novel_id}_ch{chapter}.json"
        )
        if os.path.exists(checkpoint_path):
            try:
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    state.review_round = data.get('review_round', 0)
                    state.error_message = data.get('error_message', '')
                    state.last_node = data.get('last_node', '')
            except Exception as e:
                print(f"⚠️ 加载 pipeline 检查点失败: {e}")

        return state

    def resume(self, novel_id: str, chapter: int, from_node: Optional[str] = None) -> PipelineState:
        """从检查点恢复并继续执行"""
        state = self.load_checkpoint(novel_id, chapter)
        if not state:
            raise ValueError(f"无法恢复检查点: {novel_id} 第{chapter}章")

        resume_node = from_node or state.last_node
        if not resume_node:
            print("⚠️ 未指定恢复节点，从头开始")
            return self.run(state)

        print(f"🔄 从节点 '{resume_node}' 恢复执行")

        current_state = state
        node_map = {
            "outline_refiner": self._outline_refiner,
            "writer": lambda s: self._writer_agent.invoke(s) if self._writer_agent else s,
            "reviewer": lambda s: self._reviewer_agent.invoke(s) if self._reviewer_agent else s,
            "reviser": lambda s: self._reviser_agent.invoke(s) if self._reviser_agent else s,
            "proofreader": lambda s: self._proofreader_agent.invoke(s) if self._proofreader_agent else s,
            "knowledge_extractor": self._knowledge_extractor,
            "ip_designer": self._ip_designer
        }

        if resume_node not in node_map:
            print(f"⚠️ 未知节点 '{resume_node}'，从头开始")
            return self.run(state)

        for node_name in list(node_map.keys())[list(node_map.keys()).index(resume_node):]:
            print(f"▶️ 执行节点: {node_name}")
            try:
                current_state = node_map[node_name](current_state)
                self._save_checkpoint(current_state, node_name)
            except Exception as e:
                print(f"❌ 节点 {node_name} 执行失败: {e}")
                current_state.error_message = f"节点 {node_name} 失败: {str(e)}"
                break

        return current_state

    def list_checkpoints(self, novel_id: Optional[str] = None) -> list:
        """列出所有可用的检查点"""
        if not os.path.exists(self.checkpoint_dir):
            return []

        checkpoints = []
        for fname in os.listdir(self.checkpoint_dir):
            if fname.startswith('pipeline_') and fname.endswith('.json'):
                if novel_id and novel_id not in fname:
                    continue
                checkpoints.append(fname)

        return sorted(checkpoints)

    def run(self, initial_state: PipelineState) -> PipelineState:
        """运行 Pipeline（只通过 StorageManager 持久化）"""
        print(f"🚀 启动 StoryForge Pipeline")

        sm = get_storage_manager()
        meta = sm.load_novel_meta(initial_state.novel_id)
        if meta:
            print(f"📚 小说：{meta.novel_title}")
        print(f"🎯 目标：创作第{initial_state.current_chapter}章")

        if self.memory:
            char_graph = sm.load_characters(initial_state.novel_id)
            if char_graph:
                self.memory.initialize_from_outline(
                    characters=char_graph.characters,
                    world_setting=None
                )

        result = self.workflow.invoke(initial_state)

        self._save_checkpoint(result, "completed")

        print(f"\n✨ Pipeline 完成！")

        return result

    def run_batch(self, state: PipelineState, chapters: list) -> Dict[int, PipelineState]:
        """批量创作多章"""
        results = {}
        for chapter_num in chapters:
            state.current_chapter = chapter_num
            results[chapter_num] = self.run(state)
        return results

    def visualize(self):
        """可视化"""
        try:
            return self.workflow.get_graph().draw_mermaid()
        except:
            return "可视化需要安装 graphviz"


def create_pipeline(
    llm_client: Callable = None,
    use_memory: bool = True,
    use_outline_refinement: bool = True,
    use_message_bus: bool = True,
    use_agent_routing: bool = False,
    **kwargs
) -> NovelPipeline:
    """创建 Pipeline"""
    return NovelPipeline(
        llm_client=llm_client,
        use_memory=use_memory,
        use_outline_refinement=use_outline_refinement,
        use_message_bus=use_message_bus,
        use_agent_routing=use_agent_routing,
        **kwargs
    )
