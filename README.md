<p align="center">
  <h1 align="center">StoryForge</h1>
  <p align="center">
    用 AI 创作、打磨、衍生你的小说世界
    <br />
    <a href="#-快速开始"><strong>快速开始 »</strong></a>
    <br />
    <br />
    <a href="#-核心特性">核心特性</a>
    ·
    <a href="#-使用场景">使用场景</a>
    ·
    <a href="#-文档">文档</a>
  </p>
</p>

---

## ✨ 为什么选择 StoryForge？

StoryForge 是一个多 Agent 小说创作平台，让 AI 像真实的创作团队一样工作：

- 🎭 **四个专业角色** - 作家、编辑、修改、校对各司其职
- 🔄 **审稿-修改闭环** - AI 自动审稿、给出修改意见、反复打磨
- 🧠 **记忆与一致性** - 自动追踪人物、时间线、世界观，防止穿帮
- 🎨 **IP 衍生能力** - 自动提取设定、生成人物卡、故事 bible
- 🎬 **视频剧本生成** - 从小说到镜头剧本的一键转换（实验性）
- 🖥️ **直观的 Web 界面** - 查看创作进度、管理小说、导入已有作品

---

## 🚀 快速开始

### 三分钟上手

```bash
# 1. 克隆项目
git clone https://github.com/chenboripple/StoryForge.git
cd StoryForge

# 2. 安装依赖
pip install -r requirements.txt

# 3. 运行演示（默认使用 Mock LLM，无需配置）
python examples/debug_pipeline.py
```

### 配置真实 LLM

编辑 `~/.storyforge/storyforge.yaml`：

```yaml
llm:
    provider: openai  # 或 anthropic
    model: gpt-4o-mini
    api_key: "your-api-key-here"
```

### 启动 Web 界面

```bash
# 安装前端依赖并构建
cd client
npm install
npm run build
cd ..

# 启动后端
uvicorn web_console.app:app --reload --port 8787
```

然后访问 `http://127.0.0.1:8787`

---

## 🎯 核心特性

### 🎭 多 Agent 协作

四个专业角色组成的创作团队，通过 MessageBus 互相协作：

| 角色 | 人设 | 职责 |
|------|------|------|
| **墨川** | 冷峻理性，物理背景 | 小说创作 |
| **青锋** | 犀利直接，20年经验 | 结构化审稿 |
| **墨川** (Reviser) | - | 根据意见修改 |
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
- 🌍 世界设定演进
- ⚠️ 一致性问题预警

### 📚 知识萃取与 IP 生成

- 自动从章节提取知识
- 生成故事 bible（设定集）
- 生成人物 IP 资产（人设、台词、画像提示词）

---

## 💡 使用场景

### 1. 从零开始创作

```python
from pipeline.novel_pipeline import create_pipeline

# 配置 Pipeline
pipeline = create_pipeline(llm_client=my_llm)

# 创作你的第一部小说
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

已有初稿？让 StoryForge 帮你审稿、修改、校对。

---

## 📖 文档

- 🏗️ [架构设计](docs/architecture.md) - 了解系统架构
- 🔄 [Pipeline 详解](docs/pipeline.md) - 深入理解创作流程
- 🤖 [多 Agent 指南](docs/MULTI_AGENT_GUIDE.md) - 玩转多 Agent 协作
- 📡 [API 参考](docs/api-reference.md) - 完整的 API 文档

---

## 🛠️ 项目结构

```
StoryForge/
├── core/                   # 核心模块
│   ├── models/             # 数据模型（按领域分组）
│   ├── config.py           # 配置管理
│   └── storage/            # 存储管理
├── agents/                 # Agent 角色定义
├── pipeline/               # LangGraph 流程编排
├── stages/                 # 功能模块（大纲/萃取/IP生成）
├── client/                 # React 前端
├── web_console/            # FastAPI 后端
│   ├── app.py              # 应用入口 + 生命周期管理
│   ├── routes/             # API 路由聚合（v1-only）
│   ├── services/           # 业务逻辑
│   ├── runtime/            # TaskRegistry 任务管理
│   └── middleware/         # 中间件
└── examples/               # 示例脚本
```

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
