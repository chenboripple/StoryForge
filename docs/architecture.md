# 系统架构

## 整体架构

StoryForge 是一个多 Agent 小说创作与 IP 衍生平台，基于 LangGraph 流程编排与 CrewAI 风格角色系统构建：

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Web 前端层                                   │
├─────────────────────────────────────────────────────────────────────┤
│  web_console/  (FastAPI, 端口 8787)                                 │
│  - routes/v1/ 仅保留 v1 APIRouter（/api/v1/）                       │
│  - routes/__init__.py 路由聚合入口（v1-only）                        │
│  - services/ 业务实现（ip / video / vector / novels）               │
│  - runtime/  TaskRegistry（任务队列、状态持久化）、模板白名单       │
│  - middleware/ 统一错误处理、请求 ID、CORS                          │
│  - security.py  上传安全、路径安全                                  │
│  - app.py    实例化 + include_router + React 构建产物静态托管       │
├─────────────────────────────────────────────────────────────────────┤
│                         存储层                                       │
│  - ~/.storyforge/data/  (小说数据, YAML 配置决定)                    │
│  - local_store/vector_store.jsonl  (向量库)                         │
│  - local_store/ip_assets/  (IP 资产)                                │
│  - debug_output/  (调试输出)                                        │
│  - video_assets/  (视频生成中间产物：剧本、视觉圣经、渲染计划、检查报告) │
├─────────────────────────────────────────────────────────────────────┤
│                       Pipeline 层 (LangGraph)                         │
┌─────────────────────────────────────────────────────────────────────┐
│  创作阶段：outline_refiner → writer → reviewer → reviser → proofread │
│  萃取阶段：knowledge_extractor  (从章节提取知识 → memory)            │
│  IP 阶段：ip_designer  (生成 story bible + 人物 IP)                  │
│  视频阶段（可选）：video_script → visual_bible → video_assets → video_consistency → video_generate │
│  支持：checkpoint 断点续跑、条件路由、AI 味检测                       │
├─────────────────────────────────────────────────────────────────────┤
│                        Agent 层                                      │
┌─────────────────────────────────────────────────────────────────────┐
│  Writer(墨川) | Reviewer(青锋) | Reviser(墨川) | Proofreader(砚清)  │
│  支持：MessageBus (Agent 间通讯)、memory、JSON 结构化输出            │
├─────────────────────────────────────────────────────────────────────┤
│                        Core 层                                       │
┌─────────────────────────────────────────────────────────────────────┐
│  core/models/content/   NovelMeta, Chapter, Outline, Review, Proofread│
│  core/models/world/     Characters, WorldSetting                    │
│  core/models/agent/     BaseAgent, AgentPersona, MessageBus         │
│  core/models/extraction/  KnowledgeExtractor, ChapterAnalysis       │
│  core/models/ip/        IPAssets, StoryBible                       │
│  core/models/video/     VideoScript, VisualBible, ConsistencyReport│
│  core/config.py         ~/.storyforge/storyforge.yaml  (全系统配置) │
├─────────────────────────────────────────────────────────────────────┤
│                       stages/ 模块                                   │
│  stages/outline/         OutlineGenerator (章级细纲生成)            │
│  stages/extraction/      KnowledgeExtractor (知识萃取)              │
│  stages/ip_generation/   IPGenerator (IP 资产生成)                 │
└─────────────────────────────────────────────────────────────────────┘
```

## 配置系统说明

StoryForge 使用单一配置文件：

- 文件位置：`~/.storyforge/storyforge.yaml`
- 加载入口：`core/config.py`
- 用途：FastAPI API 网关、Pipeline 与存储路径

配置结构：

```yaml
llm:
    provider: mock/openai/anthropic
    model: gpt-4o-mini
    api_key: ""
    base_url: ""
    temperature: 0.7
    timeout: 60
    extra: {}

storage:
    data_dir: ~/.storyforge/data

server:
    host: 127.0.0.1
    port: 8787
    cors_origins: ["http://localhost:3000", "http://127.0.0.1:3000"]
    cors_allow_credentials: false
    debug: false

security:
    max_upload_size: 52428800  # 50MB
    allowed_upload_extensions: null  # null 使用默认类型

pipeline:
    max_review_rounds: 3
    default_target_word_count: 3000

console:
    max_running_tasks: 3
    default_command: python examples/demo_pipeline.py
    template_file: ~/.storyforge/templates.yaml

debug:
    output_dir: debug_output
```

## 依赖注入策略

网关采用 **每请求 scoped DI**：

- 每个 HTTP 请求通过 FastAPI `Depends` 创建独立 `StorageManager` 实例
- 不在请求之间共享 `StorageManager` 内存缓存，降低跨请求状态污染风险
- 后台队列任务（pipeline/ip）不走请求上下文，按任务执行周期创建独立存储实例

实现位置：`web_console/dependencies.py` 中 `get_storage_manager_dep()` 与 `_new_storage_manager()`。

## TaskRegistry 全局状态管理

`web_console/runtime/registry.py` 中的 `TaskRegistry` 封装了所有任务相关状态：

- `tasks` - Pipeline 任务运行时
- `ip_tasks` - IP 生成任务运行时
- `task_queue` - 任务队列
- `task_runners` - 任务执行器注册表

任务运行时统一由 `web_console/runtime/registry.py` 的 `TaskRegistry` 承载，API 层通过依赖注入访问。

## 中间件与错误处理

- **RequestIdMiddleware**：为每个请求生成/传递唯一 ID（`X-Request-ID` 响应头）
- **统一错误处理**：标准错误响应格式，含 `request_id`、`error_code`、`details`
- **CORS 中间件**：可配置的跨域策略

## API 版本管理

- **新版 API**：`/api/v1/` 前缀
  - `/api/v1/health`
  - `/api/v1/novels`
  - `/api/v1/tasks`
  - `/api/v1/import`
    - `/api/v1/ip/{novel_id}/...`
    - `/api/v1/video/{novel_id}/...`

- 当前仅保留 **v1 API**，不再维护 `/api/` 旧前缀兼容层。
- `/api/*`（非 `/api/v1/*`）统一返回 `410 Gone`，用于明确迁移信号。

## 设计原则

### 状态驱动

所有 Agent 节点读写同一个 `NovelState` 对象：
- 输入：当前全局状态
- 输出：更新后的全局状态
- LangGraph 负责状态的流转和持久化
- `to_dict()` / `from_dict()` 支持完整的 JSON 序列化与反序列化（含枚举、嵌套 dataclass、int 章节键）

### 角色即提示词工程

`AgentPersona` 的每个字段都有明确的工程用途：
- `backstory`：影响 LLM 语气和知识倾向
- `expertise`：影响任务分配和工具使用
- `tone`：影响输出文本的调性
- `principles`：影响决策逻辑
- `constraints`：影响输出边界

### 结构化输出 + 人味化

- 审稿/校对使用 JSON Schema 确保可解析
- PromptAssembler 自动集成人味化规则：禁用 AI 常见句式、提升文本自然度
- AI 味检测（low/medium/high）：high 等级自动触发重写

### 记忆系统

- StoryMemory：事件时间线 + 人物状态 + 世界设定
- 一致性检查：自动检测人物名字、设定、时间线矛盾
- 用于创作上下文注入

### Agent 间通讯 (MessageBus)

- 发布/订阅模式
- 按类型过滤
- 定向投递
- 消息持久化

## 阶段详解

### 阶段一：创作 (Creation)

1. **大纲细化** (outline_refiner)：从卷纲生成章级细纲
2. **写作** (writer)：基于细纲创作章节
3. **审稿** (reviewer)：8维度结构化评分 + AI味评估
4. **修改** (reviser)：根据审稿意见修改
5. **校对** (proofreader)：6层级检查 + 终审判定（可发布/可交付/需返修）

### 阶段二：萃取 (Extraction)

- 从章节提取事件、人物、伏笔
- 构建知识图谱
- 更新 memory

### 阶段三：IP 生成 (IP Generation)

- 生成 story bible
- 人物 IP 资产（人设、台词、画像提示词）
- 存入 `local_store/ip_assets/`

## 状态字段分组

`NovelMeta` 与相关模型按领域分组在 `core/models/content/`：

```python
# 元数据
novel_id, novel_title, genre, target_word_count, current_stage

# 创作层
concept, outline, volume_outline, characters
chapters, chapter_status, current_chapter, review_round
reviews, structured_reviews, proofread_results, proofread_records
proofread_scope, proofread_context

# 萃取层
knowledge_base, chapter_analyses

# IP 层
character_ips, visual_assets, story_bible

# 兼容容器（仅存非章节辅助数据）
creation: {chapter_outlines, chapter_summaries, extraction_notes}

# 控制字段
error_message, human_feedback, should_pause
```

## 相关文档

- [Multi-Agent 系统使用指南](MULTI_AGENT_GUIDE.md)
- [Pipeline 流程详解](pipeline.md)
- [API 参考](api-reference.md)
