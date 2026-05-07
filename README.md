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
- **Web UI**: Flask 后端 + React 前端，展示小说清单和创作进展

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
# 安装前端依赖
pip install -r requirements-web.txt
cd client
npm install
npm run build
cd ..

# 启动后端
python backend/app.py

# 访问 http://localhost:5089
```

开发模式：
```bash
# 终端 1: 启动后端（自动重载）
python backend/app.py

# 终端 2: 启动前端 dev server
cd client
npm start
```

### FastAPI 操作界面（web_console）

```bash
uvicorn web_console.app:app --reload --port 8787
```

浏览器访问 `http://127.0.0.1:8787`。支持启动任务、查看状态、查看日志、停止任务、模板保存、并发上限控制、人物 IP 生成等。

---

## 配置

StoryForge 使用两套配置系统（历史原因，两者共存）。完整说明见 [docs/config.md](docs/config.md)。

### 配置系统一：web_console (JSON)

用于 FastAPI 操作界面。

- 文件：`~/.storyforge/config.json`
- 加载入口：`core/settings.py`
- 优先级：环境变量 > 配置文件

```json
{
  "console": {
    "max_running_tasks": 2,
    "default_command": "python examples/debug_pipeline.py",
    "template_file": "~/work/StoryForge/web_console/templates.json"
  },
  "debug": {
    "output_dir": "~/work/StoryForge/debug_output"
  },
  "pipeline": {
    "default_target_word_count": 3000
  }
}
```

### 配置系统二：backend (YAML)

用于 Flask API 服务和核心 Pipeline。

- 文件：`~/.storyforge/storyforge.yaml`（推荐）
- 加载入口：`core/config.py`
- 优先级：`$STORYFORGE_CONFIG` > `~/.storyforge/storyforge.yaml` > 项目根目录配置 > 默认值

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
    port: 5089
    cors_origins: "*"

pipeline:
    max_review_rounds: 3
    default_target_word_count: 3000
```

### 诊断命令

```bash
# 查看当前 YAML 配置（含来源）
python -m core.config

# 查看当前 JSON 配置（含来源）
python -m core.settings

# 仅校验 JSON 配置（成功返回 0，失败非 0）
python -m core.settings --check
```

---

## 项目结构

```
StoryForge/
├── core/                   # 核心基类
│   ├── state.py            # NovelState 状态管理
│   ├── agent.py            # BaseAgent + MessageBus
│   ├── schema.py           # 结构化输出 Schema
│   ├── memory.py           # 记忆系统
│   ├── prompt_assembler.py # 动态 Prompt 组装
│   ├── config.py           # YAML 配置（backend）
│   ├── settings.py         # JSON 配置（web_console）
│   └── utils/              # 工具函数
├── agents/                 # Agent 角色定义
│   └── creation_agents.py  # Writer / Reviewer / Reviser / Proofreader
├── pipeline/               # LangGraph 流程定义
│   └── novel_pipeline.py   # 完整 Pipeline + 路由逻辑
├── stages/                 # 功能模块
│   ├── outline/            # 大纲细化
│   ├── extraction/         # 知识萃取
│   └── ip_generation/      # IP 生成
├── backend/                # Flask 后端 API
│   ├── app.py              # API 服务
│   └── storage.py          # JSON 存储层
├── client/                 # React 前端
│   ├── src/
│   │   ├── App.jsx
│   │   ├── api/client.js
│   │   └── pages/          # 页面组件
│   └── package.json
├── web_console/            # FastAPI 操作界面
│   └── app.py
├── examples/               # 示例脚本
│   ├── debug_pipeline.py   # 调试脚本（推荐）
│   ├── demo_pipeline.py    # 基础演示
│   └── multi_agent_demo.py # 多 Agent 演示
├── docs/                   # 文档
├── data/                   # 数据存储（可选）
├── tests/                  # 测试
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
