# StoryForge

基于 LangGraph + CrewAI 风格角色系统的多 Agent 小说创作与 IP 衍生平台。

## 架构

- **LangGraph**: 流程编排与状态管理
- **CrewAI 风格**: 角色人设与任务定义
- **三阶段 Pipeline**: 创作 → 萃取 → IP 生成
- **结构化输出**: JSON Schema 确保 LLM 输出可解析
- **记忆系统**: 事件时间线 + 角色状态追踪
- **人味化规则**: 禁用 AI 常见句式，提升文本自然度

## 版本演进

| 版本 | 核心改进 | 状态 |
|------|---------|------|
| V1 | 基础 Pipeline（写作→审稿→修改→校对） | ✅ 稳定 |
| V2 | 结构化输出 + 记忆系统 + 错误处理 | ✅ 稳定 |
| V3 | 大纲细化 + PromptAssembler + AI味评估 + 终审机制 | ✅ 稳定 |

## 快速开始

```bash
pip install -r requirements.txt

# V3 版本（推荐）
python examples/debug_pipeline_v3.py

# V2 版本
python examples/debug_pipeline_v2.py

# V1 版本
python examples/demo_pipeline.py
```

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
│   └── utils/         # 工具函数
├── agents/            # Agent 角色定义
│   ├── creation_agents.py      # V1 Agent
│   ├── creation_agents_v2.py   # V2 Agent（结构化输出）
│   └── creation_agents_v3.py   # V3 Agent（AI味评估）
├── pipeline/          # LangGraph 流程定义
│   ├── novel_pipeline.py       # V1 Pipeline
│   ├── novel_pipeline_v2.py    # V2 Pipeline
│   └── novel_pipeline_v3.py    # V3 Pipeline（大纲细化）
├── examples/          # 示例和调试脚本
│   ├── demo_pipeline.py        # V1 演示
│   ├── demo_pipeline_v2.py     # V2 演示
│   └── debug_pipeline_v3.py    # V3 调试（推荐）
├── stages/            # 三阶段实现（创作/萃取/IP）
├── tests/             # 测试
└── docs/              # 文档
```

## V3 核心特性

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

V3 调试脚本会自动保存：
- 每个 LLM 调用的完整 prompt
- 所有 prompt 调用历史（JSON）
- Pipeline 运行前后的状态快照

```bash
# 查看保存的 prompt
cat debug_output_v3/prompt_*.txt

# 查看状态变化
cat debug_output_v3/state_initial.json
cat debug_output_v3/state_final_*.json
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
