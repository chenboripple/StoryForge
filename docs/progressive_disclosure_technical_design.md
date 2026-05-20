# 渐进式披露技术设计（可实施版）

## 当前实现

- 状态模型、Planner、ContextOrchestrator、feedback/proposal 相关接口已经具备基本承载位。
- 当前文档描述的是现有骨架上的可实施补全方向，而不是独立的旧方案。

## 后续计划

1. 把 ContextOrchestrator 的预算裁剪和升级加载在更多 Agent 中落地。
2. 为 proposal 生命周期补充存储与 API 说明。

## 1. 范围

本文是 [progressive_disclosure_architecture.md](progressive_disclosure_architecture.md) 的工程化落地版本，覆盖：

1. 状态模型扩展
2. 新增组件与接口
3. Pipeline 节点与路由调整
4. Agent 上下文加载协议
5. 反哺与提案协议
6. 最小交付增量（MVP）

## 2. 目标改造

在不引入外部依赖的前提下，完成以下能力：

1. 分层工件落盘到运行态：volume_briefs / chapter_briefs。
2. 新增 ContextOrchestrator：默认最小加载 + 触发升级加载 + 预算裁剪。
3. Writer/Reviewer/Reviser/Proofreader 全部接入 ContextOrchestrator。
4. 新增 feedback_synthesizer 节点：把评估结果反哺到 chapter_brief。
5. 新增 proposal 数据结构：跨层变更进入提案队列，不直接改高层真相。

## 3. 状态模型

文件：core/state.py

新增字段：

1. volume_briefs: Dict[int, Dict[str, Any]]
- 键为卷号，值为卷级摘要、目标、里程碑等。

2. chapter_briefs: Dict[int, Dict[str, Any]]
- 键为章号，值为章级概述（目标、场景、钩子、角色、约束）。

3. context_budgets: Dict[str, int]
- 各节点上下文预算（字符预算，后续可替换 token 预算）。

4. context_decisions: List[Dict[str, Any]]
- 每次上下文装载决策日志。

5. proposals: List[Dict[str, Any]]
- 跨层修订提案列表。

6. canonical_versions: Dict[str, int]
- 关键工件版本号。

新增方法：

1. get_chapter_brief(chapter: int) -> Dict[str, Any]
2. set_chapter_brief(chapter: int, brief: Dict[str, Any]) -> None
3. update_chapter_brief_from_feedback(chapter: int, summary: str, issues: List[Dict]) -> None
4. add_proposal(target_layer, reason, diff, chapter, confidence, risk_level) -> str
5. record_context_decision(agent, chapter, loaded_sections, escalated, budget, used_chars) -> None

## 4. 新增组件

### 4.1 ContextOrchestrator

文件：core/context_orchestrator.py

职责：

1. 根据 agent 类型构建上下文加载包。
2. 执行预算裁剪（优先级保留，低优先级裁切）。
3. 在触发器命中时升级加载（如前后章片段、角色完整卡）。
4. 记录上下文决策日志到 state.context_decisions。

核心接口：

1. build_writer_bundle(state, memory_context="") -> Dict[str, Any]
2. build_reviewer_bundle(state, chapter_text: str) -> Dict[str, Any]
3. build_reviser_bundle(state, chapter_text: str, latest_review, structured_review) -> Dict[str, Any]
4. build_proofreader_bundle(state, chapter_text: str) -> Dict[str, Any]

bundle 规范（公共字段）：

1. context: str
2. chapter_plan: Dict[str, Any]
3. characters: List[Any]
4. chapter_content: str
5. previous_chapter: str
6. world_setting: Optional[Any]
7. project_docs: Optional[Any]
8. loaded_sections: List[str]
9. escalated: bool

### 4.2 ProgressivePlanner

文件：stages/outline/progressive_planner.py

职责：

1. 生成卷纲摘要（volume brief）。
2. 生成章节概述（chapter brief）。
3. 无 LLM 时提供可用 fallback。

核心接口：

1. generate_volume_brief(book_outline, volume_id, current_chapter, existing_brief=None) -> Dict
2. generate_chapter_brief(book_outline, volume_brief, chapter_id, target_words, neighbors=None) -> Dict

## 5. Pipeline 改造

文件：pipeline/novel_pipeline.py

新增节点：

1. volume_planner
2. chapter_planner
3. feedback_synthesizer

目标路由：

1. entry -> volume_planner -> chapter_planner -> writer
2. reviewer(rewrite) -> chapter_planner（而非直接 writer）
3. proofreader(pass) -> feedback_synthesizer -> knowledge_extractor
4. proofreader(fail) -> reviser

说明：

1. chapter_planner 每次进入当前章前刷新 chapter_brief。
2. feedback_synthesizer 将评审结果回写 chapter_brief。
3. 若命中跨层风险，feedback_synthesizer 创建 proposal。

## 6. Agent 改造

文件：agents/creation_agents.py

统一改造项：

1. 每个 Agent 持有 ContextOrchestrator。
2. prompt 输入使用 orchestrator bundle，不再手写大块静态拼接。
3. Agent 间消息必须进入 prompt 上下文，不再只打印日志。
4. 审稿与校对后自动反哺 chapter_brief。

角色级别要求：

1. Writer：
- 默认使用 current brief + neighbor briefs + relevant characters。
- review_round 高于阈值时升级加载前章片段。

2. Reviewer：
- 审稿后写回 chapter_brief 的 revision_focus。
- rewrite 场景可创建卷级提案。

3. Reviser：
- 以 chapter_brief + 必改问题为核心上下文。

4. Proofreader：
- 仅加载与当前章相关角色卡。
- 设定冲突严重时创建 world/character 提案。

## 7. Proposal 协议

proposal 字段：

1. proposal_id
2. target_layer
3. chapter
4. reason
5. diff
6. confidence
7. risk_level
8. status（pending/approved/rejected）
9. timestamp

当前版本仅实现 pending 写入，不实现自动审批。

## 8. 可观测性

最小可观测输出：

1. state.context_decisions
2. state.proposals
3. chapter_brief.feedback_history

用于后续在 API 与调试脚本里查看。

## 9. MVP 验收标准

1. writer/reviewer/reviser/proofreader 都通过 ContextOrchestrator 组装上下文。
2. chapter_briefs 能被 planner 生成并被 writer 使用。
3. proofreader 通过后会进入 feedback_synthesizer 并更新 chapter_brief。
4. 至少一类跨层冲突会生成 proposal。

## 10. 非目标（本次不做）

1. 自动审批与回滚执行器。
2. 向量检索驱动的语义相关性选择。
3. token 级精确计量（本次使用字符预算近似）。
4. Web 控制台可视化管理提案。
