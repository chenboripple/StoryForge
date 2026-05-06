# 系统架构

## 整体架构

StoryForge 在原有「Pipeline / Agent / Core」三层基础上，扩展出 Web UI、Config、Storage、LLM Factory 等支撑层，整体形成一个可独立运行的多 Agent 创作平台：

```
┌──────────────────────────────────────────────────────────┐
│                    Web UI Layer                          │
│   React 前端（清单页 / 详情页） + Flask 后端（REST API）  │
│   client/  +  backend/app.py                             │
├──────────────────────────────────────────────────────────┤
│                    Storage Layer                         │
│   JSON 文件持久化（index.json + novels/<id>.json）        │
│   backend/storage.py                                     │
├──────────────────────────────────────────────────────────┤
│                    Pipeline Layer                        │
│   (LangGraph 图结构 + 状态机 + 路由)                       │
│   NovelPipeline、条件边、循环边                            │
├──────────────────────────────────────────────────────────┤
│                    Agent Layer                           │
│   (CrewAI 风格角色 + LLM 调用抽象)                         │
│   WriterAgent、ReviewerAgent、ReviserAgent、Proofreader   │
├──────────────────────────────────────────────────────────┤
│                    Core Layer                            │
│   状态定义 + 角色基类 + 任务定义 + 配置 + LLM 工厂          │
│   NovelState、AgentPersona、BaseAgent、Config、LLM Factory│
└──────────────────────────────────────────────────────────┘
```

## 设计原则

### 1. 状态驱动

所有 Agent 节点读写同一个 `NovelState` 对象：
- 输入：当前全局状态
- 输出：更新后的全局状态
- LangGraph 负责状态的流转和持久化
- `to_dict()` / `from_dict()` 支持完整的 JSON 序列化与反序列化（含枚举、嵌套 dataclass、int 章节键）

### 2. 角色即提示词工程

`AgentPersona` 的每个字段都有明确的工程用途：
- `backstory` → 影响 LLM 语气和知识倾向
- `expertise` → 影响任务分配和工具使用
- `tone` → 影响输出文本的调性
- `principles` → 影响决策逻辑
- `constraints` → 影响输出边界

### 3. 纯函数 Agent

每个 Agent 的 `invoke(state) -> state` 是纯函数：
- 不依赖外部状态
- 相同的输入产生相同的输出
- 便于测试、调试和并行化

### 4. 配置外置

所有可调参数（LLM、存储、服务器、Pipeline）统一通过 `.storyforge/storyforge.yaml` 管理：
- 配置文件不入仓（`.gitignore`），可安全填写 API 密钥
- 通过 `core.config.get_config()` 单例访问
- 部署脚本 `deploy.sh` 与 Flask 后端共用同一份配置

### 5. LLM 抽象

通过 `core.llm_factory.create_llm_client(cfg)` 工厂函数屏蔽 provider 差异：
- 内置 `mock`、`openai`、`anthropic` 三种 provider
- 兼容 OpenAI 协议的服务（DeepSeek、vLLM 等）通过 `base_url` 切换
- 客户端是简单的 `(prompt, temperature) -> str` 闭包，与上层完全解耦

## 数据流

```
NovelState (初始)
    │
    ▼
┌─────────────┐
│   writer    │ ──LLM──► 生成章节内容
└─────────────┘
    │
    ▼ NovelState (含章节内容)
┌─────────────┐
│  reviewer   │ ──LLM──► 评分 + 审稿意见
└─────────────┘
    │
    ▼ NovelState (含审稿记录)
┌─────────────┐
│  _router_   │ ──逻辑──► 条件路由
└─────────────┘
    │  ≥85分      60-84分      <60分
    ▼             ▼            ▼
┌──────┐    ┌──────────┐  ┌────────┐
│proof │    │ reviser  │  │ writer │
│reader│    │(修改)    │  │(重写)  │
└──────┘    └──────────┘  └────────┘
    │             │
    ▼             ▼ (循环)
  结束        reviewer
    │
    ▼
┌─────────────┐
│  storage    │ ──JSON──► data/novels/<id>.json
│ save_novel  │ ──索引──► data/index.json
└─────────────┘
    │
    ▼
┌─────────────┐
│  Flask API  │ ──HTTP──► React 前端
│  /api/...   │
└─────────────┘
```

## 模块职责

| 模块 | 路径 | 职责 |
|------|------|------|
| Core | `core/` | 状态、角色、任务、配置、LLM 工厂等基础设施 |
| Agents | `agents/` | 具体 Agent 实现（写作、审稿、修改、校对） |
| Pipeline | `pipeline/` | LangGraph 流程编排与路由 |
| Backend | `backend/` | Flask Web 服务 + JSON 存储层 |
| Client | `client/` | React 前端（小说清单 / 详情页 / 章节预览） |
| Examples | `examples/` | 端到端演示（含 `--save` 选项写入 storage） |
| Deploy | `deploy.sh` | 一键部署脚本（依赖安装、前端构建、gunicorn 守护进程） |

## 状态字段分组

`NovelState` 按阶段分组：

```python
# 元数据
novel_id, novel_title, genre, target_word_count, current_stage

# 阶段一：创作层
concept, outline, volume_outline, characters
chapters, chapter_status
current_chapter, review_round, max_review_rounds
reviews, proofread_records

# 阶段二：萃取层（预留）
knowledge_base

# 阶段三：IP 生成层（预留）
character_ips, visual_assets

# 控制字段
error_message, human_feedback, should_pause
```

## 启动链路

```
deploy.sh
   │
   ├─► 读取 .storyforge/storyforge.yaml（通过临时 Python 进程）
   │
   ├─► 安装 Python 依赖 + 构建前端
   │
   └─► gunicorn -w 2 -b host:port backend.app:app --daemon
                         │
                         ▼
                  backend/app.py
                         │
                         ├─► get_config()           ← core/config.py
                         ├─► storage.list_novels()  ← backend/storage.py
                         └─► serve client/build/    ← React 静态资源
```

## 相关文档

- [Agent 系统设计](agent-system.md)
- [Pipeline 流程详解](pipeline.md)
- [Web API 参考](api-reference.md)
- [配置系统说明](config.md)
