# StoryForge

基于 LangGraph + CrewAI 风格角色系统的多 Agent 小说创作与 IP 衍生平台。

## 架构

- **LangGraph**: 流程编排与状态管理
- **CrewAI 风格**: 角色人设与任务定义
- **三阶段 Pipeline**: 创作 → 萃取 → IP 生成
- **结构化输出**: JSON Schema 确保 LLM 输出可解析
- **记忆系统**: 事件时间线 + 角色状态追踪
- **人味化规则**: 禁用 AI 常见句式，提升文本自然度

## 快速开始

```bash
pip install -r requirements.txt
python examples/debug_pipeline.py
```

## 配置

统一配置入口：`core/settings.py`。

默认读取用户配置文件：`~/.storyforge/config.json`。

优先级：**环境变量 > `~/.storyforge/config.json`**（无代码默认值，缺失即报错）。

配置文件示例：

```json
{
  "console": {
    "max_running_tasks": 2,
    "default_command": "python3 examples/debug_pipeline.py",
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

必填配置项（可在环境变量或配置文件中提供）：

| 环境变量 | 配置路径 |
|---|---|
| `STORYFORGE_MAX_RUNNING_TASKS` | `console.max_running_tasks` |
| `STORYFORGE_DEFAULT_COMMAND` | `console.default_command` |
| `STORYFORGE_TEMPLATE_FILE` | `console.template_file` |
| `STORYFORGE_DEBUG_DIR` | `debug.output_dir` |
| `STORYFORGE_DEFAULT_TARGET_WORD_COUNT` | `pipeline.default_target_word_count` |

## 操作页面（MVP）

启动命令：

```bash
uvicorn web_console.app:app --reload --port 8787
```

浏览器访问 `http://127.0.0.1:8787`。
支持启动任务、查看状态、查看日志、停止任务，以及模板保存、并发上限控制、日志下载。

## 项目结构

```
StoryForge/
├── core/              # 核心基类
│   ├── state.py       # NovelState 状态管理
│   ├── agent_v2.py    # BaseAgent 基类
│   ├── schema.py      # 结构化输出 Schema
│   ├── memory.py      # 记忆系统
│   ├── outline.py     # 大纲数据结构
│   ├── prompt_assembler.py  # 动态 Prompt 组装
│   ├── settings.py    # 统一配置入口
│   └── utils/         # 工具函数
├── agents/            # Agent 角色定义
│   └── creation_agents.py    # 墨川/青锋/砚清
├── pipeline/          # LangGraph 流程定义
│   └── novel_pipeline.py     # 完整 Pipeline
├── examples/          # 示例和调试脚本
│   └── debug_pipeline.py     # 调试脚本（推荐）
├── web_console/       # 操作页面（FastAPI）
├── stages/            # 三阶段实现（创作/萃取/IP）
├── tests/             # 测试
└── docs/              # 文档
```

## 核心特性

### 1. 大纲细化阶段
- 基于卷纲生成章级细纲
- 包含：场景列表、字数分配、伏笔规划

### 2. PromptAssembler 动态组装
- 根据上下文动态构建 prompt
- 融入人味化规则（禁用 AI 常见句式）
- 支持审稿/校对/写作三种模式

### 3. 结构化审稿（8 维度）
- 叙事结构、人物一致性、文学性、市场潜力
- AI 味评估（低/中/高）
- 位置一致性检查
- 元叙事穿帮检测

### 4. 结构化校对（6 层级）
- 基础层、设定层、时间线层、人物层、地理层、伏笔层
- 终审判定：可发布 / 可交付 / 需返修

### 5. 智能路由
- AI 味过高 → 自动重写
- 终审不通过 → 返修改
- 审稿通过 → 进入校对

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

## 角色系统

| 角色 | 职责 | 特点 |
|------|------|------|
| 墨川 | 小说家 | 冷峻理性，物理背景 |
| 青锋 | 文学编辑 | 犀利直接，20年经验 |
| 砚清 | 校对专家 | 严谨细致，处女座 |

## 依赖

```
langgraph>=0.0.50
langchain>=0.1.0
pydantic>=2.0
```

## License

MIT
