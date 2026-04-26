"""
StoryForge - 重构后的创作 Agent
改进点：
1. 结构化输出（JSON）
2. 记忆系统集成
3. 错误处理
"""

from datetime import datetime

from core.agent_v2 import BaseAgent, AgentPersona
from core.memory import StoryMemory
from core.schema import (
    ReviewResult, ProofreadResult, ChapterContent,
    REVIEW_JSON_PROMPT, PROOFREAD_JSON_PROMPT
)
from core.utils.errors import with_error_handler


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
眼光毒辣，但改稿意见永远具体到位——不说"这里不好"，而是说"这里如果改成XXX会更张力"。
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
                "区分'致命问题'和'优化建议'"
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


# ==================== Agent 实现 ====================

class WriterAgent(BaseAgent):
    """墨川 - 写作节点"""
    
    def __init__(
        self,
        llm_client=None,
        memory: StoryMemory = None,
        error_handler=None
    ):
        super().__init__(
            persona=MochuanPersona(),
            llm_client=llm_client,
            memory=memory,
            error_handler=error_handler,
            use_json_mode=False
        )
    
    def invoke(self, state):
        """写作章节"""
        
        # 1. 构建上下文（包括记忆）
        context = self._build_writer_context(state)
        
        # 2. 构建任务
        task = f"""请创作第{state.current_chapter}章，目标字数{state.target_word_count}字。

要求：
1. 严格遵循大纲中本章的情节安排
2. 保持人物性格和动机的一致性
3. 与上一章衔接自然
4. 至少包含一个冲突或转折
5. 结尾留悬念或钩子

请直接输出章节正文，不需要标题和章节号。"""
        
        # 3. 调用 LLM
        chapter_text = self._call_llm(task, context)
        
        # 4. 一致性检查
        if self.memory:
            issues = self.memory.check_consistency(state.current_chapter, chapter_text)
            for issue in issues:
                if issue.severity == "error":
                    print(f"⚠️ 发现严重不一致：{issue.description}")
        
        # 5. 更新状态
        from core.state import ChapterStatus
        chapter_content = ChapterContent(
            text=chapter_text,
            version=1,
            word_count=len(chapter_text),
            generated_at=datetime.now().isoformat(),
            modified_at=datetime.now().isoformat()
        )
        
        # 保持兼容：旧的 dict 接口
        state.chapters[state.current_chapter] = chapter_text  # 旧接口
        state.creation = getattr(state, 'creation', {})
        state.creation.setdefault('chapters', {})[state.current_chapter] = chapter_content  # 新接口
        
        state.chapter_status[state.current_chapter] = ChapterStatus.DRAFT
        state.review_round = 0
        
        self._notify("chapter_written", {
            "chapter": state.current_chapter,
            "word_count": len(chapter_text)
        })
        
        return state
    
    def _build_writer_context(self, state) -> str:
        """构建写作用上下文"""
        parts = [
            f"【小说信息】\n标题：{state.novel_title}\n类型：{state.genre}\n",
            f"\n【大纲】\n{state.outline[:500]}...\n",
            f"\n【当前章节】第{state.current_chapter}章\n",
            f"\n【角色设定】\n{self._format_characters(state.characters)}\n"
        ]
        
        # 记忆上下文（如果有）
        memory_context = self._build_memory_context(state)
        if memory_context:
            parts.append(f"\n{memory_context}")
        
        # 最近章节
        recent = self._get_recent_chapters(state)
        if recent:
            parts.append(f"\n【最近章节】\n{recent}")
        
        return "\n".join(parts)
    
    def _format_characters(self, characters) -> str:
        if not characters:
            return "暂无角色设定"
        return "\n".join([
            f"- {c.name}：{c.personality}\n  背景：{c.background[:100]}..."
            for c in characters[:5]
        ])
    
    def _get_recent_chapters(self, state) -> str:
        recent = []
        for i in range(max(1, state.current_chapter - 2), state.current_chapter):
            if i in state.chapters:
                content = state.chapters[i][:200]
                recent.append(f"第{i}章结尾：{content}...")
        return "\n".join(recent)


class ReviewerAgent(BaseAgent):
    """青锋 - 审稿节点（JSON mode）"""
    
    def __init__(
        self,
        llm_client=None,
        memory: StoryMemory = None,
        error_handler=None
    ):
        super().__init__(
            persona=QingfengPersona(),
            llm_client=llm_client,
            memory=memory,
            error_handler=error_handler,
            use_json_mode=True
        )
    
    def invoke(self, state):
        """审稿（结构化输出）"""
        
        chapter_text = state.chapters.get(state.current_chapter, "")
        if not chapter_text:
            state.error_message = f"第{state.current_chapter}章无内容可审"
            return state
        
        # 1. 构建上下文
        context = self._build_reviewer_context(state, chapter_text)
        
        # 2. 任务 + JSON 格式要求
        task = """请对以上章节进行审稿，从叙事结构、人物一致性、文学性、市场潜力四个维度评分。"""
        
        # 3. 调用 LLM（JSON mode）
        result_dict = self._call_llm(
            task=task,
            context=context,
            json_schema=REVIEW_JSON_PROMPT
        )
        
        # 4. 解析结构化结果
        review = self._parse_review_result(result_dict)
        
        # 5. 更新状态
        self._update_state_with_review(state, review)
        
        self._notify("chapter_reviewed", {
            "chapter": state.current_chapter,
            "round": state.review_round,
            "score": review.total_score,
            "verdict": review.verdict.value
        })
        
        return state
    
    def _build_reviewer_context(self, state, chapter_text) -> str:
        parts = [
            f"【小说信息】\n{state.to_context_string()}\n",
            f"\n【角色设定】\n{self._format_characters(state.characters)}\n",
            f"\n【本章内容】\n{chapter_text}\n",
            f"\n【历史审稿记录】\n{self._format_reviews(state)}"
        ]
        return "\n".join(parts)
    
    def _parse_review_result(self, result_dict: dict) -> ReviewResult:
        """解析 JSON 结果为 ReviewResult 对象"""
        from core.schema import DimensionScore, ReviewIssue, ReviewVerdict
        
        dimensions = [
            DimensionScore(**d) for d in result_dict.get("dimensions", [])
        ]
        issues = [
            ReviewIssue(**i) for i in result_dict.get("issues", [])
        ]
        verdict = ReviewVerdict(result_dict.get("verdict", "revise"))
        
        return ReviewResult(
            total_score=result_dict.get("total_score", 70),
            dimensions=dimensions,
            issues=issues,
            verdict=verdict,
            summary=result_dict.get("summary", "")
        )
    
    def _update_state_with_review(self, state, review: ReviewResult):
        """将审稿结果更新到状态"""
        from core.state import ReviewRecord, ChapterStatus
        
        # 创建兼容的 ReviewRecord
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
            state.chapter_status[state.current_chapter] = ChapterStatus.PENDING  # 重写
        else:
            state.chapter_status[state.current_chapter] = ChapterStatus.IN_REVIEW
    
    def _format_characters(self, characters) -> str:
        if not characters:
            return "暂无"
        return "\n".join([f"- {c.name}：{c.personality}" for c in characters])
    
    def _format_reviews(self, state) -> str:
        reviews = state.reviews.get(state.current_chapter, [])
        if not reviews:
            return "无"
        return "\n".join([
            f"第{r.round}轮：{r.reviewer} {r.score}分 {'✅' if r.passed else '❌'}"
            for r in reviews
        ])


class ReviserAgent(BaseAgent):
    """修改节点"""
    
    def __init__(
        self,
        llm_client=None,
        memory: StoryMemory = None,
        error_handler=None
    ):
        super().__init__(
            persona=MochuanPersona(),
            llm_client=llm_client,
            memory=memory,
            error_handler=error_handler,
            use_json_mode=False
        )
        self.persona.tone += "（当前任务：根据编辑意见修改，保持开放心态）"
    
    def invoke(self, state):
        """根据审稿意见修改"""
        
        chapter_text = state.chapters.get(state.current_chapter, "")
        latest = state.get_latest_review()
        
        if not latest:
            state.error_message = "无审稿记录，无法修改"
            return state
        
        # 1. 构建上下文
        context = self._build_reviser_context(state, chapter_text, latest)
        
        # 2. 任务
        task = """请根据以上审稿意见修改章节。

要求：
1. 优先处理致命问题
2. 尽量采纳优化建议
3. 保持原有风格和亮点
4. 输出完整的修改后章节

请直接输出修改后的完整章节正文。"""
        
        # 3. 调用 LLM
        revised_text = self._call_llm(task, context)
        
        # 4. 更新状态
        from core.state import ChapterStatus
        state.chapters[state.current_chapter] = revised_text
        state.chapter_status[state.current_chapter] = ChapterStatus.REVISING
        
        # 更新结构化章节内容（新接口）
        if hasattr(state, 'creation') and state.creation:
            from core.schema import ChapterContent
            state.creation['chapters'][state.current_chapter] = ChapterContent(
                text=revised_text,
                version=state.review_round + 1,
                word_count=len(revised_text),
                modified_at=datetime.now().isoformat()
            )
        
        self._notify("chapter_revised", {
            "chapter": state.current_chapter,
            round: state.review_round
        })
        
        return state
    
    def _build_reviser_context(self, state, chapter_text, latest):
        """构建修改上下文"""
        parts = [
            f"【当前章节内容】\n{chapter_text}\n",
            f"\n【编辑审稿意见】\n{latest.comments}\n",
            f"\n【历史修改轮次】{state.review_round}轮"
        ]
        return "\n".join(parts)


class ProofreaderAgent(BaseAgent):
    """砚清 - 校对节点（JSON mode）"""
    
    def __init__(
        self,
        llm_client=None,
        memory: StoryMemory = None,
        error_handler=None
    ):
        super().__init__(
            persona=YanqingPersona(),
            llm_client=llm_client,
            memory=memory,
            error_handler=error_handler,
            use_json_mode=True
        )
    
    def invoke(self, state):
        """校对（结构化输出）"""
        
        chapter_text = state.chapters.get(state.current_chapter, "")
        
        # 1. 构建上下文
        context = self._build_proofread_context(state, chapter_text)
        
        # 2. 任务 + JSON 格式
        task = """请对以上章节进行最终校对，检查错别字、标点错误、一致性问题、逻辑漏洞。"""
        
        # 3. 调用 LLM
        result_dict = self._call_llm(
            task=task,
            context=context,
            json_schema=PROOFREAD_JSON_PROMPT
        )
        
        # 4. 解析结果
        proofread = self._parse_proofread_result(result_dict)
        
        # 5. 更新状态
        self._update_state_with_proofread(state, proofread)
        
        self._notify("chapter_proofread", {
            "chapter": state.current_chapter,
            "passed": proofread.passed
        })
        
        return state
    
    def _build_proofread_context(self, state, chapter_text) -> str:
        parts = [
            f"【章节内容】\n{chapter_text}\n",
            f"\n【角色名单】（请检查一致性）\n{[c.name for c in state.characters]}"
        ]
        return "\n".join(parts)
    
    def _parse_proofread_result(self, result_dict: dict) -> ProofreadResult:
        from core.schema import ProofreadIssue
        
        issues = [
            ProofreadIssue(**i) for i in result_dict.get("issues", [])
        ]
        
        return ProofreadResult(
            passed=result_dict.get("passed", False),
            issues=issues,
            summary=result_dict.get("summary", "")
        )
    
    def _update_state_with_proofread(self, state, proofread: ProofreadResult):
        from core.state import ChapterStatus, ReviewRecord
        
        if proofread.passed:
            state.chapter_status[state.current_chapter] = ChapterStatus.APPROVED
        else:
            state.chapter_status[state.current_chapter] = ChapterStatus.PROOFREADING
            # 添加校对记录
            record = ReviewRecord(
                round=state.review_round + 1,
                reviewer=self.persona.name,
                score=80 if proofread.passed else 50,
                comments=proofread.summary,
                passed=proofread.passed,
                timestamp=datetime.now().isoformat()
            )
            state.reviews.setdefault(state.current_chapter, []).append(record)
