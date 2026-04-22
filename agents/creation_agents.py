"""
NovelForge - 角色定义
墨川、青锋、砚清等 Agent 的具体实现
"""

from core.agent import AgentPersona, BaseAgent
from core.state import NovelState, ReviewRecord, ChapterStatus

import re
from datetime import datetime


# ==================== 阶段一：创作层 Agent ====================

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
能一眼看出三百页手稿里'他'和'她'的混用，能记住第50章出现的配角名字并在第200章发现拼写不一致。
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


# ==================== Agent 节点实现 ====================

class WriterAgent(BaseAgent):
    """墨川 - 写作节点"""
    
    def __init__(self, llm_client=None):
        super().__init__(MochuanPersona(), llm_client)
    
    def invoke(self, state: NovelState) -> NovelState:
        """写作章节"""
        
        # 构建上下文
        context = f"""
【小说信息】
标题：{state.novel_title}
类型：{state.genre}

【大纲】
{state.outline[:500]}...

【当前章节】第{state.current_chapter}章

【角色设定】
{self._format_characters(state.characters)}

【已完成的最近章节】
{self._get_recent_chapters(state)}
"""
        
        task = f"""请创作第{state.current_chapter}章，目标字数{state.target_word_count}字。

要求：
1. 严格遵循大纲中本章的情节安排
2. 保持人物性格和动机的一致性
3. 与上一章衔接自然
4. 至少包含一个冲突或转折
5. 结尾留悬念或钩子

请直接输出章节正文，不需要标题和章节号。"""
        
        # 调用 LLM
        chapter_content = self._call_llm(task, context)
        
        # 更新状态
        state.chapters[state.current_chapter] = chapter_content
        state.chapter_status[state.current_chapter] = ChapterStatus.DRAFT
        state.review_round = 0  # 重置审稿轮次
        
        self._notify("chapter_written", {
            "chapter": state.current_chapter,
            "word_count": len(chapter_content)
        })
        
        return state
    
    def _format_characters(self, characters) -> str:
        """格式化角色信息"""
        if not characters:
            return "暂无角色设定"
        return "\n".join([
            f"- {c.name}：{c.personality}。{c.background[:100]}..."
            for c in characters[:5]  # 只取前5个主要角色
        ])
    
    def _get_recent_chapters(self, state: NovelState) -> str:
        """获取最近完成的章节摘要"""
        recent = []
        for i in range(max(1, state.current_chapter - 2), state.current_chapter):
            if i in state.chapters:
                content = state.chapters[i][:200]
                recent.append(f"第{i}章结尾：{content}...")
        return "\n".join(recent) if recent else "无"


class ReviewerAgent(BaseAgent):
    """青锋 - 审稿节点"""
    
    def __init__(self, llm_client=None):
        super().__init__(QingfengPersona(), llm_client)
    
    def invoke(self, state: NovelState) -> NovelState:
        """审稿并给出评分和建议"""
        
        chapter_content = state.chapters.get(state.current_chapter, "")
        if not chapter_content:
            state.error_message = f"第{state.current_chapter}章无内容可审"
            return state
        
        context = f"""
【小说信息】
{state.to_context_string()}

【角色设定】
{self._format_characters(state.characters)}

【本章内容】
{chapter_content[:1500]}...
（共{len(chapter_content)}字）

【历史审稿记录】
{self._format_reviews(state)}
"""
        
        task = """请对以上章节进行审稿，按以下格式输出：

【总体评分】XX分（0-100）

【维度评分】
- 叙事结构：XX分
- 人物一致性：XX分  
- 文学性：XX分
- 市场潜力：XX分

【致命问题】（必须修改）
1. ...

【优化建议】（建议修改）
1. ...

【亮点】
1. ...

【是否通过】通过/需修改/重写"""
        
        review_text = self._call_llm(task, context)
        
        # 解析评分
        score = self._extract_score(review_text)
        passed = "通过" in review_text and score >= 85
        
        # 创建审稿记录
        record = ReviewRecord(
            round=state.review_round + 1,
            reviewer=self.persona.name,
            score=score,
            comments=review_text,
            passed=passed,
            timestamp=datetime.now().isoformat()
        )
        
        # 更新状态
        if state.current_chapter not in state.reviews:
            state.reviews[state.current_chapter] = []
        state.reviews[state.current_chapter].append(record)
        state.review_round += 1
        
        if passed:
            state.chapter_status[state.current_chapter] = ChapterStatus.APPROVED
        else:
            state.chapter_status[state.current_chapter] = ChapterStatus.IN_REVIEW
        
        self._notify("chapter_reviewed", {
            "chapter": state.current_chapter,
            "round": record.round,
            "score": score,
            "passed": passed
        })
        
        return state
    
    def _extract_score(self, text: str) -> int:
        """从审稿意见中提取评分"""
        # 匹配 "总体评分】85分" 或 "评分：85" 等格式
        patterns = [
            r'总体评分[】\:]\s*(\d+)',
            r'评分[】\:]\s*(\d+)',
            r'(\d{2,3})\s*分'
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                score = int(match.group(1))
                return min(100, max(0, score))  # 限制在0-100
        return 70  # 默认评分
    
    def _format_characters(self, characters) -> str:
        """格式化角色信息"""
        if not characters:
            return "暂无"
        return "\n".join([
            f"- {c.name}：{c.personality}"
            for c in characters
        ])
    
    def _format_reviews(self, state: NovelState) -> str:
        """格式化历史审稿记录"""
        reviews = state.reviews.get(state.current_chapter, [])
        if not reviews:
            return "无"
        return "\n".join([
            f"第{r.round}轮：{r.reviewer} {r.score}分 {'通过' if r.passed else '未通过'}"
            for r in reviews
        ])


class ReviserAgent(BaseAgent):
    """修改节点（也是墨川，但任务不同）"""
    
    def __init__(self, llm_client=None):
        super().__init__(MochuanPersona(), llm_client)
        # 修改时调整语气，更配合编辑
        self.persona.tone += "（当前任务：根据编辑意见修改，保持开放心态）"
    
    def invoke(self, state: NovelState) -> NovelState:
        """根据审稿意见修改"""
        
        chapter_content = state.chapters.get(state.current_chapter, "")
        latest_review = state.get_latest_review()
        
        if not latest_review:
            state.error_message = "无审稿记录，无法修改"
            return state
        
        context = f"""
【当前章节内容】
{chapter_content}

【编辑审稿意见】
{latest_review.comments}

【历史修改轮次】{state.review_round}轮
"""
        
        task = """请根据以上审稿意见修改章节。

要求：
1. 优先处理"致命问题"
2. 尽量采纳"优化建议"
3. 保持原有风格和亮点
4. 输出完整的修改后章节（不是修改说明）

请直接输出修改后的完整章节正文。"""
        
        revised_content = self._call_llm(task, context)
        
        # 更新状态
        state.chapters[state.current_chapter] = revised_content
        state.chapter_status[state.current_chapter] = ChapterStatus.REVISING
        
        self._notify("chapter_revised", {
            "chapter": state.current_chapter,
            "round": state.review_round
        })
        
        return state


class ProofreaderAgent(BaseAgent):
    """砚清 - 校对节点"""
    
    def __init__(self, llm_client=None):
        super().__init__(YanqingPersona(), llm_client)
    
    def invoke(self, state: NovelState) -> NovelState:
        """最终校对"""
        
        chapter_content = state.chapters.get(state.current_chapter, "")
        
        context = f"""
【章节内容】
{chapter_content}

【角色名单】（请检查一致性）
{[c.name for c in state.characters]}
"""
        
        task = """请对以上章节进行最终校对，检查：

1. 错别字、标点错误
2. 人物名字前后不一致
3. 时间线/地理矛盾
4. 逻辑漏洞
5. 格式规范

按以下格式输出：

【错误列表】
- 第X段："原文" → 应改为"修改"

【一致性检查】
- 通过/问题：...

【总体评价】
通过 / 需返工

如果无错误，直接输出"通过"。"""
        
        proofread_result = self._call_llm(task, context)
        
        # 判断是否通过
        passed = "通过" in proofread_result and "需返工" not in proofread_result
        
        if passed:
            state.chapter_status[state.current_chapter] = ChapterStatus.APPROVED
        else:
            state.chapter_status[state.current_chapter] = ChapterStatus.PROOFREADING
            # 把校对意见加入审稿记录，触发修改
            state.reviews.setdefault(state.current_chapter, []).append(
                ReviewRecord(
                    round=state.review_round + 1,
                    reviewer=self.persona.name,
                    score=80 if passed else 50,
                    comments=proofread_result,
                    passed=passed
                )
            )
        
        self._notify("chapter_proofread", {
            "chapter": state.current_chapter,
            "passed": passed
        })
        
        return state
