# NovelForge

基于 LangGraph + CrewAI 风格角色系统的多 Agent 小说创作与 IP 衍生平台。

## 架构

- **LangGraph**: 流程编排与状态管理
- **CrewAI 风格**: 角色人设与任务定义
- **三阶段 Pipeline**: 创作 → 萃取 → IP 生成

## 快速开始

```bash
pip install -r requirements.txt
python examples/demo_pipeline.py
```

## 项目结构

```
NovelForge/
├── core/           # 核心基类（状态、Agent、任务）
├── agents/         # Agent 角色定义（墨川/青锋/砚清等）
├── pipeline/       # LangGraph 流程定义
├── stages/         # 三阶段实现（创作/萃取/IP）
├── utils/          # 工具函数
├── tests/          # 测试
└── docs/           # 文档
```
