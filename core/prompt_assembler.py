"""
StoryForge - 动态 Prompt 组装器
参考 novel-chapter-expander skill 的人味化规则
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class HumanizationRule:
    """人味化规则"""
    name: str
    description: str
    examples: List[Dict[str, str]]
    priority: int = 1


class PromptAssembler:
    """
    动态 Prompt 组装器
    
    职责：
    1. 根据当前阶段动态调整 prompt
    2. 注入人味化规则
    3. 管理 few-shot 示例
    """
    
    # 人味化规则（来自 novel-chapter-expander skill）
    HUMANIZATION_RULES = [
        HumanizationRule(
            name="禁用句式",
            description="严禁使用以下句式",
            examples=[
                {"forbidden": "不是……而是……", "reason": "过于二元对立"},
                {"forbidden": "破折号'——'", "reason": "用逗号或句号断句"},
            ],
            priority=1
        ),
        HumanizationRule(
            name="叙述者禁令",
            description="叙述者不得替读者下结论",
            examples=[
                {"forbidden": "这一刻，他终于明白了", "replacement": "他盯着那行字，手指悬在半空"},
                {"forbidden": "她意识到X", "replacement": "后颈汗毛再次竖起。这个声音……是X"},
            ],
            priority=1
        ),
        HumanizationRule(
            name="心理描写改写",
            description="直接心理描写改为动作暗示",
            examples=[
                {"forbidden": "她心里知道，这次必须成功", "replacement": "她捏紧了手中的玉佩，指节发白"},
                {"forbidden": "他非常愤怒", "replacement": "他攥紧拳头，指节咔咔作响"},
            ],
            priority=1
        ),
        HumanizationRule(
            name="高风险词汇限制",
            description="限制以下词汇使用频率",
            examples=[
                {"type": "总结归纳词", "limit": "≤3次/千字", "examples": "综合、总之、由此可见"},
                {"type": "枚举模板词", "limit": "绝对禁止三段式", "examples": "首先、其次、最后"},
                {"type": "书面学术腔", "limit": "≤3次/千字", "examples": "某种程度上、本质上"},
                {"type": "情绪直述词", "limit": "必须用动作替代", "examples": "非常愤怒、心中五味杂陈"},
            ],
            priority=2
        ),
        HumanizationRule(
            name="转折标记词限制",
            description="每3000字≤1次",
            examples=[
                {"words": "仿佛、忽然、猛地、不禁"},
            ],
            priority=2
        ),
        HumanizationRule(
            name="人味化技巧",
            description="增强真实感的写作技巧",
            examples=[
                {"technique": "生理反应", "examples": "手心出汗、喉结滚动、后背冷汗、指尖发抖"},
                {"technique": "对话停顿", "examples": "'我……'、'哦'、'那个'、压低声音、顿了顿"},
                {"technique": "多感官细节", "examples": "声音（金属摩擦）、触觉（微烫、硌着指尖）、视觉"},
                {"technique": "微动作链", "examples": "抿嘴→扫视→确认→触碰"},
                {"technique": "电影式切镜", "examples": "用单字/短语段落切换场景（'宿舍。'、'走廊。'）"},
            ],
            priority=3
        ),
        HumanizationRule(
            name="隐喻独特性",
            description="每章2-4个独特比喻，0个常见比喻",
            examples=[
                {"common": "像被针扎", "unique": "像被静电轻轻咬了一口"},
                {"common": "心如刀割", "unique": "胸口像被一块温热的铁慢慢烙着"},
            ],
            priority=2
        ),
    ]
    
    def __init__(self):
        self.rules = self.HUMANIZATION_RULES
        self.few_shot_examples: Dict[str, List[str]] = {}
    
    def assemble_writer_prompt(
        self,
        persona: Any,
        chapter_plan: Any,
        context: str,
        memory_context: str = "",
        examples: List[str] = None,
        humanization: bool = True
    ) -> str:
        """
        组装写作 Prompt
        
        Args:
            persona: Agent 人设
            chapter_plan: 章节计划
            context: 上下文
            memory_context: 记忆上下文
            examples: few-shot 示例
            humanization: 是否注入人味化规则
        """
        parts = []
        
        # 1. 基础人设
        parts.append(persona.system_prompt())
        
        # 2. 人味化规则（如果启用）
        if humanization:
            parts.append(self._format_humanization_rules())
        
        # 3. 任务上下文
        parts.append("\n========== 任务上下文 ==========")
        parts.append(context)
        
        # 4. 记忆上下文
        if memory_context:
            parts.append("\n========== 故事记忆 ==========")
            parts.append(memory_context)
        
        # 5. 章节计划
        if chapter_plan:
            parts.append("\n========== 章节计划 ==========")
            parts.append(self._format_chapter_plan(chapter_plan))
        
        # 6. Few-shot 示例
        if examples:
            parts.append("\n========== 参考示例 ==========")
            for i, example in enumerate(examples[:3], 1):  # 最多3个示例
                parts.append(f"【示例{i}】\n{example}\n")
        
        # 7. 输出要求
        parts.append("\n========== 输出要求 ==========")
        parts.append(self._format_output_requirements())
        
        return "\n".join(parts)
    
    def assemble_reviewer_prompt(
        self,
        persona: Any,
        chapter_content: str,
        chapter_plan: Any,
        characters: List[Any],
        previous_chapter: str = "",
        next_chapter_plan: Any = None,
        extra_context: str = "",
    ) -> str:
        """
        组装审稿 Prompt
        
        参考 novel-chapter-review skill 的 checklist
        """
        parts = []
        
        # 1. 基础人设
        parts.append(persona.system_prompt())
        
        # 2. 审稿 Checklist
        parts.append("\n========== 审稿 Checklist ==========")
        parts.append(self._format_review_checklist())
        
        # 3. 章节内容
        parts.append(f"\n========== 章节内容 ==========\n{chapter_content}\n")
        
        # 4. 章节计划（对照）
        if chapter_plan:
            parts.append("\n========== 章节计划（对照） ==========")
            parts.append(self._format_chapter_plan(chapter_plan))
        
        # 5. 人物设定（对照）
        if characters:
            parts.append("\n========== 人物设定（对照） ==========")
            parts.append(self._format_characters_for_review(characters))
        
        # 6. 前后章衔接
        if previous_chapter:
            parts.append(f"\n========== 前一章结尾 ==========\n{previous_chapter[-500:]}\n")

        # 6.1 额外上下文（如 Agent 消息、预算决策后的补充信息）
        if extra_context:
            parts.append(f"\n========== 额外上下文 ==========\n{extra_context}\n")
        
        # 7. 输出格式要求
        parts.append("\n========== 输出格式要求 ==========")
        parts.append(self._format_review_output_requirements())
        
        return "\n".join(parts)
    
    def assemble_proofreader_prompt(
        self,
        persona: Any,
        chapter_content: str,
        characters: List[Any],
        world_setting: Any = None,
        scope: str = "chapter",
        project_docs: Any = None,
        extra_context: str = "",
    ) -> str:
        """
        组装校对 Prompt

        scope:
        - chapter: 按章校对
        - volume: 按卷校对
        - book: 按本校对
        - project_docs: 对大纲/卷纲/世界观/时间线/人物设定做综合校对
        """
        parts = []

        # 1. 基础人设
        parts.append(persona.system_prompt())

        # 2. 校对 Checklist
        parts.append("\n========== 校对 Checklist ==========")
        parts.append(self._format_proofread_checklist())

        # 3. 校对范围
        parts.append("\n========== 校对范围 ==========")
        parts.append(self._format_proofread_scope(scope))

        # 4. 正文内容（chapter/volume/book 场景）
        if chapter_content:
            parts.append(f"\n========== 正文内容 ==========\n{chapter_content}\n")

        # 5. 人物名单（检查一致性）
        if characters:
            parts.append("\n========== 人物名单（检查一致性） ==========")
            parts.append(self._format_characters_for_proofread(characters))

        # 6. 世界观设定（检查一致性）
        if world_setting:
            parts.append("\n========== 世界观设定（检查一致性） ==========")
            parts.append(str(world_setting))

        # 7. 项目综合文档（project_docs 场景）
        if project_docs:
            parts.append("\n========== 综合项目文档（大纲/卷纲/设定） ==========")
            parts.append(self._format_project_docs_for_proofread(project_docs))

        # 7.1 额外上下文（如 Agent 消息、预算决策后的补充信息）
        if extra_context:
            parts.append(f"\n========== 额外上下文 ==========\n{extra_context}\n")

        # 8. 输出格式要求
        parts.append("\n========== 输出格式要求 ==========")
        parts.append(self._format_proofread_output_requirements())

        return "\n".join(parts)

    def _format_proofread_scope(self, scope: str) -> str:
        mapping = {
            "chapter": "按章校对：聚焦当前章节文本的一致性与错误。",
            "volume": "按卷校对：跨章节检查本卷内时间线、设定和人物连续性。",
            "book": "按本校对：全书级一致性检查（设定、时间线、人物弧线）。",
            "project_docs": "综合文档校对：对大纲、卷纲、世界观、时间线、人物设定进行交叉校验。"
        }
        return mapping.get(scope, mapping["chapter"])

    def _format_project_docs_for_proofread(self, project_docs: Any) -> str:
        if not project_docs:
            return "暂无"
        if isinstance(project_docs, str):
            return project_docs
        if isinstance(project_docs, dict):
            parts = []
            ordered_keys = [
                ("outline", "总大纲"),
                ("volume_outline", "卷纲"),
                ("worldview", "世界观"),
                ("timeline", "时间线"),
                ("character_profiles", "人物设定")
            ]
            used = set()
            for key, title in ordered_keys:
                if key in project_docs and project_docs[key]:
                    parts.append(f"\n【{title}】\n{project_docs[key]}")
                    used.add(key)
            for key, value in project_docs.items():
                if key in used or not value:
                    continue
                parts.append(f"\n【{key}】\n{value}")
            return "\n".join(parts) if parts else "暂无"
        return str(project_docs)

    def _format_humanization_rules(self) -> str:
        """格式化人味化规则"""
        parts = ["\n========== 人味化规则（必须遵守） =========="]
        
        for rule in sorted(self.rules, key=lambda r: r.priority):
            parts.append(f"\n【{rule.name}】{rule.description}")
            for example in rule.examples:
                if "forbidden" in example:
                    parts.append(f"  ❌ 禁用：{example['forbidden']}")
                    if "replacement" in example:
                        parts.append(f"  ✅ 改为：{example['replacement']}")
                    if "reason" in example:
                        parts.append(f"  原因：{example['reason']}")
                elif "technique" in example:
                    parts.append(f"  💡 {example['technique']}：{example.get('examples', '')}")
                elif "type" in example:
                    parts.append(f"  ⚠️ {example['type']}（{example.get('limit', '')}）")
        
        return "\n".join(parts)
    
    def _format_chapter_plan(self, chapter_plan: Any) -> str:
        """格式化章节计划"""
        if hasattr(chapter_plan, '__dict__'):
            plan_dict = chapter_plan.__dict__
        else:
            plan_dict = chapter_plan
        
        parts = []
        parts.append(f"章节：第{plan_dict.get('chapter_id', '?')}章 {plan_dict.get('title', '')}")
        parts.append(f"主题：{plan_dict.get('theme', '')}")
        parts.append(f"情节：{plan_dict.get('plot', '')}")
        parts.append(f"目标字数：{plan_dict.get('words_target', 3000)}字")
        
        scenes = plan_dict.get('scenes', [])
        if scenes:
            parts.append(f"场景：{' / '.join(scenes)}")
        
        hooks = plan_dict.get('hooks', [])
        if hooks:
            parts.append(f"钩子：{' / '.join(hooks)}")
        
        characters = plan_dict.get('characters_involved', [])
        if characters:
            parts.append(f"出场人物：{', '.join(characters)}")
        
        return "\n".join(parts)
    
    def _format_output_requirements(self) -> str:
        """格式化输出要求"""
        return """
请直接输出章节正文，不需要标题和章节号。

字数要求：
- 只统计中文正文字符（不含标点、空格、英文、数字）
- 必须达到目标字数

质量要求：
1. 每个场景至少包含一个冲突或转折
2. 对话要有个性，不能千人一面
3. 展示而非告诉（Show, don't tell）
4. 结尾留悬念或钩子
"""
    
    def _format_review_checklist(self) -> str:
        """格式化审稿 Checklist（参考 novel-chapter-review）"""
        return """
请按以下维度审稿：

1. AI味 vs 人味
   - 是否出现信息堆叠、说明书式段落、模板化比喻、过度总结心理
   - 是否有真实生活质感的场景与对话

2. 人物一致性
   - 人设是否与设定一致（动机、性格、行为逻辑）

3. 伏笔密度与节奏
   - 是否在单章中过度集中数值/编号/伏笔点

4. 语言与节奏
   - 句式是否有起伏；比喻是否克制；口语是否自然

5. 与前后章自洽
   - 关键事件与前后章节是否连贯

6. 元叙事/穿帮红线
   - 正文是否出现"第XX章/上一章/下一章/本卷/读者"等章节外表述

7. 角色位置一致性
   - 本章出场人物位置是否与设定一致
   - 位置变化是否有合理交代
   - 是否存在"角色闪现"（同一章无交代出现在两地）

8. 隐喻独特性
   - 目标：每章2-4个独特比喻，0个常见比喻
"""
    
    def _format_review_output_requirements(self) -> str:
        """格式化审稿输出要求"""
        return """
请严格按照以下 JSON 格式输出审稿结果：

{
  "total_score": <0-100的总评分>,
  "dimensions": [
    {"name": "叙事结构", "score": <0-100>, "weight": 0.3, "comment": "..."},
    {"name": "人物一致性", "score": <0-100>, "weight": 0.3, "comment": "..."},
    {"name": "文学性", "score": <0-100>, "weight": 0.3, "comment": "..."},
    {"name": "市场潜力", "score": <0-100>, "weight": 0.1, "comment": "..."}
  ],
  "ai_flavor": {
    "score": <0-10>,
    "level": "very_low|low|medium|high"
  },
  "issues": [
    {"severity": "S|A|B|C", "location": "第X段", "type": "类型", "description": "问题描述", "suggestion": "修改建议"}
  ],
  "human_highlights": [
    {"point": "亮点描述", "example": "原文示例"}
  ],
  "location_check": {
    "passed": true|false,
    "issues": []
  },
  "meta_issues": [],
  "verdict": "pass|revise|rewrite",
  "summary": "总体评语"
}

AI味等级：
- very_low (0-2): 几乎无AI味，可发布
- low (3-4): 少量AI味，轻微修改即可
- medium (5-7): 中度AI味，需要多处修改
- high (8-10): 重度AI味，需要重写大部分

严重度：
- S: 硬伤（必须改）
- A: 影响阅读（必须改）
- B: 中度问题（建议改）
- C: 轻度问题（可选改）
"""
    
    def _format_proofread_checklist(self) -> str:
        """格式化校对 Checklist（参考 novel-proofread）"""
        return """
请按以下层级校对：

### 基础层
- [ ] 错别字、错用字
- [ ] 标点符号规范
- [ ] 数字写法统一（汉字/阿拉伯数字）
- [ ] 专有名词一致性

### 设定层
- [ ] 力量体系/技术规则一致性
- [ ] 货币/资源体系逻辑自洽
- [ ] 权限/等级体系不矛盾
- [ ] 特殊设定前后口径统一

### 时间线层
- [ ] 历史大事记时间顺序
- [ ] 人物年龄计算
- [ ] 事件间隔合理性

### 人物层
- [ ] 人物关系图谱准确性
- [ ] 称呼变化有据可查
- [ ] 立场转变有迹可循
- [ ] 人物状态（受伤/中毒/etc.）连续性

### 地理层
- [ ] 地图格局一致性
- [ ] 方位距离合理性
- [ ] 场景转换逻辑

### 伏笔层
- [ ] 前文埋线登记
- [ ] 后文呼应检查
- [ ] 回收状态标记
"""
    
    def _format_proofread_output_requirements(self) -> str:
        """格式化校对输出要求"""
        return """
请严格按照以下 JSON 格式输出校对结果：

{
  "passed": true|false,
  "verdict": "可发布|可交付|需返修",
  "issues": [
    {"type": "typo|consistency|logic|format|setting", "severity": "S|A|B|C", "location": "第X段", "original": "原文", "correction": "修改", "explanation": "说明"}
  ],
  "summary": "总体评价"
}

终审判定标准：
- 可发布：无致命错误，无重要错误，一般错误<5处/章
- 可交付：无致命错误，重要错误<3处/卷，一般错误<10处/章
- 需返修：存在致命错误（设定矛盾、时间线断裂、人物关系错乱）
"""
    
    def _format_characters_for_review(self, characters: List[Any]) -> str:
        """格式化人物信息（用于审稿）"""
        parts = []
        for char in characters:
            if hasattr(char, 'name'):
                parts.append(f"- {char.name}：{getattr(char, 'personality', '')}")
                if hasattr(char, 'motivation') and char.motivation:
                    parts.append(f"  动机：{char.motivation}")
                if hasattr(char, 'current_location') and char.current_location:
                    parts.append(f"  当前位置：{char.current_location}")
        return "\n".join(parts) if parts else "暂无"
    
    def _format_characters_for_proofread(self, characters: List[Any]) -> str:
        """格式化人物信息（用于校对）"""
        parts = []
        for char in characters:
            if hasattr(char, 'name'):
                parts.append(f"- {char.name}")
                if hasattr(char, 'current_location') and char.current_location:
                    parts.append(f"  位置：{char.current_location}")
        return "\n".join(parts) if parts else "暂无"
