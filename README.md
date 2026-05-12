# StoryForge

基于 LangGraph + CrewAI 风格角色系统的多 Agent 小说创作与 IP 衍生平台。

---

## 架构

- **LangGraph**: 流程编排与状态管理
- **CrewAI 风格**: 角色人设与任务定义
- **多 Agent 协作**: MessageBus 消息总线 + 自主路由建议
- **三阶段 Pipeline**: 创作 → 萃取 → IP 生成
- **结构化输出**: JSON Schema 确保 LLM 输出可解析
- **记忆系统**: 事件时间线 + 角色状态追踪
- **人味化规则**: 禁用 AI 常见句式，提升文本自然度
- **Web UI**: FastAPI 网关 + React 前端，展示小说清单和创作进展

---

## 快速开始

### 核心 Pipeline

```bash
pip install -r requirements.txt
python examples/debug_pipeline.py
```

### 多 Agent 演示

```bash
# 默认模式（启用 MessageBus，记录路由建议）
python examples/multi_agent_demo.py

# 启用 Agent 自主路由
python examples/multi_agent_demo.py --agent-routing
```

详细多 Agent 功能说明见 [docs/MULTI_AGENT_GUIDE.md](docs/MULTI_AGENT_GUIDE.md)。

### Web UI

```bash
# 安装后端依赖
pip install -r requirements.txt
cd client
npm install
npm run build
cd ..

# 启动统一 API 网关（FastAPI）
uvicorn web_console.app:app --reload --port 8787

# 访问 http://127.0.0.1:8787
```

开发模式：
```bash
# 终端 1: 启动 FastAPI 网关
uvicorn web_console.app:app --reload --port 8787

# 终端 2: 启动前端 dev server
cd client
npm start
```

### FastAPI 操作界面（web_console）

```bash
uvicorn web_console.app:app --reload --port 8787
```

浏览器访问 `http://127.0.0.1:8787`，根路径直接服务 `client/build/` 的 React UI。若尚未执行 `npm run build`，根路径会返回 JSON 提示。

`web_console/` 内部按职责分层：

- `routes/`   - 按领域分组的 APIRouter（health/tasks/templates/novels/import/ip/video/ai）
  - `routes/v1/` - 版本化 API（/api/v1/）
- `services/` - 业务实现（ip / video / vector / novels）
- `runtime/`  - TaskRegistry（任务队列、状态持久化）、模板白名单
- `middleware/` - 统一错误处理、请求 ID、CORS
- `security.py` - 文件上传安全、路径安全
- `app.py`    - FastAPI 实例化、生命周期管理、路由聚合、React 静态托管（含 SPA fallback）

### API 版本管理

- **新版 API**：`/api/v1/` 前缀（推荐）
- **旧版 API**：`/api/` 前缀（保持向后兼容）

详见 [docs/api-reference.md](docs/api-reference.md)。

---

## 配置

StoryForge 当前使用单一配置文件：`~/.storyforge/storyforge.yaml`。

- 配置文件：`~/.storyforge/storyforge.yaml`
- 加载入口：`core/config.py`
- 适用范围：FastAPI 网关（web_console）、核心 Pipeline

```yaml
llm:
    provider: mock
    model: gpt-4o-mini
    api_key: ""
    base_url: ""
    temperature: 0.7
    timeout: 60
    extra: {}

storage:
    data_dir: ~/.storyforge/data

server:
    host: 0.0.0.0
    port: 8787
    cors_origins: ["*"]  # 允许的源列表，或 "*" 表示全部
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
  template_file: ~/.storyforge/templates.json

debug:
  output_dir: debug_output
```

### 诊断命令

```bash
# 查看当前生效配置（含来源）
python -m core.config
```

---

## 项目结构

```
StoryForge/
├── core/                   # 核心基类
│   ├── models/             # 数据模型（按领域分组）
│   │   ├── content/        # 内容相关：NovelMeta, Chapter, Outline, Review, Proofread
│   │   ├── world/          # 世界设定：Characters, WorldSetting
│   │   ├── agent/          # Agent相关：AgentPersona, MessageBus
│   │   ├── extraction/     # 萃取相关：KnowledgeExtractor, ChapterAnalysis
│   │   ├── ip/             # IP相关：IPAssets, StoryBible
│   │   └── video/          # 视频相关：VideoScript, VisualBible, ConsistencyReport
│   ├── config.py           # YAML 配置（全系统）
│   ├── storage/            # 存储管理
│   └── utils/              # 工具函数
├── agents/                 # Agent 角色定义
│   └── creation_agents.py  # Writer / Reviewer / Reviser / Proofreader
├── pipeline/               # LangGraph 流程定义
│   └── novel_pipeline.py   # 完整 Pipeline + 路由逻辑
├── stages/                 # 功能模块
│   ├── outline/            # 大纲细化
│   ├── extraction/         # 知识萃取
│   └── ip_generation/      # IP 生成
├── client/                 # React 前端
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api/client.js
│   │   └── pages/          # 页面组件
│   └── package.json
├── web_console/            # FastAPI 操作界面
│   ├── app.py              # FastAPI 实例化、路由聚合、生命周期管理、SPA 托管
│   ├── middleware/         # 中间件：统一错误处理、请求 ID、CORS
│   ├── dependencies.py     # DI 提供器（StorageManager, TaskRegistry）
│   ├── security.py         # 安全工具：路径安全、上传验证
│   ├── utils.py            # 通用工具函数
│   ├── routes/             # 按领域分组的 APIRouter（含 /api/v1/ 版本化）
│   ├── services/           # 业务实现（ip / video / vector / novels）
│   └── runtime/            # 任务队列、TaskRegistry、状态持久化、模板白名单
├── examples/               # 示例脚本
│   ├── debug_pipeline.py   # 调试脚本（推荐）
│   ├── demo_pipeline.py    # 基础演示
│   └── multi_agent_demo.py # 多 Agent 演示
├── tests/                  # 测试
├── docs/                   # 文档
├── LICENSE                 # 许可证
└── deploy.sh               # 部署脚本
```

---

## 核心特性

### 1. 多 Agent 协作

- **MessageBus**: Agent 间消息传递系统
- **路由建议**: Agent 可以建议 Pipeline 下一步动作
- **渐进式启用**: 先记录后决策，逐步替代硬编码路由

详细说明见 [docs/MULTI_AGENT_GUIDE.md](docs/MULTI_AGENT_GUIDE.md)。

### 2. 大纲细化阶段

- 基于卷纲生成章级细纲
- 包含：场景列表、字数分配、伏笔规划

### 3. PromptAssembler 动态组装

- 根据上下文动态构建 prompt
- 融入人味化规则（禁用 AI 常见句式）
- 支持审稿/校对/写作三种模式

### 4. 结构化审稿（8 维度）

- 叙事结构、人物一致性、文学性、市场潜力
- AI 味评估（低/中/高）
- 位置一致性检查
- 元叙事穿帮检测

### 5. 结构化校对（6 层级）

- 基础层、设定层、时间线层、人物层、地理层、伏笔层
- 终审判定：可发布 / 可交付 / 需返修

### 6. 智能路由

- AI 味过高 → 自动重写
- 终审不通过 → 返回修改
- 审稿通过 → 进入校对

### 7. 视频生成（实验性）

- 支持从小说内容自动生成视频相关资产：镜头剧本（VideoScript）、视觉圣经（VisualBible）、镜头级视觉资产与渲染计划
- 流程（Pipeline 节点）：`video_script` → `visual_bible` → `video_assets` → `video_consistency` → `video_generate`
- 控制台 API（web_console）支持手动触发：`POST /api/video/script/generate`、`POST /api/video/consistency/check`、`GET /api/video/consistency/{novel_id}`
- 存储：视频相关的中间产物与报告由 `StorageManager` 统一持久化（`video_script`, `visual_bible`, `video_render_plan`, `video_output`, `video_consistency_report`）
- Provider 抽象：Image / Video / Embedding Provider 为抽象接口，仓库内含占位实现（stub），可以在 `~/.storyforge/storyforge.yaml` 中配置真实供应商

> 注意：视频生成功能目前为首阶段实现（骨架 + 可量化一致性检查），实际生成需要接入具体的 Image/Video/Embedding 服务并调优阈值。

---

## 调试

调试脚本会自动保存：
- 每个 LLM 调用的完整 prompt
- 所有 prompt 调用历史（JSON）
- Pipeline 运行前后的状态快照

```bash
# 查看保存的 prompt
cat debug_output/prompt_*.txt

# 查看状态变化
cat debug_output/state_initial.json
cat debug_output/state_final_*.json
```

---

## 角色系统

| 角色 | 职责 | 特点 |
|------|------|------|
| Writer | 小说家 | 冷峻理性，物理背景 |
| Reviewer | 文学编辑 | 犀利直接，20年经验 |
| Reviser | 修改编辑 | 根据审稿意见修改 |
| Proofreader | 校对专家 | 严谨细致，处女座 |

---

## 许可证

### 代码（MIT）

```
Copyright (c) 2026 StoryForge Contributors

Permission is hereby granted, free of charge...
```

详见 [LICENSE](LICENSE)。

### 生成内容（CC BY-NC-SA 4.0）

StoryForge 生成的内容（小说、角色、视觉资产）使用 **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International** 许可证。

- ✅ 个人使用和非商业分享
- ✅ 修改和衍生作品（必须保持相同许可证）
- ❌ 未经许可的商业使用
- ❌ 创建闭源衍生品

商业许可咨询请联系项目维护者。

---

## 文档

- [MULTI_AGENT_GUIDE.md](docs/MULTI_AGENT_GUIDE.md) - 多 Agent 系统使用指南
- [config.md](docs/config.md) - 配置系统完整说明
- [architecture.md](docs/architecture.md) - 系统架构设计
- [pipeline.md](docs/pipeline.md) - Pipeline 流程详解
- [api-reference.md](docs/api-reference.md) - API 参考
- [config-example.md](docs/config-example.md) - 配置示例
