# StoryForge 当前实现与后续计划

## 当前实现

StoryForge 当前已经具备一条可运行的小说生产链路，核心能力集中在以下几个方面：

1. 创作 Pipeline
- LangGraph 编排的 `volume_planner -> chapter_planner -> writer -> reviewer -> reviser -> proofreader -> feedback_synthesizer -> knowledge_extractor -> ip_designer` 主链路已接通。
- 可选视频链路已包含 `video_script`、`visual_bible`、`video_assets`、`video_consistency`、`video_generate` 节点。

2. 多 Agent 协作
- `BaseAgent`、`MessageBus`、`AgentPersona` 已形成统一基座。
- Writer、Reviewer、Reviser、Proofreader、VisualDirector、CharacterVisual 等 Agent 已接入实际业务。

3. 状态与模型体系
- `core/models` 以 `content / world / agent / extraction / ip / video` 六个分组作为唯一模型入口。
- `NovelState` 已收口到正式模型类型，不再维护重复的 review/proofread/character 运行时副本。

4. 存储与任务系统
- `StorageManager` 按小说目录拆分存储 `novel_meta`、`chapters`、`reviews`、`proofreads`、`story_bible`、视频状态等数据。
- `web_console/runtime/registry.py` 已统一承载 pipeline / ip / visual 三类任务运行态。

5. Web Console 与视觉资产
- FastAPI + React 的控制台支持小说创建、导入、章节任务、校对、角色视觉、封面、IP 与视频状态查看。
- 视觉服务已统一收口到共享 helper 和 workflow，图片支持本地持久化与 `/api/v1/media/generated/*` 访问。

## 当前重点约束

1. 文档与代码应统一使用分组模型入口，例如 `core.models.content`、`core.models.video`、`core.models.ip`。
2. 当前 `/api/v1/health` 仍然存在，相关 smoke test 预期需要与现状保持一致。
3. `progressive disclosure` 相关能力已具备基础状态字段与节点，但仍属于持续完善中的主题。

## 后续计划

1. 文档收敛
- 继续清理剩余过时表述，统一改为“当前实现 + 后续计划”。
- 将 API、架构、配置文档统一指向当前目录结构和 v1 API。

2. 创作链路增强
- 把 `NovelState.creation` 中剩余辅助字段进一步瘦身，只保留必要兼容信息。
- 继续提升 feedback/proposal 的可视化与审批体验。

3. 视频与 IP 产物增强
- 为 `StoryBible`、`VideoState`、`VisualBible` 增加更多面向 Web Console 的摘要视图。
- 为视频链路补充更真实的 provider 对接，而不只停留在 stub/provider skeleton。

4. 运行质量与成本控制
- 完善 `CostTracker` 与模型路由统计。
- 把多模型路由结果暴露到 Web Console 或调试接口，便于观察任务执行质量。
