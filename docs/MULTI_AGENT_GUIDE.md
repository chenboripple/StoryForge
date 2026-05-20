# StoryForge Multi-Agent 系统使用指南

## 当前实现

- MessageBus 已默认可用，Agent 间消息会写入 `NovelState.agent_messages`。
- 路由建议会写入 `NovelState.routing_suggestions`，当前主要用于观测、调试和后续决策分析。

## 后续计划

1. 为 `routing_suggestions` 增加更明确的采用策略和可视化界面。
2. 将多 Agent 消息与章节审稿、校对、视觉任务串联得更完整。

## 概述

StoryForge 现在支持真正的 multi-agent 功能：

1. **MessageBus** - Agent 间消息总线
2. **Agent 自主路由** - Agent 可以建议 Pipeline 下一步动作

## 架构

```
NovelState
├── agent_messages: List[Dict]     # Agent 间消息日志
└── routing_suggestions: List[Dict] # Agent 路由建议

Pipeline
├── use_message_bus: bool = True    # 是否启用消息总线
└── use_agent_routing: bool = False # 是否启用自主路由（渐进式）
```

## 快速开始

### 基础使用（默认启用 MessageBus）

```python
from pipeline.novel_pipeline import create_pipeline

# MessageBus 默认已启用
pipeline = create_pipeline(
    llm_client=your_llm,
    use_message_bus=True,  # 默认 True
    use_agent_routing=False # 自主路由默认关闭（渐进式）
)

result = pipeline.run(state)

# 查看 Agent 间消息
for msg in result.agent_messages:
    print(f"[{msg['sender']}] {msg['msg_type']}: {msg['content']}")

# 查看 Agent 路由建议
for suggestion in result.routing_suggestions:
    print(f"[{suggestion['suggested_by']}] -> {suggestion['suggested_node']}")
```

### 启用 Agent 自主路由

```python
pipeline = create_pipeline(
    llm_client=your_llm,
    use_agent_routing=True # 预留开关，当前实现仍以内建路由为主
)
```

## Agent 间消息类型

| 类型 | 发送方 | 接收方 | 说明 |
|------|--------|--------|------|
| info | Writer | Reviewer | 章节写作完成通知 |
| suggestion | Reviewer | Writer | 审稿建议和反馈 |
| warning | Any | Any | 一致性问题等警告 |
| routing_suggestion | Any | Pipeline | 路由建议（优先处理） |

## 路由建议机制

Agent 自主路由的工作流程：

1. **Agent 发布建议** - Reviewer/Proofreader 完成任务后发布路由建议
2. **建议存入 state** - 路由建议保存在 `state.routing_suggestions` 中
3. **Pipeline 记录** - 当前实现会把建议写入 `state.routing_suggestions`，供调试与后续决策分析使用

```python
# Agent 代码示例
self.suggest_route(
    suggested_node="proofreader",  # 建议的下一节点
    reason="审稿通过，建议进入校对",
    confidence=0.9,  # 置信度 0.0 - 1.0
    chapter=state.current_chapter
)
```

## MessageBus 使用

### 在自定义 Agent 中使用 MessageBus

```python
from core.agent import BaseAgent, AgentMessage

class MyAgent(BaseAgent):
    def __init__(self, persona, llm_client, message_bus=None, state=None):
        super().__init__(
            persona=persona,
            llm_client=llm_client,
            message_bus=message_bus,
            state=state
        )

    def invoke(self, state):
        # 绑定 state 用于持久化
        self.state = state
        self._current_chapter = state.current_chapter

        # 发布消息
        self.publish_message(
            msg_type="info",
            content="我的任务完成了！",
            target="其他 Agent 名字",  # None = 广播
            chapter=state.current_chapter
        )

        # 建议路由
        self.suggest_route(
            suggested_node="next_node",
            reason="为什么建议这个路由",
            confidence=0.85
        )

        return state
```

### 从 state 读取其他 Agent 的消息

```python
# 在自定义 Agent 中读取消息
messages = self.get_messages_from_state(
    msg_type="suggestion",  # None = 所有类型
    chapter=state.current_chapter,
    limit=5
)
# messages: List[Dict]
```

## 当前使用建议

为了保持系统稳定性，当前建议这样使用多 Agent 功能：

1. 开启 MessageBus，观察 Agent 间消息是否能覆盖审稿、返修和视觉协作场景。
2. 保留路由建议记录，但仍以 Pipeline 内建路由作为正式执行依据。
3. 在验证建议质量稳定后，再考虑把部分建议接入真实决策链。

## 示例

运行 `examples/multi_agent_demo.py` 查看完整演示：

```bash
# 传统模式（只记录消息和建议）
python3 examples/multi_agent_demo.py

# 启用 Agent 自主路由
python3 examples/multi_agent_demo.py --agent-routing
```

## 回退策略

当前代码路径中，Pipeline 仍使用原有路由逻辑；路由建议主要用于观测与调试：

1. Reviewer 路由：基于 `verdict` 和 `ai_flavor_level`
2. Proofreader 路由：基于终审结果和审稿轮次

## 数据持久化

所有 Agent 间消息和路由建议都会保存在 NovelState 中：

```python
# 通过 StorageManager 持久化（按模型分文件）
from core.storage import get_storage_manager
sm = get_storage_manager()

# 加载后消息和路由建议各自从对应文件恢复
# 具体方法见 core/storage/manager.py
```

## API 参考

### NovelState 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `agent_messages` | List[Dict] | Agent 间消息历史 |
| `routing_suggestions` | List[Dict] | Agent 路由建议 |

### NovelState 新增方法

| 方法 | 说明 |
|------|------|
| `get_agent_messages(msg_type, chapter, target, limit)` | 获取 Agent 消息 |
| `get_routing_suggestions(chapter)` | 获取路由建议 |
| `add_agent_message(sender, msg_type, content, target, chapter, priority)` | 添加消息 |
| `add_routing_suggestion(suggested_by, suggested_node, reason, confidence, chapter)` | 添加路由建议 |

### BaseAgent 新增方法

| 方法 | 说明 |
|------|------|
| `publish_message(msg_type, content, target, chapter, priority)` | 发布消息 |
| `suggest_route(suggested_node, reason, confidence, chapter)` | 建议路由 |
| `get_messages_from_state(msg_type, chapter, limit)` | 从 state 读取消息 |
| `_get_agent_messages_for_prompt(state, msg_type, limit)` | 获取消息用于 prompt 上下文 |

## 常见问题

### Q: 如何查看 Agent 间发送了什么消息？

A: `result.agent_messages` 包含所有消息历史。

### Q: Agent 建议的路由优先级如何确定？

A: 当前实现仅记录建议，还没有在 Pipeline 中做统一排序和采用。

### Q: 是否可以禁用 MessageBus 但保留路由建议？

A: 可以。`publish_message()` 会优先走 MessageBus，同时也会把消息/建议持久化到 `NovelState`。

### Q: 路由建议的置信度如何计算？

A: 目前是在 Agent 内部硬编码的（Reviewer 用 0.9 等），未来可以结合 LLM 输出的置信度。
