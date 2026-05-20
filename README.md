<p align="center">
  <h1 align="center">StoryForge</h1>
  <p align="center">
    把写作、审稿、校对、知识萃取与 IP 衍生串成一条可运行的小说流水线
    <br />
    <a href="#-快速开始"><strong>快速开始 »</strong></a>
    <br />
    <br />
    <a href="#-为什么它更像创作工作台">为什么它更像创作工作台</a>
    ·
    <a href="#-核心特性">核心特性</a>
    ·
    <a href="#-使用场景">使用场景</a>
    ·
    <a href="#-文档">文档</a>
  </p>
</p>

---

## ✨ 为什么它更像创作工作台

StoryForge 不是单次 Prompt 包装器，而是一个围绕小说生产流程搭起来的多 Agent 工作台。它把规划、写作、审稿、修改、校对、知识萃取、角色视觉生成和 Web 控制台放进同一个项目里，让你既能跑脚本，也能通过界面管理整部作品。

你能直接得到这些能力：

- 🎭 **多 Agent 创作闭环**：Writer、Reviewer、Reviser、Proofreader 串成可执行流程，不是分散脚本。
- 🔁 **从写到改的真实循环**：章节会经历审稿、返修、校对，再进入萃取和 IP 生成。
- 🧠 **分层规划 + 一致性控制**：支持 volume brief、chapter brief、上下文预算、提案回写。
- 🖥️ **可用的 Web Console**：创建小说、导入文本、发起章节任务、查看封面和角色视觉档案。
- 🎨 **角色与封面视觉生成**：主形象、艺术照、视频立体图、小说封面都已接入任务系统。
- 🎬 **视频链路预留**：镜头剧本、视觉圣经、一致性检查和视频生成节点已在 Pipeline 中接好。

一条典型链路如下：

`volume_planner -> chapter_planner -> writer -> reviewer -> reviser -> proofreader -> feedback_synthesizer -> knowledge_extractor -> ip_designer`

---

## 🚀 快速开始

### 路线 A：先跑通 CLI Pipeline

```bash
# 1. 克隆项目
git clone https://github.com/chenboripple/StoryForge.git
cd StoryForge

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行演示（默认使用 Mock LLM，无需配置）
python examples/debug_pipeline.py
```

这条路线适合先确认核心 Pipeline 能跑通。默认使用 `mock` 配置，不需要 API Key。

### 配置真实 LLM

编辑 `~/.storyforge/storyforge.yaml`：

```yaml
llm:
    provider: openai  # 或 anthropic
    model: gpt-4o-mini
    api_key: "your-api-key-here"
```

更多配置项见 [docs/config.md](docs/config.md) 和 [docs/config-example.md](docs/config-example.md)。

### 路线 B：启动 Web Console

```bash
# 安装前端依赖并构建
cd client
npm install
npm run build
cd ..

# 启动后端
uvicorn web_console.app:app --reload --port 5089

# 或使用常驻服务（macOS，关闭 VS Code 后仍运行）
./deploy.sh service-install
./deploy.sh service-status
```

然后访问 `http://127.0.0.1:5089`。

Web Console 当前可以做这些事：

- 创建小说、重排小说、查看章节与上下文
- 导入 `txt/md`、EPUB、PDF、图片 OCR
- 提交章节生成、章节返修、章节/卷/全书校对任务
- 查看角色列表、小说封面、角色视觉档案
- 查看 proposals 和 context decisions 等调试信息

---

## 🎯 核心特性

### 一眼看懂

| 能力 | 当前实现 | 你能拿它做什么 |
|------|----------|----------------|
| 创作 Pipeline | LangGraph 工作流 + checkpoint | 让章节生成、审稿、返修、校对串起来 |
| 多 Agent 协作 | MessageBus + state 持久化 | 记录角色间消息和路由建议 |
| 分层规划 | volume brief / chapter brief | 让长篇写作不只依赖单次上下文 |
| Web Console | FastAPI + React | 管理小说、任务和导入流程 |
| 视觉生成 | 封面 + 角色 main/gallery/video | 扩展角色资产与展示物料 |
| IP / 视频衍生 | story bible + 视频节点 | 为后续改编保留结构化产物 |

### 🎭 多 Agent 协作

四个专业角色组成的创作团队，通过 MessageBus 互相协作：

| 角色 | 人设 | 职责 |
|------|------|------|
| **墨川** | 冷峻理性，物理背景 | 小说创作 |
| **青锋** | 犀利直接，20年经验 | 结构化审稿 |
| **墨川** (Reviser) | 冷峻理性，擅长返工修稿 | 根据意见修改 |
| **砚清** | 严谨细致，处女座 | 6层级校对 + 终审 |

### 📝 8维度结构化审稿

从多个维度评估小说质量：

- ✅ 叙事结构
- ✅ 人物一致性
- ✅ 文学性
- ✅ 市场潜力
- ✅ AI 味评估（低/中/高，过高自动重写）
- ✅ 位置一致性检查
- ✅ 元叙事穿帮检测

### 🔍 6层级深度校对

不放过任何细节：

1. **基础层** - 错别字、标点
2. **设定层** - 世界观一致性
3. **时间线层** - 时序逻辑
4. **人物层** - 人物行为一致性
5. **地理层** - 空间逻辑
6. **伏笔层** - 伏笔回收检查

### 🧠 记忆系统

自动追踪：

- 📅 事件时间线
- 👤 人物状态变化
- 🌍 世界设定变化
- ⚠️ 一致性问题预警

### 📚 知识萃取与 IP 生成

- 自动从章节提取知识
- 生成故事 bible（设定集）
- 生成人物 IP 资产（人设、台词、画像提示词）

### 🖥️ Web Console 与任务系统

- 统一使用 `/api/v1/*` 路由
- 章节生成、校对、视觉生成走任务队列，便于追踪状态
- 已实现角色视觉档案、小说封面、导入解析、模板命令管理

---

## 💡 使用场景

### 1. 从零开始创作

```python
from core.state import NovelState
from pipeline.novel_pipeline import create_pipeline

pipeline = create_pipeline(llm_client=my_llm)

initial_state = NovelState(
  novel_id="demo_001",
  novel_title="熵塔",
  genre="科幻末日",
  concept="末日后的城市废墟中出现了一段神秘信号",
  outline="第一卷：信号。主角在废墟中发现异样广播，决定出发追查来源。",
  current_chapter=1,
)

result = pipeline.run(initial_state)
```

### 2. 导入已有作品

通过 Web 界面上传：
- 纯文本 (txt/md)
- EPUB 电子书
- PDF 文档
- 图片（OCR 识别）

### 3. 批量生成章节

```python
# 一次性创作多章
results = pipeline.run_batch(state, chapters=[1, 2, 3, 4, 5])
```

### 4. AI 辅助审稿与润色

已有初稿？让 StoryForge 帮你审稿、修改、校对，再把结果回写到后续规划中。

### 5. 角色视觉与封面生产

在 Web Console 中为小说生成封面，并为角色生成：

- `main` 主形象
- `gallery` 艺术照
- `video` 多视角参考图

---

## 📖 文档

- 🏗️ [架构设计](docs/architecture.md) - 了解系统架构
- 🔄 [Pipeline 详解](docs/pipeline.md) - 深入理解创作流程
- 🤖 [多 Agent 指南](docs/MULTI_AGENT_GUIDE.md) - 玩转多 Agent 协作
- 🎨 [角色视觉生成](docs/CHARACTER_VISUAL_GENERATION.md) - 查看视觉生成约束与 API
- 📡 [API 参考](docs/api-reference.md) - 完整的 API 文档
- ⚙️ [配置说明](docs/config.md) - 配置文件结构与字段解释

---

## 当前版本

- 当前仓库以 `core.models.content / world / agent / extraction / ip / video` 作为统一模型入口。
- Web Console 统一使用 `/api/v1/*` 路由，支持常驻服务、任务队列和本地图片持久化。
- IP 与 Video 相关共享逻辑已经分别收口到 `core/ip_workflow.py` 和 `core/video/workflow.py`。

## 后续计划

1. 继续增强 Web Console 的任务反馈与提案审批体验。
2. 补全视频 provider 的真实接入，而不只保留 stub/provider skeleton。
3. 继续压缩兼容层，让运行态和正式模型保持更一致的结构。

---

## 🛠️ 项目结构

```
StoryForge/
├── core/                   # 核心模块
│   ├── models/             # 数据模型（按领域分组）
│   ├── config.py           # 配置管理
│   ├── storage/            # 存储管理
│   └── state.py            # Pipeline 运行态
├── agents/                 # Agent 角色定义
├── pipeline/               # LangGraph 流程编排
├── stages/                 # 功能模块（规划/萃取/IP/视频）
├── client/                 # React 前端
├── web_console/            # FastAPI 后端
│   ├── app.py              # 应用入口 + 生命周期管理
│   ├── routes/             # API 路由聚合（v1-only）
│   ├── services/           # 业务逻辑
│   ├── runtime/            # TaskRegistry 任务管理
│   └── middleware/         # 中间件
└── examples/               # 示例脚本
```

如果你更关注实现入口，通常从这些文件开始读：

- `pipeline/novel_pipeline.py`
- `agents/creation_agents.py`
- `web_console/app.py`
- `web_console/routes/v1/`
- `core/state.py`

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 📄 许可证

### 代码 (MIT)

详见 [LICENSE](LICENSE) 文件。

### 生成内容 (CC BY-NC-SA 4.0)

StoryForge 生成的内容（小说、角色、视觉资产）使用 **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International** 许可证。

- ✅ 个人使用和非商业分享
- ✅ 修改和衍生作品（必须保持相同许可证）
- ❌ 未经许可的商业使用
- ❌ 创建闭源衍生品

商业许可咨询请联系项目维护者。

---

<p align="center">
  Made with ❤️ by StoryForge Contributors
</p>
