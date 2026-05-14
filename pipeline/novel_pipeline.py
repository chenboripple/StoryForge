"""
StoryForge - Pipeline
卷纲规划 → 章纲规划 → 写作 → 审稿 → 修订 → 校对 → 反馈反哺 → 萃取 → IP 生成
"""

from langgraph.graph import StateGraph, END
from typing import Dict, Callable, Any, Optional, List
import json
import os
from collections import Counter

# 引入旧状态的所有字段用于兼容
from core.state import NovelState

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
from stages.outline.progressive_planner import ProgressivePlanner
from stages.video_script.video_script_generator import VideoScriptGenerator
from stages.video_bible.visual_bible_builder import VisualBibleBuilder
from stages.video_assets.video_asset_generator import VideoAssetGenerator
from stages.video_generation.video_generator import VideoGenerator
from core.video import (
    StubImageProvider,
    StubVideoProvider,
    StubEmbeddingProvider,
    VideoConsistencyService,
)
from core.models.video_assets import VideoState
from core.proposal_manager import ProposalManager

# 使用单一状态模型，避免 PipelineState 与 NovelState 漂移。
PipelineState = NovelState


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
        use_video_generation: bool = False,
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
        self.use_video_generation = use_video_generation
        self.use_message_bus = use_message_bus
        self.use_agent_routing = use_agent_routing
        self.checkpoint_dir = checkpoint_dir or ".checkpoints"
        self.ip_output_dir = ip_output_dir
        self.memory: Optional[StoryMemory] = None
        self.prompt_assembler: Optional[PromptAssembler] = None
        self.outline_generator: Optional[OutlineGenerator] = None
        self.progressive_planner: Optional[ProgressivePlanner] = None
        self.knowledge_extractor: Optional[KnowledgeExtractor] = None
        self.ip_generator: Optional[IPGenerator] = None
        self.video_script_generator: Optional[VideoScriptGenerator] = None
        self.visual_bible_builder: Optional[VisualBibleBuilder] = None
        self.video_asset_generator: Optional[VideoAssetGenerator] = None
        self.video_generator: Optional[VideoGenerator] = None
        self.video_consistency_service: Optional[VideoConsistencyService] = None
        self.proposal_manager: Optional[ProposalManager] = None
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
        self.progressive_planner = ProgressivePlanner(self.llm_client)
        self.error_handler = ErrorHandler()
        self.proposal_manager = ProposalManager()

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

        if self.use_video_generation:
            image_provider = StubImageProvider()
            video_provider = StubVideoProvider()
            embedding_provider = StubEmbeddingProvider()
            self.video_script_generator = VideoScriptGenerator()
            self.visual_bible_builder = VisualBibleBuilder()
            self.video_asset_generator = VideoAssetGenerator(image_provider=image_provider)
            self.video_generator = VideoGenerator(video_provider=video_provider)
            self.video_consistency_service = VideoConsistencyService(
                embedding_provider=embedding_provider
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

        workflow = StateGraph(NovelState)

        workflow.add_node("volume_planner", self._volume_planner)
        workflow.add_node("chapter_planner", self._chapter_planner)

        workflow.add_node("writer", self._wrap_agent_invoke(self._writer_agent, "writer"))
        workflow.add_node("reviewer", self._wrap_agent_invoke(self._reviewer_agent, "reviewer"))
        workflow.add_node("reviser", self._wrap_agent_invoke(self._reviser_agent, "reviser"))
        workflow.add_node("proofreader", self._wrap_agent_invoke(self._proofreader_agent, "proofreader"))
        workflow.add_node("feedback_synthesizer", self._feedback_synthesizer)
        workflow.add_node("knowledge_extractor", self._knowledge_extractor)
        workflow.add_node("ip_designer", self._ip_designer)
        workflow.add_node("video_script", self._video_script)
        workflow.add_node("visual_bible", self._visual_bible)
        workflow.add_node("video_assets", self._video_assets)
        workflow.add_node("video_consistency", self._video_consistency)
        workflow.add_node("video_generate", self._video_generate)

        if self.use_outline_refinement:
            workflow.set_entry_point("volume_planner")
            workflow.add_edge("volume_planner", "chapter_planner")
        else:
            workflow.set_entry_point("chapter_planner")

        workflow.add_edge("chapter_planner", "writer")

        workflow.add_edge("writer", "reviewer")

        workflow.add_conditional_edges(
            "reviewer",
            self._review_router,
            {
                "approve": "proofreader",
                "revise": "reviser",
                "rewrite": "chapter_planner",
                "max_retries": "proofreader"
            }
        )

        workflow.add_edge("reviser", "reviewer")

        workflow.add_conditional_edges(
            "proofreader",
            self._proofread_router,
            {
                "pass": "feedback_synthesizer",
                "fail": "reviser"
            }
        )

        workflow.add_edge("feedback_synthesizer", "knowledge_extractor")

        workflow.add_edge("knowledge_extractor", "ip_designer")

        workflow.add_conditional_edges(
            "ip_designer",
            self._post_ip_router,
            {
                "video": "video_script",
                "end": END,
            }
        )

        workflow.add_edge("video_script", "visual_bible")
        workflow.add_edge("visual_bible", "video_assets")
        workflow.add_edge("video_assets", "video_consistency")
        workflow.add_conditional_edges(
            "video_consistency",
            self._video_consistency_router,
            {
                "retry_assets": "video_assets",
                "render": "video_generate",
            }
        )
        workflow.add_edge("video_generate", END)

        self.workflow = workflow.compile()

    def _volume_planner(self, state: NovelState) -> NovelState:
        """卷纲规划：按当前章节所属卷生成/更新 volume brief。"""
        if not self.progressive_planner:
            return state

        volume_id = ((state.current_chapter - 1) // 10) + 1
        existing = state.volume_briefs.get(volume_id)
        brief = self.progressive_planner.generate_volume_brief(
            book_outline=state.outline,
            volume_id=volume_id,
            current_chapter=state.current_chapter,
            existing_brief=existing,
        )
        state.volume_briefs[volume_id] = brief
        if isinstance(state.volume_outline, dict):
            state.volume_outline[volume_id] = brief.get("summary", "")
        if isinstance(state.creation, dict):
            state.creation["volume_briefs"] = state.volume_briefs
        return state

    def _chapter_planner(self, state: NovelState) -> NovelState:
        """章节规划：基于卷纲和邻章概述生成当前章 chapter brief。"""
        if not self.progressive_planner:
            return state

        chapter = state.current_chapter
        volume_id = ((chapter - 1) // 10) + 1
        volume_brief = state.volume_briefs.get(volume_id, {})

        neighbors = []
        for c in [chapter - 2, chapter - 1, chapter + 1, chapter + 2]:
            if c <= 0:
                continue
            brief = state.get_chapter_brief(c)
            if brief:
                neighbors.append({"chapter": c, "brief": brief})

        brief = self.progressive_planner.generate_chapter_brief(
            book_outline=state.outline,
            volume_brief=volume_brief,
            chapter_id=chapter,
            target_words=state.target_word_count,
            neighbors=neighbors,
        )
        state.set_chapter_brief(chapter, brief)
        return state

    def _feedback_synthesizer(self, state: NovelState) -> NovelState:
        """将审稿/校对反馈反哺到 chapter brief，并生成跨层提案。"""
        chapter = state.current_chapter
        summary_parts: List[str] = []
        issue_items: List[Dict[str, Any]] = []

        if chapter in state.structured_reviews and state.structured_reviews[chapter]:
            latest_review = state.structured_reviews[chapter][-1]
            if hasattr(latest_review, "summary"):
                summary_parts.append(str(getattr(latest_review, "summary", "")))
            for issue in getattr(latest_review, "issues", []) or []:
                issue_items.append({
                    "severity": getattr(issue, "severity", ""),
                    "location": getattr(issue, "location", ""),
                    "description": getattr(issue, "description", ""),
                    "suggestion": getattr(issue, "suggestion", ""),
                })

        if chapter in state.proofread_results and state.proofread_results[chapter]:
            latest_pf = state.proofread_results[chapter][-1]
            summary_parts.append(str(getattr(latest_pf, "summary", "")))
            for issue in getattr(latest_pf, "issues", []) or []:
                issue_items.append({
                    "severity": getattr(issue, "severity", ""),
                    "location": getattr(issue, "location", ""),
                    "description": getattr(issue, "explanation", ""),
                    "suggestion": getattr(issue, "correction", ""),
                    "type": getattr(issue, "issue_type", ""),
                })

        summary_text = "\n".join([s for s in summary_parts if s])[:800]
        state.update_chapter_brief_from_feedback(
            chapter=chapter,
            summary=summary_text,
            issues=issue_items,
        )

        # 跨层提案：严重设定类问题不直接改高层，先入 proposal。
        severe = [i for i in issue_items if str(i.get("severity", "")).upper() in {"S", "A", "CRITICAL"}]
        if severe:
            setting_related = [
                i for i in severe
                if any(k in (str(i.get("description", "")) + str(i.get("type", ""))).lower()
                       for k in ["设定", "时间线", "timeline", "world", "角色", "character"])
            ]
            if setting_related:
                state.add_proposal(
                    target_layer="volume_or_world",
                    reason="章节评估发现高风险跨层冲突，需规划层确认",
                    diff={
                        "chapter": chapter,
                        "issues": setting_related[:5],
                    },
                    chapter=chapter,
                    confidence=0.82,
                    risk_level="high",
                )

                if self.proposal_manager:
                    self.proposal_manager.review_pending(state)

        return state

    def _wrap_agent_invoke(self, agent, node_name: str):
        """包装 Agent.invoke（当前 Agents 仍使用旧 NovelState，后续逐步迁移）"""
        def invoke(state: NovelState) -> NovelState:
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

    def _outline_refiner(self, state: NovelState) -> NovelState:
        """兼容旧节点名：转发到新的分层规划。"""
        state = self._volume_planner(state)
        state = self._chapter_planner(state)
        return state

    def _review_router(self, state: NovelState) -> str:
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

    def _proofread_router(self, state: NovelState) -> str:
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

    def _knowledge_extractor(self, state: NovelState) -> NovelState:
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

    def _ip_designer(self, state: NovelState) -> NovelState:
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

    def _post_ip_router(self, state: NovelState) -> str:
        """IP 阶段后路由：是否进入视频生成"""
        if self.use_video_generation and state.video_enabled:
            return "video"
        return "end"

    def _video_script(self, state: NovelState) -> NovelState:
        """生成镜头级视频剧本"""
        print("🎞️ 生成视频剧本...")
        state.current_stage = PipelineStage.VIDEO_GENERATION

        if not self.video_script_generator:
            return state

        sm = get_storage_manager()
        chapters = sm.load_chapters(state.novel_id)
        meta = sm.load_novel_meta(state.novel_id)

        script = self.video_script_generator.generate(
            novel_id=state.novel_id,
            title=meta.novel_title if meta else state.novel_id,
            chapters=chapters,
        )
        sm.save_video_script(state.novel_id, script)

        video_state = sm.load_video_state(state.novel_id) or VideoState(novel_id=state.novel_id)
        video_state.script = script
        video_state.status = "scripted"
        sm.save_video_state(state.novel_id, video_state)

        state.video_state_status = "scripted"
        state.video_script_id = f"{state.novel_id}:video_script"
        return state

    def _visual_bible(self, state: NovelState) -> NovelState:
        """生成视觉圣经（角色一致性/场景稳定规则）"""
        print("🖼️ 构建视觉圣经...")

        if not self.visual_bible_builder:
            return state

        sm = get_storage_manager()
        script = sm.load_video_script(state.novel_id)
        chars = sm.load_characters(state.novel_id)
        if not script:
            state.error_message = "缺少视频剧本，无法构建视觉圣经"
            return state

        bible = self.visual_bible_builder.build(state.novel_id, script, chars)
        sm.save_visual_bible(state.novel_id, bible)

        video_state = sm.load_video_state(state.novel_id) or VideoState(novel_id=state.novel_id)
        video_state.visual_bible = bible
        video_state.status = "bibled"
        sm.save_video_state(state.novel_id, video_state)

        state.video_state_status = "bibled"
        state.visual_bible_id = f"{state.novel_id}:visual_bible"
        return state

    def _video_assets(self, state: NovelState) -> NovelState:
        """生成角色/场景/镜头参考资产"""
        print("🎨 生成视频资产...")

        if not self.video_asset_generator:
            return state

        sm = get_storage_manager()
        script = sm.load_video_script(state.novel_id)
        bible = sm.load_visual_bible(state.novel_id)
        if not script or not bible:
            state.error_message = "缺少视频剧本或视觉圣经，无法生成资产"
            return state

        manifest = self.video_asset_generator.generate(state.novel_id, script, bible)
        sm.save_visual_bible(state.novel_id, bible)
        sm.save_video_manifest(state.novel_id, manifest)

        video_state = sm.load_video_state(state.novel_id) or VideoState(novel_id=state.novel_id)
        video_state.visual_bible = bible
        video_state.manifest = manifest
        video_state.status = "asseted"
        sm.save_video_state(state.novel_id, video_state)

        state.video_state_status = "asseted"
        state.video_manifest_id = f"{state.novel_id}:video_manifest"
        return state

    def _video_consistency(self, state: NovelState) -> NovelState:
        """一致性校验（规则 + embedding）"""
        print("🧪 校验视频一致性...")

        if not self.video_consistency_service:
            return state

        sm = get_storage_manager()
        bible = sm.load_visual_bible(state.novel_id)
        manifest = sm.load_video_manifest(state.novel_id)
        if not bible or not manifest:
            state.error_message = "缺少视觉圣经或资产索引，无法做一致性校验"
            return state

        report = self.video_consistency_service.validate(state.novel_id, bible, manifest)
        sm.save_video_consistency_report(state.novel_id, report)

        video_state = sm.load_video_state(state.novel_id) or VideoState(novel_id=state.novel_id)
        video_state.consistency_report = report
        video_state.error_message = "\n".join(report.fallback_reasons) if report.fallback_reasons else ""
        video_state.status = "asseted" if report.passed else "failed"
        sm.save_video_state(state.novel_id, video_state)

        return state

    def _video_consistency_router(self, state: NovelState) -> str:
        """一致性失败时自动回退到资产重建"""
        sm = get_storage_manager()
        report = sm.load_video_consistency_report(state.novel_id)
        if report and not report.passed and state.video_retry_count < state.video_max_retries:
            reasons = list(report.fallback_reasons or [])
            state.video_fallback_reasons = reasons
            if reasons:
                state.error_message = " | ".join(reasons)
            state.video_retry_count += 1
            print(
                f"♻️ 一致性未通过，回退重建资产（第{state.video_retry_count}次）"
                f"，原因: {state.error_message or '指标低于阈值'}"
            )
            return "retry_assets"
        if report and not report.passed:
            state.video_fallback_reasons = list(report.fallback_reasons or [])
            if state.video_fallback_reasons:
                state.error_message = " | ".join(state.video_fallback_reasons)
        return "render"

    def _video_generate(self, state: NovelState) -> NovelState:
        """生成最终视频"""
        print("🎬 生成最终视频...")

        if not self.video_generator:
            state.current_stage = PipelineStage.COMPLETED
            return state

        sm = get_storage_manager()
        script = sm.load_video_script(state.novel_id)
        manifest = sm.load_video_manifest(state.novel_id)
        if not script or not manifest:
            state.error_message = "缺少剧本或资产索引，无法生成视频"
            return state

        plan = self.video_generator.build_render_plan(state.novel_id, script, manifest)
        output = self.video_generator.generate(script, plan, manifest)

        sm.save_video_render_plan(state.novel_id, plan)
        sm.save_video_output(state.novel_id, output)

        video_state = sm.load_video_state(state.novel_id) or VideoState(novel_id=state.novel_id)
        video_state.render_plan = plan
        video_state.output = output
        video_state.status = "rendered"
        sm.save_video_state(state.novel_id, video_state)

        state.video_state_status = "rendered"
        state.video_render_plan_id = f"{state.novel_id}:video_render_plan"
        state.video_output_id = f"{state.novel_id}:video_output"
        state.current_stage = PipelineStage.COMPLETED
        return state

    def _save_checkpoint(self, state: NovelState, node_name: str):
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
            "chapter_briefs": state.chapter_briefs,
            "volume_briefs": state.volume_briefs,
            "context_decisions": state.context_decisions,
            "proposals": state.proposals,
            "canonical_versions": state.canonical_versions,
        }
        try:
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(checkpoint, f, ensure_ascii=False, indent=2)
            print(f"💾 Pipeline 检查点保存: {node_name}")
        except Exception as e:
            print(f"⚠️ 保存 pipeline 检查点失败: {e}")

    def load_checkpoint(self, novel_id: str, chapter: int) -> Optional[NovelState]:
        """从 StorageManager 恢复状态"""
        sm = get_storage_manager()
        meta = sm.load_novel_meta(novel_id)
        if not meta:
            return None

        state = NovelState(
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
                    state.chapter_briefs = {
                        int(k): v for k, v in (data.get('chapter_briefs', {}) or {}).items()
                    }
                    state.volume_briefs = {
                        int(k): v for k, v in (data.get('volume_briefs', {}) or {}).items()
                    }
                    state.context_decisions = list(data.get('context_decisions', []) or [])
                    state.proposals = list(data.get('proposals', []) or [])
                    state.canonical_versions = dict(data.get('canonical_versions', {}) or state.canonical_versions)
            except Exception as e:
                print(f"⚠️ 加载 pipeline 检查点失败: {e}")

        return state

    def resume(self, novel_id: str, chapter: int, from_node: Optional[str] = None) -> NovelState:
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
            "volume_planner": self._volume_planner,
            "chapter_planner": self._chapter_planner,
            "outline_refiner": self._outline_refiner,
            "writer": lambda s: self._writer_agent.invoke(s) if self._writer_agent else s,
            "reviewer": lambda s: self._reviewer_agent.invoke(s) if self._reviewer_agent else s,
            "reviser": lambda s: self._reviser_agent.invoke(s) if self._reviser_agent else s,
            "proofreader": lambda s: self._proofreader_agent.invoke(s) if self._proofreader_agent else s,
            "feedback_synthesizer": self._feedback_synthesizer,
            "knowledge_extractor": self._knowledge_extractor,
            "ip_designer": self._ip_designer,
            "video_script": self._video_script,
            "visual_bible": self._visual_bible,
            "video_assets": self._video_assets,
            "video_consistency": self._video_consistency,
            "video_generate": self._video_generate,
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

    def run(self, initial_state: NovelState) -> NovelState:
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

        result_data = self.workflow.invoke(initial_state)

        # 将 LangGraph 返回的 dict 转换回 NovelState 对象
        if isinstance(result_data, dict):
            # 从字典安全构造，自动过滤不在 dataclass 中的字段
            valid_fields = {f.name for f in NovelState.__dataclass_fields__.values()}
            filtered = {k: v for k, v in result_data.items() if k in valid_fields}
            result = NovelState(**filtered)
        else:
            result = result_data

        self._save_checkpoint(result, "completed")

        print(f"\n✨ Pipeline 完成！")

        return result

    def run_batch(self, state: NovelState, chapters: list) -> Dict[int, NovelState]:
        """批量创作多章"""
        results = {}
        for chapter_num in chapters:
            chapter_state = state.copy()
            chapter_state.current_chapter = chapter_num
            results[chapter_num] = self.run(chapter_state)
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
