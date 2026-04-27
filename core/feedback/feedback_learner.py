"""
StoryForge - 人类反馈学习机制

职责：
1. 收集用户对生成内容的修改意见
2. 将反馈转化为 Prompt 优化规则
3. 定期更新模型的系统提示词
4. 支持用户点赞/点踩和修改追踪
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import json
import os
from datetime import datetime


class FeedbackType(Enum):
    """反馈类型"""
    THUMBS_UP = "thumbs_up"      # 点赞
    THUMBS_DOWN = "thumbs_down"  # 点踩
    EDIT = "edit"                # 编辑修改
    COMMENT = "comment"          # 文字评论
    REWRITE = "rewrite"          # 重写/改写


class FeedbackTag(Enum):
    """反馈标签（用于归类）"""
    TOO_AI_LIKE = "too_ai_like"      # 太 AI 味
    TOO_VERBOSE = "too_verbose"      # 太啰嗦
    TOO_SHORT = "too_short"          # 太短
    INCONSISTENT = "inconsistent"    # 不一致
    WRONG_TONE = "wrong_tone"        # 语气不对
    BAD_CHARACTER = "bad_character"  # 人物走形
    BAD_PLOT = "bad_plot"            # 剧情问题
    GOOD = "good"                    # 写得好
    EXCELLENT = "excellent"          # 特别好


@dataclass
class FeedbackRecord:
    """反馈记录"""
    feedback_id: str
    novel_id: str
    chapter: int
    task_type: str  # writing / review / proofread / etc.
    feedback_type: FeedbackType
    original_content: str
    modified_content: Optional[str] = None
    comment: Optional[str] = None
    tags: List[FeedbackTag] = field(default_factory=list)
    rating: Optional[int] = None  # 1-5
    prompt_used: Optional[str] = None  # 使用的提示词
    model_used: Optional[str] = None  # 使用的模型
    timestamp: str = ""
    processed: bool = False  # 是否已用于优化
    applied_rule_ids: List[str] = field(default_factory=list)  # 应用的规则 ID


@dataclass
class PromptRule:
    """提示词优化规则"""
    rule_id: str
    name: str
    description: str
    trigger_tags: List[FeedbackTag] = field(default_factory=list)
    prompt_addition: str  # 添加到提示词中的内容
    prompt_modification: Optional[str] = None  # 修改提示词中的某部分
    weight: float = 1.0  # 权重（影响排序）
    apply_count: int = 0  # 应用次数
    success_count: int = 0  # 成功次数（后续继续获得好评）
    created_at: str = ""
    updated_at: str = ""
    enabled: bool = True
    task_scope: Optional[List[str]] = None  # 适用的任务类型（None 表示所有）


class FeedbackLearner:
    """
    反馈学习器

    使用示例：
    ```python
    learner = FeedbackLearner(feedback_dir="./feedback")
    
    # 记录反馈
    record = FeedbackRecord(
        feedback_id="f_001",
        novel_id="my_novel",
        chapter=1,
        task_type="writing",
        feedback_type=FeedbackType.EDIT,
        original_content="...",
        modified_content="...",
        tags=[FeedbackTag.TOO_AI_LIKE]
    )
    learner.record_feedback(record)
    
    # 优化提示词
    optimized_prompt = learner.optimize_prompt(
        base_prompt="You are a writer...",
        task_type="writing"
    )
    
    # 学习新规则
    new_rules = learner.learn_rules(recent_feedback)
    for rule in new_rules:
        learner.add_rule(rule)
    ```
    """

    def __init__(
        self,
        feedback_dir: str = "./feedback",
        auto_learn: bool = True,
        learn_threshold: int = 3  # 多少次相似反馈才学习新规则
    ):
        self.feedback_dir = feedback_dir
        self.auto_learn = auto_learn
        self.learn_threshold = learn_threshold
        
        # 数据存储
        self.feedback_records: Dict[str, FeedbackRecord] = {}
        self.prompt_rules: Dict[str, PromptRule] = {}
        
        # 索引
        self._feedback_by_novel: Dict[str, List[str]] = {}
        self._feedback_by_tag: Dict[FeedbackTag, List[str]] = {}
        
        # 确保目录存在
        os.makedirs(feedback_dir, exist_ok=True)
        self._load_data()
    
    def record_feedback(self, record: FeedbackRecord):
        """
        记录用户反馈
        
        Args:
            record: 反馈记录
        """
        if not record.timestamp:
            record.timestamp = datetime.now().isoformat()
        
        if not record.feedback_id:
            record.feedback_id = f"f_{int(time.time())}"
        
        # 存储
        self.feedback_records[record.feedback_id] = record
        
        # 更新索引
        if record.novel_id not in self._feedback_by_novel:
            self._feedback_by_novel[record.novel_id] = []
        self._feedback_by_novel[record.novel_id].append(record.feedback_id)
        
        for tag in record.tags:
            if tag not in self._feedback_by_tag:
                self._feedback_by_tag[tag] = []
            self._feedback_by_tag[tag].append(record.feedback_id)
        
        # 保存
        self._save_data()
        
        print(f"📝 已记录反馈: {record.feedback_type.value} (ID: {record.feedback_id})")
        
        # 自动学习
        if self.auto_learn:
            self._auto_learn_from_feedback(record)
    
    def add_rule(self, rule: PromptRule):
        """
        添加提示词规则
        
        Args:
            rule: 提示词规则
        """
        if not rule.created_at:
            rule.created_at = datetime.now().isoformat()
        if not rule.updated_at:
            rule.updated_at = datetime.now().isoformat()
        
        self.prompt_rules[rule.rule_id] = rule
        self._save_data()
        
        print(f"✅ 已添加规则: {rule.name} (ID: {rule.rule_id})")
    
    def optimize_prompt(
        self,
        base_prompt: str,
        task_type: str,
        novel_id: Optional[str] = None,
        chapter: Optional[int] = None
    ) -> str:
        """
        根据反馈优化提示词
        
        Args:
            base_prompt: 基础提示词
            task_type: 任务类型
            novel_id: 小说 ID（可选，用于获取特定反馈）
            chapter: 章节号（可选）
        
        Returns:
            str: 优化后的提示词
        """
        # 收集适用的规则
        applicable_rules = []
        
        for rule in self.prompt_rules.values():
            if not rule.enabled:
                continue
            
            # 检查任务范围
            if rule.task_scope and task_type not in rule.task_scope:
                continue
            
            applicable_rules.append(rule)
        
        # 按权重排序
        applicable_rules.sort(key=lambda r: r.weight, reverse=True)
        
        # 构建优化后的提示词
        optimized_prompt = base_prompt
        
        if applicable_rules:
            optimized_prompt += "\n\n===== 写作指导（基于用户反馈）=====\n"
            
            for rule in applicable_rules:
                optimized_prompt += f"\n{rule.prompt_addition}"
        
        return optimized_prompt
    
    def learn_rules(self, feedback_records: List[FeedbackRecord]) -> List[PromptRule]:
        """
        从反馈记录中学习新规则
        
        Args:
            feedback_records: 反馈记录列表
        
        Returns:
            List[PromptRule]: 学习到的新规则
        """
        new_rules = []
        
        # 按标签分组统计
        tag_counts: Dict[FeedbackTag, List[FeedbackRecord]] = {}
        for record in feedback_records:
            for tag in record.tags:
                if tag not in tag_counts:
                    tag_counts[tag] = []
                tag_counts[tag].append(record)
        
        # 为超过阈值的标签生成规则
        for tag, records in tag_counts.items():
            if len(records) >= self.learn_threshold:
                rule = self._generate_rule_from_tag(tag, records)
                if rule:
                    new_rules.append(rule)
        
        # 从编辑反馈中学习
        edit_records = [r for r in feedback_records if r.feedback_type == FeedbackType.EDIT]
        if len(edit_records) >= self.learn_threshold:
            edit_rule = self._generate_rule_from_edits(edit_records)
            if edit_rule:
                new_rules.append(edit_rule)
        
        return new_rules
    
    def get_feedback(
        self,
        novel_id: Optional[str] = None,
        tag: Optional[FeedbackTag] = None,
        chapter: Optional[int] = None,
        limit: int = 100
    ) -> List[FeedbackRecord]:
        """
        获取反馈记录
        
        Args:
            novel_id: 按小说筛选
            tag: 按标签筛选
            chapter: 按章节筛选
            limit: 返回数量限制
        
        Returns:
            List[FeedbackRecord]: 反馈记录列表
        """
        candidates = list(self.feedback_records.values())
        
        if novel_id:
            candidates = [r for r in candidates if r.novel_id == novel_id]
        
        if tag:
            candidates = [r for r in candidates if tag in r.tags]
        
        if chapter:
            candidates = [r for r in candidates if r.chapter == chapter]
        
        # 按时间倒序
        candidates.sort(key=lambda r: r.timestamp, reverse=True)
        
        return candidates[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取反馈统计"""
        total_feedback = len(self.feedback_records)
        processed_count = len([r for r in self.feedback_records.values() if r.processed])
        
        tag_counts = {}
        for tag in FeedbackTag:
            tag_counts[tag.value] = len(self._feedback_by_tag.get(tag, []))
        
        type_counts = {}
        for record in self.feedback_records.values():
            ft = record.feedback_type.value
            type_counts[ft] = type_counts.get(ft, 0) + 1
        
        return {
            "total_feedback": total_feedback,
            "processed_count": processed_count,
            "active_rules": len([r for r in self.prompt_rules.values() if r.enabled]),
            "tag_distribution": tag_counts,
            "type_distribution": type_counts
        }
    
    def export_rules(self, file_path: str):
        """导出规则到文件"""
        data = [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "description": r.description,
                "trigger_tags": [t.value for t in r.trigger_tags],
                "prompt_addition": r.prompt_addition,
                "weight": r.weight,
                "enabled": r.enabled
            }
            for r in self.prompt_rules.values()
        ]
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"💾 已导出 {len(data)} 条规则到 {file_path}")
    
    def import_rules(self, file_path: str):
        """从文件导入规则"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data_list = json.load(f)
        
        imported = 0
        for data in data_list:
            rule = PromptRule(
                rule_id=data['rule_id'],
                name=data['name'],
                description=data.get('description', ''),
                trigger_tags=[FeedbackTag(t) for t in data.get('trigger_tags', [])],
                prompt_addition=data['prompt_addition'],
                weight=data.get('weight', 1.0),
                enabled=data.get('enabled', True)
            )
            self.prompt_rules[rule.rule_id] = rule
            imported += 1
        
        self._save_data()
        print(f"📥 已导入 {imported} 条规则")
    
    def _auto_learn_from_feedback(self, record: FeedbackRecord):
        """自动从新反馈中学习"""
        # 检查是否达到学习阈值
        for tag in record.tags:
            if tag in self._feedback_by_tag:
                if len(self._feedback_by_tag[tag]) == self.learn_threshold:
                    # 刚好达到阈值，学习新规则
                    records = [self.feedback_records[fid] for fid in self._feedback_by_tag[tag]]
                    rule = self._generate_rule_from_tag(tag, records)
                    if rule:
                        self.add_rule(rule)
    
    def _generate_rule_from_tag(
        self,
        tag: FeedbackTag,
        records: List[FeedbackRecord]
    ) -> Optional[PromptRule]:
        """根据标签和相关反馈生成规则"""
        # 预设规则模板
        rule_templates = {
            FeedbackTag.TOO_AI_LIKE: PromptRule(
                rule_id=f"rule_no_ai_like_{int(time.time())}",
                name="减少 AI 味",
                description="让写作更自然，减少 AI 生成的痕迹",
                trigger_tags=[FeedbackTag.TOO_AI_LIKE],
                prompt_addition="""
重要提示：请让写作更自然，避免 AI 生成的痕迹。
- 使用更口语化的表达
- 避免完美得有些假的对话
- 增加一些"不完美"但真实的细节
- 让角色说话更像真人，不要每句都那么精炼
- 适当使用网络用语和流行词汇（符合故事背景的前提下）
""",
                weight=1.5
            ),
            FeedbackTag.TOO_VERBOSE: PromptRule(
                rule_id=f"rule_concise_{int(time.time())}",
                name="精简表达",
                description="避免过于啰嗦的表达",
                trigger_tags=[FeedbackTag.TOO_VERBOSE],
                prompt_addition="""
重要提示：请保持文字简洁精炼。
- 避免冗长的描述
- 删除对剧情没有帮助的修饰
- 让每一句话都有意义
- 用更少的词表达同样的意思
""",
                weight=1.2
            ),
            FeedbackTag.INCONSISTENT: PromptRule(
                rule_id=f"rule_consistent_{int(time.time())}",
                name="保持一致性",
                description="确保人物和设定的一致性",
                trigger_tags=[FeedbackTag.INCONSISTENT],
                prompt_addition="""
重要提示：请仔细检查人物和设定的一致性。
- 确保人物性格、背景前后一致
- 确保世界设定没有冲突
- 确保时间线、地点等逻辑正确
- 确保伏笔和回收对应
""",
                weight=1.8
            ),
            FeedbackTag.WRONG_TONE: PromptRule(
                rule_id=f"rule_tone_{int(time.time())}",
                name="调整语气",
                description="让语气更符合故事风格",
                trigger_tags=[FeedbackTag.WRONG_TONE],
                prompt_addition="""
重要提示：请注意语气和风格。
- 保持和之前章节一致的基调
- 对话要符合人物性格
- 叙述节奏要恰当
""",
                weight=1.3
            ),
            FeedbackTag.BAD_CHARACTER: PromptRule(
                rule_id=f"rule_character_{int(time.time())}",
                name="人物塑造",
                description="让人物更真实、符合人设",
                trigger_tags=[FeedbackTag.BAD_CHARACTER],
                prompt_addition="""
重要提示：请确保人物符合人设。
- 说话要符合人物性格
- 行为要符合人物设定
- 保持人物的连贯性和成长性
- 避免人物突然变得陌生
""",
                weight=1.6
            ),
            FeedbackTag.BAD_PLOT: PromptRule(
                rule_id=f"rule_plot_{int(time.time())}",
                name="剧情优化",
                description="让剧情更合理、更吸引人",
                trigger_tags=[FeedbackTag.BAD_PLOT],
                prompt_addition="""
重要提示：请注意剧情质量。
- 确保剧情逻辑通顺
- 确保发展合理可信
- 避免机械降神或突兀转折
- 让剧情有张力和吸引力
""",
                weight=1.6
            ),
            FeedbackTag.GOOD: PromptRule(
                rule_id=f"rule_good_example_{int(time.time())}",
                name="保持风格",
                description="保持当前的写作风格",
                trigger_tags=[FeedbackTag.GOOD],
                prompt_addition="""
重要提示：请保持当前的写作风格。
- 继续按照之前的风格写作
- 保持节奏和基调一致
- 用户对之前的内容很满意，请继续保持！
""",
                weight=0.8
            )
        }
        
        return rule_templates.get(tag)
    
    def _generate_rule_from_edits(
        self,
        edit_records: List[FeedbackRecord]
    ) -> Optional[PromptRule]:
        """从编辑记录中学习规则"""
        if not edit_records:
            return None
        
        # 这里可以实现更复杂的差异分析
        # 简化版：生成一个通用编辑优化规则
        return PromptRule(
            rule_id=f"rule_edit_learned_{int(time.time())}",
            name="基于编辑的优化",
            description="从用户编辑中学习的优化方向",
            trigger_tags=[],
            prompt_addition="""
重要提示：请参考用户对之前章节的编辑。
- 注意用户喜欢什么样的表达
- 避免用户修改过的问题
- 让风格更接近用户偏好
""",
            weight=1.0
        )
    
    def _load_data(self):
        """加载持久化数据"""
        feedback_file = os.path.join(self.feedback_dir, "feedback_records.json")
        rules_file = os.path.join(self.feedback_dir, "prompt_rules.json")
        
        if os.path.exists(feedback_file):
            try:
                with open(feedback_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for record_data in data:
                    record = self._record_from_dict(record_data)
                    self.feedback_records[record.feedback_id] = record
                    # 重建索引
                    if record.novel_id not in self._feedback_by_novel:
                        self._feedback_by_novel[record.novel_id] = []
                    self._feedback_by_novel[record.novel_id].append(record.feedback_id)
                    for tag in record.tags:
                        if tag not in self._feedback_by_tag:
                            self._feedback_by_tag[tag] = []
                        self._feedback_by_tag[tag].append(record.feedback_id)
            except Exception as e:
                print(f"⚠️ 加载反馈记录失败: {e}")
        
        if os.path.exists(rules_file):
            try:
                with open(rules_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for rule_data in data:
                    rule = self._rule_from_dict(rule_data)
                    self.prompt_rules[rule.rule_id] = rule
            except Exception as e:
                print(f"⚠️ 加载规则失败: {e}")
    
    def _save_data(self):
        """保存数据到文件"""
        feedback_file = os.path.join(self.feedback_dir, "feedback_records.json")
        rules_file = os.path.join(self.feedback_dir, "prompt_rules.json")
        
        feedback_data = [self._record_to_dict(r) for r in self.feedback_records.values()]
        rules_data = [self._rule_to_dict(r) for r in self.prompt_rules.values()]
        
        with open(feedback_file, 'w', encoding='utf-8') as f:
            json.dump(feedback_data, f, ensure_ascii=False, indent=2)
        
        with open(rules_file, 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)
    
    def _record_to_dict(self, record: FeedbackRecord) -> Dict:
        """FeedbackRecord 转 dict"""
        return {
            "feedback_id": record.feedback_id,
            "novel_id": record.novel_id,
            "chapter": record.chapter,
            "task_type": record.task_type,
            "feedback_type": record.feedback_type.value,
            "original_content": record.original_content,
            "modified_content": record.modified_content,
            "comment": record.comment,
            "tags": [t.value for t in record.tags],
            "rating": record.rating,
            "prompt_used": record.prompt_used,
            "model_used": record.model_used,
            "timestamp": record.timestamp,
            "processed": record.processed,
            "applied_rule_ids": record.applied_rule_ids
        }
    
    def _record_from_dict(self, data: Dict) -> FeedbackRecord:
        """dict 转 FeedbackRecord"""
        return FeedbackRecord(
            feedback_id=data['feedback_id'],
            novel_id=data['novel_id'],
            chapter=data['chapter'],
            task_type=data['task_type'],
            feedback_type=FeedbackType(data['feedback_type']),
            original_content=data['original_content'],
            modified_content=data.get('modified_content'),
            comment=data.get('comment'),
            tags=[FeedbackTag(t) for t in data.get('tags', [])],
            rating=data.get('rating'),
            prompt_used=data.get('prompt_used'),
            model_used=data.get('model_used'),
            timestamp=data.get('timestamp', ''),
            processed=data.get('processed', False),
            applied_rule_ids=data.get('applied_rule_ids', [])
        )
    
    def _rule_to_dict(self, rule: PromptRule) -> Dict:
        """PromptRule 转 dict"""
        return {
            "rule_id": rule.rule_id,
            "name": rule.name,
            "description": rule.description,
            "trigger_tags": [t.value for t in rule.trigger_tags],
            "prompt_addition": rule.prompt_addition,
            "prompt_modification": rule.prompt_modification,
            "weight": rule.weight,
            "apply_count": rule.apply_count,
            "success_count": rule.success_count,
            "created_at": rule.created_at,
            "updated_at": rule.updated_at,
            "enabled": rule.enabled,
            "task_scope": rule.task_scope
        }
    
    def _rule_from_dict(self, data: Dict) -> PromptRule:
        """dict 转 PromptRule"""
        return PromptRule(
            rule_id=data['rule_id'],
            name=data['name'],
            description=data.get('description', ''),
            trigger_tags=[FeedbackTag(t) for t in data.get('trigger_tags', [])],
            prompt_addition=data['prompt_addition'],
            prompt_modification=data.get('prompt_modification'),
            weight=data.get('weight', 1.0),
            apply_count=data.get('apply_count', 0),
            success_count=data.get('success_count', 0),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
            enabled=data.get('enabled', True),
            task_scope=data.get('task_scope')
        )


# 导入 time 模块（放在最后避免循环导入问题）
import time
