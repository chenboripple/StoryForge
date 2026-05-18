"""
StoryForge - 创作 Agent
使用 PromptAssembler 动态组装 prompt，支持大纲细化和人味化规则
"""

from datetime import datetime
from typing import Optional

from core.agent import BaseAgent, AgentPersona
from core.context_orchestrator import ContextOrchestrator
from core.memory import StoryMemory
from core.schema import (
    ReviewResult, ProofreadResult, ChapterContent,
    REVIEW_JSON_PROMPT, PROOFREAD_JSON_PROMPT
)
from core.models import ChapterStatus
from core.prompt_assembler import PromptAssembler



# ==================== 角色人设（保持兼容） ====================

class MochuanPersona(AgentPersona):
    """墨川 - 小说家"""
    
    def __init__(self):
        super().__init__(
            name="墨川",
            role="职业小说家",
            goal="基于大纲创作高质量小说章节，保持人物一致性、情节张力和文学性",
            backstory="""曾是理论物理学博士，因一次实验事故放弃科研，转而用笔构建更可控的宇宙。
擅长将硬核科学概念转化为人类情感冲突。出版过3部长篇科幻，拿过银河奖。
相信好故事的本质是"在极端环境下测试人性"。""",
            expertise=[
                "科幻世界观构建",
                "人物心理刻画",
                "情节节奏控制",
                "硬科学概念通俗化",
                "长篇叙事结构"
            ],
            tone="冷峻理性，关键时刻爆发诗意。不写废话，每个场景必须推动剧情或揭示人物。",
            principles=[
                "人物行为必须符合其性格和动机",
                "每个场景至少包含一个冲突或转折",
                "展示而非告诉（Show, don't tell）",
                "对话要有个性，不能千人一面"
            ],
            constraints=[
                "严格遵循大纲设定，不擅自新增核心设定",
                "保持与已写章节的一致性",
                "每章字数控制在目标范围内"
            ]
        )


class QingfengPersona(AgentPersona):
    """青锋 - 文学编辑"""
    
    def __init__(self):
        super().__init__(
            name="青锋",
            role="资深文学编辑",
            goal="从叙事结构、人物一致性、文学性三个维度审稿，给出可执行的修改建议",
            backstory="""从业20年的文学编辑，经手过3部茅盾文学奖作品，退稿过500+部。
眼光毒辣，但改稿意见永远具体到位——不说"这里不好"，而是说"这里如果改成XXX会更有张力"。
最恨两种作者：一种是不改，一种是乱改。""",
            expertise=[
                "叙事结构分析",
                "人物一致性检查",
                "文学性评估",
                "出版标准把控",
                "市场敏感度"
            ],
            tone="犀利直接，对好文字不吝赞美，对问题一针见血。不寒暄，不客套。",
            principles=[
                "审稿意见必须具体，指出具体段落和问题",
                "评分标准：结构30%、人物30%、文字30%、市场潜力10%",
                "区分致命问题和优化建议"
            ],
            constraints=[
                "不修改作者原意，只提建议",
                "评分必须客观，不因个人偏好打极端分"
            ]
        )


class YanqingPersona(AgentPersona):
    """砚清 - 文字校对专家"""
    
    def __init__(self):
        super().__init__(
            name="砚清",
            role="文字校对专家",
            goal="消除所有文字错误、逻辑漏洞、设定矛盾，确保文本质量达到出版标准",
            backstory="""处女座，前出版社校对部主任，30年校对经验。
能一眼看出三百页手稿里"他"和"她"的混用，能记住第50章出现的配角名字并在第200章发现拼写不一致。
相信好作品是改出来的，但改的前提是"找到所有问题"。""",
            expertise=[
                "文字错误检测",
                "设定一致性检查",
                "逻辑漏洞发现",
                "标点规范",
                "前后文对照"
            ],
            tone="严谨细致，发现错误时略带得意。对马虎的作者零容忍。",
            principles=[
                "不放过任何一个错别字",
                "人物名字、设定必须全文一致",
                "时间线、地理位置不能自相矛盾",
                "标点符号使用规范"
            ],
            constraints=[
                "只改错误，不改风格",
                "不删减内容，只标记问题"
            ]
        )


def _extract_json(text):
    """从文本中提取 JSON 块"""
    import re
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        return match.group(1)
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    return text


class WriterAgent(BaseAgent):
    """墨川 - 写作节点（支持大纲细化和人味化）"""

    def __init__(
        self,
        llm_client=None,
        memory: StoryMemory = None,
        error_handler=None,
        prompt_assembler: PromptAssembler = None,
        message_bus=None,
        state=None
    ):
        super().__init__(
            persona=MochuanPersona(),
            llm_client=llm_client,
            memory=memory,
            error_handler=error_handler,
            use_json_mode=False,
            message_bus=message_bus,
            state=state
        )
        self.prompt_assembler = prompt_assembler or PromptAssembler()
        self.context_orchestrator = ContextOrchestrator()
    
    def invoke(self, state):
        """写作章节"""
        # 绑定 state 到 self（用于消息持久化）
        self.state = state
        self._current_chapter = state.current_chapter

        # 0. 渐进式披露加载上下文
        context_bundle = self.context_orchestrator.build_writer_bundle(
            state,
            memory_context=self._build_memory_context(state)
        )
        chapter_plan = context_bundle.get("chapter_plan")
        context = context_bundle.get("context", "")
        memory_context = context_bundle.get("memory_context", "")

        # 3. 使用 PromptAssembler 组装 prompt
        prompt = self.prompt_assembler.assemble_writer_prompt(
            persona=self.persona,
            chapter_plan=chapter_plan,
            context=context,
            memory_context=memory_context,
            humanization=True
        )

        # 4. 调用 LLM
        chapter_text = self._call_llm_raw(prompt)

        # 5. 一致性检查
        if self.memory:
            issues = self.memory.check_consistency(state.current_chapter, chapter_text)
            for issue in issues:
                if issue.severity == "error":
                    print(f"⚠️ 发现严重不一致：{issue.description}")
                    # 发布消息提醒其他 Agent
                    self.publish_message(
                        msg_type="warning",
                        content=f"写作时检测到严重不一致：{issue.description}，建议审稿时重点检查",
                        target="青锋",
                        chapter=state.current_chapter,
                        priority="high"
                    )

        # 6. 更新状态
        chapter_content = ChapterContent(
            text=chapter_text,
            version=1,
            word_count=len(chapter_text),
            generated_at=datetime.now().isoformat(),
            modified_at=datetime.now().isoformat()
        )

        state.chapters[state.current_chapter] = chapter_content

        state.chapter_status[state.current_chapter] = ChapterStatus.DRAFT
        state.review_round = 0

        # 7. 发布写作完成消息到 MessageBus
        self.publish_message(
            msg_type="info",
            content=f"第{state.current_chapter}章写作完成，字数：{len(chapter_text)}，请审稿",
            target="青锋",
            chapter=state.current_chapter
        )

        self._notify("chapter_written", {
            "chapter": state.current_chapter,
            "word_count": len(chapter_text)
        })

        return state

    def _get_messages_context(self, state):
        """获取来自其他 Agent 的消息作为上下文"""
        messages = self.get_messages_from_state(
            msg_type="suggestion",
            chapter=state.current_chapter,
            limit=5
        )
        if not messages:
            messages = self.get_messages_from_state(
                chapter=state.current_chapter,
                limit=5
            )
        if messages:
            parts = ["\n【来自其他 Agent 的反馈】"]
            for m in messages:
                parts.append(f"  [{m['sender']}] {m['msg_type']}: {m['content']}")
            return "\n".join(parts)
        return ""
    
    def _get_chapter_plan(self, state):
        """获取章节计划"""
        if hasattr(state, 'get_chapter_brief'):
            brief = state.get_chapter_brief(state.current_chapter)
            if brief:
                return brief

        # 优先从 creation.chapter_outlines 获取
        if hasattr(state, 'creation') and state.creation:
            outlines = state.creation.get('chapter_outlines', {})
            if state.current_chapter in outlines:
                return outlines[state.current_chapter]
        
        # 回退到 outline 字段
        if hasattr(state, 'outline') and state.outline:
            return {
                "chapter_id": state.current_chapter,
                "title": f"第{state.current_chapter}章",
                "theme": "",
                "plot": state.outline[:200] if state.outline else "",
                "words_target": state.target_word_count
            }
        
        return None
    
    def _build_writer_context(self, state):
        """构建写作用上下文"""
        parts = [
            f"【小说信息】\n标题：{state.novel_title}\n类型：{state.genre}\n",
            f"\n【大纲】\n{state.outline[:500] if state.outline else '暂无'}...\n",
            f"\n【当前章节】第{state.current_chapter}章\n",
            f"\n【角色设定】\n{self._format_characters(state.characters)}\n"
        ]
        
        recent = self._get_recent_chapters(state)
        if recent:
            parts.append(f"\n【最近章节】\n{recent}")
        
        return "\n".join(parts)
    
    def _call_llm_raw(self, prompt):
        """调用基类统一 LLM 入口"""
        return super()._call_llm_raw(
            prompt=prompt,
            json_mode=False,
            task="写作章节（使用动态Prompt）"
        )
    
    def _format_characters(self, characters):
        if not characters:
            return "暂无角色设定"
        return "\n".join([
            f"- {c.name}：{c.personality}\n  背景：{c.background[:100] if hasattr(c, 'background') else ''}..."
            for c in characters[:5]
        ])
    
    def _get_recent_chapters(self, state):
        recent = []
        for i in range(max(1, state.current_chapter - 2), state.current_chapter):
            if i in state.chapters:
                chapter_obj = state.chapters[i]
                content = getattr(chapter_obj, "text", chapter_obj)[:200]
                recent.append(f"第{i}章结尾：{content}...")
        return "\n".join(recent)


class ReviewerAgent(BaseAgent):
    """青锋 - 审稿节点（结构化输出 + AI味评估）"""

    def __init__(
        self,
        llm_client=None,
        memory: StoryMemory = None,
        error_handler=None,
        prompt_assembler: PromptAssembler = None,
        message_bus=None,
        state=None
    ):
        super().__init__(
            persona=QingfengPersona(),
            llm_client=llm_client,
            memory=memory,
            error_handler=error_handler,
            use_json_mode=True,
            message_bus=message_bus,
            state=state
        )
        self.prompt_assembler = prompt_assembler or PromptAssembler()
        self.context_orchestrator = ContextOrchestrator()

    def invoke(self, state):
        """审稿（结构化输出 + AI味评估 + Agent 间通信）"""
        self.state = state
        self._current_chapter = state.current_chapter

        chapter_obj = state.chapters.get(state.current_chapter, "")
        chapter_text = getattr(chapter_obj, "text", chapter_obj)
        if not chapter_text:
            state.error_message = f"第{state.current_chapter}章无内容可审"
            return state

        # 0. 渐进式披露加载审稿上下文
        context_bundle = self.context_orchestrator.build_reviewer_bundle(state, chapter_text)
        chapter_plan = context_bundle.get("chapter_plan") or self._get_chapter_plan(state)

        # 2. 使用 PromptAssembler 组装审稿 prompt
        prompt = self.prompt_assembler.assemble_reviewer_prompt(
            persona=self.persona,
            chapter_content=context_bundle.get("chapter_content", chapter_text),
            chapter_plan=chapter_plan,
            characters=context_bundle.get("characters", state.characters),
            previous_chapter=context_bundle.get("previous_chapter", self._get_previous_chapter(state)),
            extra_context=context_bundle.get("context", "")
        )

        # 3. 调用 LLM
        result_dict = self._call_llm_raw(prompt, json_mode=True)

        # 4. 解析结构化结果
        review = self._parse_review_result(result_dict)

        # 5. 更新状态
        self._update_state_with_review(state, review)

        # 5.1 反哺章节概述
        issue_dicts = []
        for issue in getattr(review, 'issues', []) or []:
            issue_dicts.append({
                "severity": getattr(issue, "severity", ""),
                "location": getattr(issue, "location", ""),
                "description": getattr(issue, "description", ""),
                "suggestion": getattr(issue, "suggestion", ""),
            })
        if hasattr(state, 'update_chapter_brief_from_feedback'):
            state.update_chapter_brief_from_feedback(
                chapter=state.current_chapter,
                summary=review.summary,
                issues=issue_dicts,
            )

        # 5.2 重写判定触发卷级提案
        if getattr(review.verdict, 'value', '') == 'rewrite' and hasattr(state, 'add_proposal'):
            state.add_proposal(
                target_layer="volume_brief",
                reason="审稿判定需重写，可能已偏离卷级目标",
                diff={
                    "chapter": state.current_chapter,
                    "review_summary": review.summary,
                    "critical_issues": issue_dicts[:5],
                },
                chapter=state.current_chapter,
                confidence=0.8,
                risk_level="medium",
            )

        # 6. Agent 自主路由建议（根据 verdict）
        if review.verdict.value == "pass":
            self.suggest_route(
                suggested_node="proofreader",
                reason="审稿通过，符合发布标准，建议进入校对阶段",
                confidence=0.9,
                chapter=state.current_chapter
            )
        elif review.verdict.value == "rewrite":
            self.suggest_route(
                suggested_node="writer",
                reason="需要重大重写，建议返回给墨川",
                confidence=0.85,
                chapter=state.current_chapter
            )
        else:
            self.suggest_route(
                suggested_node="reviser",
                reason="需要局部修改，建议返回给墨川",
                confidence=0.8,
                chapter=state.current_chapter
            )

        # 7. 发布详细的审稿消息
        issue_summary = ""
        if hasattr(review, 'issues') and review.issues:
            critical_count = sum(
                1 for i in review.issues
                if getattr(i, 'severity', '').upper() in ['S', 'CRITICAL', 'A']
            )
            issue_summary = f"，发现 {critical_count} 个严重问题"

        self.publish_message(
            msg_type="suggestion",
            content=f"第{state.current_chapter}章审稿完成：{review.summary}，总分{review.total_score}分{issue_summary}",
            target="墨川",
            chapter=state.current_chapter
        )

        self._notify("chapter_reviewed", {
            "chapter": state.current_chapter,
            "round": state.review_round,
            "score": review.total_score,
            "ai_flavor": review.ai_flavor_level if hasattr(review, 'ai_flavor_level') else "unknown",
            "verdict": review.verdict.value
        })

        return state
    
    def _call_llm_raw(self, prompt, json_mode=False):
        """调用基类统一 LLM 入口"""
        return super()._call_llm_raw(
            prompt=prompt,
            json_mode=json_mode,
            task="审稿（结构化输出）"
        )
    
    def _get_chapter_plan(self, state):
        """获取章节计划"""
        if hasattr(state, 'get_chapter_brief'):
            brief = state.get_chapter_brief(state.current_chapter)
            if brief:
                return brief

        if hasattr(state, 'creation') and state.creation:
            outlines = state.creation.get('chapter_outlines', {})
            if state.current_chapter in outlines:
                return outlines[state.current_chapter]
        return None
    
    def _get_previous_chapter(self, state):
        """获取前一章内容"""
        prev = state.current_chapter - 1
        if prev > 0 and prev in state.chapters:
            prev_chapter = state.chapters[prev]
            return getattr(prev_chapter, "text", prev_chapter)
        return ""
    
    def _parse_review_result(self, result_dict):
        """解析 JSON 结果为 ReviewResult 对象"""
        from core.models.review import DimensionScore, ReviewIssue, ReviewVerdict

        dimensions = [
            DimensionScore(**d) for d in result_dict.get("dimensions", [])
        ]
        issues = []
        for i in result_dict.get("issues", []):
            issue_data = i.copy()
            if "type" in issue_data and "issue_type" not in issue_data:
                issue_data["issue_type"] = issue_data.pop("type")
            issues.append(ReviewIssue(**issue_data))
        verdict = ReviewVerdict(result_dict.get("verdict", "revise"))

        review = ReviewResult(
            total_score=result_dict.get("total_score", 70),
            dimensions=dimensions,
            issues=issues,
            verdict=verdict,
            summary=result_dict.get("summary", "")
        )
        
        # 添加 AI味评估
        ai_flavor = result_dict.get("ai_flavor", {})
        review.ai_flavor_score = ai_flavor.get("score", 5)
        review.ai_flavor_level = ai_flavor.get("level", "medium")
        
        return review
    
    def _update_state_with_review(self, state, review):
        """将审稿结果更新到状态"""
        from core.state import ReviewRecord
        from core.models import ChapterStatus
        
        record = ReviewRecord(
            round=state.review_round + 1,
            reviewer=self.persona.name,
            score=review.total_score,
            comments=review.summary,
            passed=review.verdict.value == "pass",
            timestamp=datetime.now().isoformat()
        )
        
        # 结构化数据存到新字段
        if not hasattr(state, 'structured_reviews'):
            state.structured_reviews = {}
        state.structured_reviews.setdefault(state.current_chapter, []).append(review)
        
        # 兼容旧接口
        if state.current_chapter not in state.reviews:
            state.reviews[state.current_chapter] = []
        state.reviews[state.current_chapter].append(record)
        
        state.review_round += 1
        
        # 更新状态
        if review.verdict.value == "pass":
            state.chapter_status[state.current_chapter] = ChapterStatus.APPROVED
        elif review.verdict.value == "rewrite":
            state.chapter_status[state.current_chapter] = ChapterStatus.PENDING
        else:
            state.chapter_status[state.current_chapter] = ChapterStatus.IN_REVIEW


class ReviserAgent(BaseAgent):
    """修改节点"""

    def __init__(
        self,
        llm_client=None,
        memory: StoryMemory = None,
        error_handler=None,
        prompt_assembler: PromptAssembler = None,
        message_bus=None,
        state=None
    ):
        super().__init__(
            persona=MochuanPersona(),
            llm_client=llm_client,
            memory=memory,
            error_handler=error_handler,
            use_json_mode=False,
            message_bus=message_bus,
            state=state
        )
        self.prompt_assembler = prompt_assembler or PromptAssembler()
        self.context_orchestrator = ContextOrchestrator()

    def invoke(self, state):
        """根据审稿意见修改（支持 MessageBus 消息反馈）"""
        self.state = state
        self._current_chapter = state.current_chapter

        chapter_obj = state.chapters.get(state.current_chapter, "")
        chapter_text = getattr(chapter_obj, "text", chapter_obj)
        latest = state.get_latest_review()

        if not latest:
            state.error_message = "无审稿记录，无法修改"
            return state

        # 1. 获取结构化审稿结果
        structured_review = None
        if hasattr(state, 'structured_reviews') and state.current_chapter in state.structured_reviews:
            structured_review = state.structured_reviews[state.current_chapter][-1]

        # 2. 渐进式披露加载修改上下文
        context_bundle = self.context_orchestrator.build_reviser_bundle(
            state,
            chapter_text,
            latest,
            structured_review,
        )
        context = context_bundle.get("context", "")

        # 3. 使用 PromptAssembler 组装修改 prompt
        prompt = self.prompt_assembler.assemble_writer_prompt(
            persona=self.persona,
            chapter_plan=state.get_chapter_brief(state.current_chapter) if hasattr(state, 'get_chapter_brief') else None,
            context=context,
            memory_context=context_bundle.get("memory_context", ""),
            humanization=True
        )

        # 4. 调用 LLM
        revised_text = self._call_llm_raw(prompt)

        # 5. 更新状态
        from core.models import ChapterStatus
        from core.schema import ChapterContent

        state.chapters[state.current_chapter] = ChapterContent(
            text=revised_text,
            version=state.review_round + 1,
            word_count=len(revised_text),
            modified_at=datetime.now().isoformat()
        )
        state.chapter_status[state.current_chapter] = ChapterStatus.REVISING

        # 6. 发布修改完成消息
        self.publish_message(
            msg_type="info",
            content=f"第{state.current_chapter}章修改完成（第{state.review_round}轮），请重新审稿",
            target="青锋",
            chapter=state.current_chapter
        )

        self._notify("chapter_revised", {
            "chapter": state.current_chapter,
            "round": state.review_round
        })

        return state
    
    def _build_reviser_context(self, state, chapter_text, latest, structured_review=None):
        """构建修改上下文"""
        parts = [
            f"【当前章节内容】\n{chapter_text}\n",
            f"\n【编辑审稿意见】\n{latest.comments}\n",
            f"\n【历史修改轮次】{state.review_round}轮"
        ]
        
        # 如果有结构化审稿结果，添加可执行建议
        if structured_review and hasattr(structured_review, 'issues'):
            parts.append("\n【可执行修改建议】")
            for issue in structured_review.issues:
                severity = getattr(issue, 'severity', 'B')
                if severity in ['S', 'A']:  # 只显示必须改的建议
                    parts.append(f"  [{severity}] {getattr(issue, 'location', '')}: {getattr(issue, 'description', '')}")
                    if hasattr(issue, 'suggestion'):
                        parts.append(f"    建议：{issue.suggestion}")
        
        return "\n".join(parts)
    
    def _call_llm_raw(self, prompt):
        return super()._call_llm_raw(
            prompt=prompt,
            json_mode=False,
            task="根据审稿意见修改"
        )


class ProofreaderAgent(BaseAgent):
    """砚清 - 校对节点（结构化输出 + 终审 + Agent 间通信）"""

    def __init__(
        self,
        llm_client=None,
        memory: StoryMemory = None,
        error_handler=None,
        prompt_assembler: PromptAssembler = None,
        message_bus=None,
        state=None
    ):
        super().__init__(
            persona=YanqingPersona(),
            llm_client=llm_client,
            memory=memory,
            error_handler=error_handler,
            use_json_mode=True,
            message_bus=message_bus,
            state=state
        )
        self.prompt_assembler = prompt_assembler or PromptAssembler()
        self.context_orchestrator = ContextOrchestrator()

    def invoke(self, state):
        """校对（结构化输出 + 终审 + Agent 间通信）"""
        self.state = state
        self._current_chapter = state.current_chapter

        chapter_obj = state.chapters.get(state.current_chapter, "")
        chapter_text = getattr(chapter_obj, "text", chapter_obj)

        scope = getattr(state, "proofread_scope", "chapter")
        proofread_context = getattr(state, "proofread_context", {}) or {}

        # 0. 渐进式披露加载校对上下文
        context_bundle = self.context_orchestrator.build_proofreader_bundle(state, chapter_text)

        # 1. 使用 PromptAssembler 组装校对 prompt
        prompt = self.prompt_assembler.assemble_proofreader_prompt(
            persona=self.persona,
            chapter_content=context_bundle.get("chapter_content", chapter_text),
            characters=context_bundle.get("characters", state.characters),
            world_setting=context_bundle.get("world_setting", proofread_context.get("world_setting")),
            scope=context_bundle.get("scope", scope),
            project_docs=context_bundle.get("project_docs") if context_bundle.get("scope", scope) == "project_docs" else None,
            extra_context=context_bundle.get("context", "")
        )

        # 2. 调用 LLM
        result_dict = self._call_llm_raw(prompt, json_mode=True)

        # 3. 解析结果
        proofread = self._parse_proofread_result(result_dict)

        # 4. 更新状态
        self._update_state_with_proofread(state, proofread)

        # 4.1 校对反馈反哺到章节概述
        issue_dicts = []
        for issue in getattr(proofread, 'issues', []) or []:
            issue_dicts.append({
                "severity": getattr(issue, "severity", ""),
                "location": getattr(issue, "location", ""),
                "description": getattr(issue, "explanation", ""),
                "suggestion": getattr(issue, "correction", ""),
                "type": getattr(issue, "issue_type", ""),
            })
        if hasattr(state, 'update_chapter_brief_from_feedback'):
            state.update_chapter_brief_from_feedback(
                chapter=state.current_chapter,
                summary=getattr(proofread, 'summary', ''),
                issues=issue_dicts,
            )

        severe_setting_issues = [
            i for i in issue_dicts
            if str(i.get("severity", "")).upper() in {"S", "A", "CRITICAL"}
            and any(k in str(i.get("description", "")).lower() for k in ["设定", "时间", "world", "timeline", "角色"])
        ]
        if severe_setting_issues and hasattr(state, 'add_proposal'):
            state.add_proposal(
                target_layer="world_or_character",
                reason="校对发现高风险设定冲突，需跨层确认",
                diff={
                    "chapter": state.current_chapter,
                    "issues": severe_setting_issues[:5],
                },
                chapter=state.current_chapter,
                confidence=0.85,
                risk_level="high",
            )

        # 5. Agent 自主路由建议（根据终审结果）
        verdict = proofread.verdict if hasattr(proofread, 'verdict') else "需返修"
        if verdict == "可发布":
            self.suggest_route(
                suggested_node="knowledge_extractor",
                reason="终审通过，质量达标，建议进入萃取阶段",
                confidence=0.95,
                chapter=state.current_chapter
            )
        elif verdict == "可交付":
            self.suggest_route(
                suggested_node="knowledge_extractor",
                reason="终审通过，质量合格，建议进入萃取阶段",
                confidence=0.85,
                chapter=state.current_chapter
            )
        else:
            self.suggest_route(
                suggested_node="reviser",
                reason="终审发现问题，需要返修",
                confidence=0.9,
                chapter=state.current_chapter
            )

        # 6. 发布校对消息
        issue_count = len(proofread.issues) if hasattr(proofread, 'issues') else 0
        self.publish_message(
            msg_type="info",
            content=f"第{state.current_chapter}章校对完成：{verdict}，发现{issue_count}个问题",
            target="墨川",
            chapter=state.current_chapter
        )

        self._notify("chapter_proofread", {
            "chapter": state.current_chapter,
            "passed": proofread.passed,
            "verdict": verdict
        })

        return state
    
    def _call_llm_raw(self, prompt, json_mode=False):
        return super()._call_llm_raw(
            prompt=prompt,
            json_mode=json_mode,
            task="校对（结构化输出 + 终审）"
        )
    
    def _parse_proofread_result(self, result_dict):
        from core.models.proofread import ProofreadIssue

        issues = []
        for i in result_dict.get("issues", []):
            issue_data = i.copy()
            if "type" in issue_data and "issue_type" not in issue_data:
                issue_data["issue_type"] = issue_data.pop("type")
            issues.append(ProofreadIssue(**issue_data))

        proofread = ProofreadResult(
            passed=result_dict.get("passed", False),
            issues=issues,
            summary=result_dict.get("summary", "")
        )

        # 添加终审判定
        proofread.verdict = result_dict.get("verdict", "需返修")

        return proofread
    
    def _update_state_with_proofread(self, state, proofread):
        from core.state import ReviewRecord
        from core.models import ChapterStatus

        state.proofread_results.setdefault(state.current_chapter, []).append(proofread)

        if proofread.passed:
            state.chapter_status[state.current_chapter] = ChapterStatus.APPROVED
        else:
            state.chapter_status[state.current_chapter] = ChapterStatus.PROOFREADING
            record = ReviewRecord(
                round=state.review_round + 1,
                reviewer=self.persona.name,
                score=80 if proofread.passed else 50,
                comments=proofread.summary,
                passed=proofread.passed,
                timestamp=datetime.now().isoformat()
            )
            state.reviews.setdefault(state.current_chapter, []).append(record)
