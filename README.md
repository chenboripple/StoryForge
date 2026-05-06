# StoryForge

基于 LangGraph + CrewAI 风格角色系统的多 Agent 小说创作与 IP 衍生平台。

## 特性

- **多 Agent 协作创作** — 小说家（墨川）、编辑（青锋）、校对（砚清）各司其职
- **审稿-修改闭环** — 图结构实现循环审稿，自动触发修改直到达标
- **角色即提示词工程** — 产品人设直接转化为系统提示词注入 LLM
- **三阶段 Pipeline** — 创作（Creation）→ 萃取（Extraction）→ IP 生成（IP Generation）
- **Web UI** — 小说清单页、详情页、章节预览、Pipeline 进度可视化
- **统一配置** — 基于 YAML 的配置系统，包含 LLM、存储、服务器等所有设置
- **持久化存储** — 自动保存到 JSON，支持清单索引和状态查询 API

## 项目结构

```
StoryForge/
├── core/                      # 核心基类
│   ├── agent.py               # AgentPersona、BaseAgent、Task
│   ├── state.py               # NovelState、ReviewRecord、ProofreadRecord 等状态定义
│   ├── config.py              # 配置系统（YAML 解析、路径解析）
│   └── llm_factory.py         # LLM 客户端工厂（mock/openai/anthropic）
├── agents/                    # Agent 角色实现
│   └── creation_agents.py     # WriterAgent、ReviewerAgent、ReviserAgent、ProofreaderAgent
├── pipeline/                  # LangGraph 流程编排
│   └── novel_pipeline.py      # NovelPipeline、路由逻辑
├── backend/                   # Web 后端（Flask）
│   ├── __init__.py
│   ├── app.py                 # Flask 应用 + API 端点
│   └── storage.py             # JSON 存储层（保存/加载/索引）
├── client/                    # Web 前端（React）
│   ├── src/
│   │   ├── App.jsx
│   │   ├── index.css
│   │   ├── api/client.js
│   │   └── pages/
│   │       ├── NovelList.jsx
│   │       └── NovelDetail.jsx
│   ├── public/index.html
│   ├── package.json
│   └── README.md
├── examples/                  # 示例
│   └── demo_pipeline.py       # 完整演示（含 Mock LLM + 保存到 Storage）
├── data/                      # JSON 数据目录
│   ├── index.json             # 小说清单索引
│   └── novels/                # 单个小说完整状态
│       └── *.json
├── .storyforge/               # 配置目录
│   ├── storyforge.yaml        # 实际运行配置（.gitignore）
│   └── storyforge.example.yaml # 配置模板
├── docs/                      # 文档
├── deploy.sh                  # 自动部署脚本
├── requirements.txt           # 核心依赖
├── requirements-web.txt       # Web 服务依赖
├── LICENSE
└── README.md
```

## 快速开始

### 方式一：一键部署（推荐）

```bash
# 首次运行会自动复制配置文件
./deploy.sh
```

部署后访问 http://localhost:5089

### 方式二：手动安装

#### 1. 安装依赖

```bash
# 核心依赖
pip install -r requirements.txt

# Web 服务依赖
pip install -r requirements-web.txt
```

#### 2. 配置

编辑 `.storyforge/storyforge.yaml`：

```yaml
llm:
  provider: mock        # 或 openai/anthropic
  api_key: ""           # 你的 API Key
  model: gpt-4o-mini

server:
  port: 5089            # 服务端口

storage:
  data_dir: ./data      # 数据存储目录
```

#### 3. 运行示例并保存

```bash
python examples/demo_pipeline.py --save
```

#### 4. 启动服务

```bash
# 开发模式（自动重载）
python backend/app.py

# 或生产模式（gunicorn 常驻后台）
./deploy.sh start
```

访问 http://localhost:5089 查看 Web UI

### 核心用法（Python API）

```python
from core.state import NovelState, CharacterInfo
from core.config import get_config
from core.llm_factory import create_llm_client
from pipeline.novel_pipeline import create_pipeline

# 1. 加载配置（自动从 .storyforge/storyforge.yaml 读取）
config = get_config()

# 2. 根据配置创建 LLM 客户端
llm = create_llm_client(config.llm)

# 3. 创建 Pipeline
pipeline = create_pipeline(llm_client=llm)

# 4. 准备初始状态
state = NovelState(
    novel_id="novel_001",
    novel_title="熵塔",
    genre="科幻末日",
    target_word_count=3000,
    current_chapter=1,
    concept="末日后的世界，主角发现父亲参与的禁忌实验",
    outline="第一卷：崩塌\n第1章：观测塔废墟...",
    characters=[
        CharacterInfo(
            name="林晚",
            personality="理性、果断",
            background="前物理学家"
        )
    ]
)

# 5. 运行（单章）
result = pipeline.run(state)

# 6. 保存到 Storage
from backend import storage
storage.save_novel(result)
```

## 部署命令

```bash
# 查看当前配置
./deploy.sh config

# 完整部署（安装依赖+构建前端+启动后台服务）
./deploy.sh

# 启动/停止/重启
./deploy.sh start
./deploy.sh stop
./deploy.sh restart

# 查看状态
./deploy.sh status

# 查看日志
./deploy.sh logs          # 错误日志
./deploy.sh logs access   # 访问日志
./deploy.sh logs all      # 所有日志
```

## API 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/health` | GET | 健康检查（返回当前配置路径、数据目录） |
| `/api/novels` | GET | 获取小说清单（轻量索引） |
| `/api/novels/<novel_id>` | GET | 获取单个小说完整状态 |
| `/api/novels/<novel_id>/chapters` | GET | 获取章节列表（含状态、字数、分数预览） |
| `/api/novels/<novel_id>/chapters/<chapter_num>` | GET | 获取章节内容和完整审稿/校对记录 |

## 核心设计

### 1. Agent 角色系统

每个 Agent 有完整的人设，自动转化为系统提示词：

| Agent | 人设 | 职责 |
|-------|------|------|
| **墨川** | 职业小说家 | 基于大纲创作章节 |
| **青锋** | 资深文学编辑 | 从结构/人物/文学性三维审稿 |
| **砚清** | 文字校对专家 | 消除错字、逻辑漏洞、设定矛盾 |

### 2. Pipeline 流程图

```
writer(写作) → reviewer(审稿)
                     ↓
              ┌────┴────┐
           ≥85分   60-84分   <60分
              ↓        ↓         ↓
        proofreader  reviser   writer
        (校对)      (修改)    (重写)
              ↓        ↓
              └────┬────┘
              approved
                   ↓
         knowledge_extractor
              (知识萃取)
                   ↓
            ip_designer
              (IP 生成)
                   ↓
                  END
```

审稿循环支持最多 3 轮，超过则强制进入下一节点，避免死循环。

### 3. 状态管理

`NovelState` 是贯穿整个 Pipeline 的全局状态对象，包含：

- 小说元数据（标题、类型、字数目标）
- 大纲与角色设定
- 章节内容与状态
- **审稿记录**（`reviews`）和**校对记录**（`proofread_records`）独立存储
- Human-in-the-loop 接口（`human_feedback`、`should_pause`）

**新增方法（用于 Web UI）**：
- `to_dict()` → 序列化为 JSON 友好的字典
- `to_index_entry()` → 生成清单页所需的轻量索引
- `from_dict(data)` → 从字典安全还原（支持字符串 key 的章节反序列化为 int）

### 4. 配置系统

统一通过 `.storyforge/storyforge.yaml` 配置：

```yaml
llm:
  provider: mock/openai/anthropic
  model: gpt-4o-mini
  api_key: "sk-..."
  base_url: ""                # 自定义 endpoint（可选）
  temperature: 0.7

storage:
  data_dir: ./data

server:
  host: 0.0.0.0
  port: 5089
  cors_origins: "*"

pipeline:
  max_review_rounds: 3
  default_target_word_count: 3000
```

配置加载优先级：
1. `$STORYFORGE_CONFIG` 环境变量指定的路径
2. `<项目根目录>/.storyforge/storyforge.yaml`
3. `~/.storyforge/storyforge.yaml`
4. 内置默认值

## 文档

- [系统架构](docs/architecture.md)
- [Agent 系统设计](docs/agent-system.md)
- [Pipeline 流程详解](docs/pipeline.md)
- [Web API 参考](docs/api-reference.md)
- [配置系统说明](docs/config.md)

## 许可证

代码采用 MIT 许可证，生成内容采用 CC BY-NC-SA 4.0。
详见 [LICENSE](LICENSE)。
