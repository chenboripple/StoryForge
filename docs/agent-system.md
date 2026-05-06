# Agent 系统设计

## 核心概念

### AgentPersona: 角色即提示词工程

每个 Agent 都有完整的人设，自动转化为系统提示词注入 LLM。

```python
from core.agent import AgentPersona

persona = AgentPersona(
    name="墨川",
    role="职业小说家",
    goal="基于大纲创作高质量小说章节",
    backstory="曾是理论物理学博士...",
    expertise=["科幻世界观构建", "人物心理刻画"],
    tone="冷峻理性",
    principles=["人物行为必须符合其性格和动机"],
    constraints=["严格遵循大纲设定"]
)

# 自动生成系统提示词
print(persona.system_prompt())
```

### BaseAgent: Agent 基类

所有具体 Agent 继承 `BaseAgent`，必须实现 `invoke` 方法：

```python
class MyAgent(BaseAgent):
    def invoke(self, state: NovelState) -> NovelState:
        # 1. 从 state 读取上下文
        context = self._format_context(state)

        # 2. 调用 LLM
        result = self.call_llm(
            task="具体任务描述",
            context=context,
            extra_system_prompt="可选：临时追加系统提示词（线程安全）"
        )

        # 3. 更新 state 并返回
        state.chapters[1] = result
        return state
```

### call_llm API

```python
def call_llm(
    self,
    task: str,
    context: str = "",
    temperature: Optional[float] = None,
    extra_system_prompt: str = ""
) -> str
```

- `task`：具体任务描述
- `context`：任务上下文（从 State 生成）
- `temperature`：可选覆盖默认温度
- `extra_system_prompt`：**线程安全**的额外系统提示词（不修改 persona 对象）

## LLM 客户端注入

`BaseAgent` 在构造时接收一个 `llm_client: Callable`，调用签名为：

```python
def llm_client(prompt: str, temperature: Optional[float] = None) -> str
```

推荐通过 `core.llm_factory.create_llm_client(cfg)` 根据配置统一构造：

```python
from core.config import get_config
from core.llm_factory import create_llm_client
from agents.creation_agents import WriterAgent

config = get_config()
llm = create_llm_client(config.llm)

writer = WriterAgent(llm_client=llm)
```

工厂函数支持的 provider：

| provider | 适用场景 | 备注 |
|----------|----------|------|
| `mock` | 离线开发 / CI 测试 | 内置占位响应，关键词与示例数据匹配 |
| `openai` | OpenAI 及其兼容服务 | 通过 `base_url` 切换 DeepSeek、vLLM 等 |
| `anthropic` | Anthropic Claude | 需要在 `extra.max_tokens` 中指定上限 |

详见 [配置系统说明](config.md) 和 [API 参考](api-reference.md#llm-factory)。

## 内置 Agent 列表

### 1. WriterAgent（墨川）

**职责**：基于大纲创作章节

**上下文**：
- 小说信息（标题、类型）
- 大纲摘要（前500字）
- 角色设定（前5个主要角色）
- 已完成的最近章节的结尾（前两章）

**输出**：章节内容

**副作用**：写入 `state.chapters[current_chapter]`，状态置为 `DRAFT`，`review_round` 重置为 0。

### 2. ReviewerAgent（青锋）

**职责**：审稿并给出评分和修改建议

**评分标准**（≥85分通过）：
- 叙事结构：30%
- 人物一致性：30%
- 文学性：30%
- 市场潜力：10%

**输出格式**：
```
【总体评分】88分
【维度评分】
- 叙事结构：90分
- 人物一致性：85分
- 文学性：88分
- 市场潜力：90分
【致命问题】
- ...
【优化建议】
- ...
【亮点】
- ...
【是否通过】通过
```

**路由逻辑**：
- ≥85分 → approve → proofreader
- 60-84分 → revise → reviser
- <60分 → rewrite → writer
- ≥3轮 → max_retries → proofreader（强制进入）

**副作用**：在 `state.reviews[current_chapter]` 追加 `ReviewRecord`，`review_round += 1`。

### 3. ReviserAgent（墨川）

**职责**：根据审稿意见修改章节

**实现特点**：
- 复用 `MochuanPersona`（与 Writer 同一人设）
- 使用 `extra_system_prompt` 临时追加"修改任务"提示词
- **不修改 persona 对象**，线程安全
- 优先处理"致命问题"，其次"优化建议"

### 4. ProofreaderAgent（砚清）

**职责**：最终校对，检查：
- 错别字、标点错误
- 人物名字前后不一致
- 时间线/地理矛盾
- 逻辑漏洞
- 格式规范

**数据分离**：
- 审稿记录存入 `state.reviews`
- 校对记录存入 `state.proofread_records`（独立字段）

## 回调机制

支持添加回调钩子用于日志和监控：

```python
agent.add_callback(lambda event, data: print(f"{event}: {data}"))
```

回调事件类型：
- `llm_request`
- `llm_response`
- `chapter_written`
- `chapter_reviewed`
- `chapter_revised`
- `chapter_proofread`

## 与 Pipeline 协作

每个 Agent 仅承担「读 state → 调 LLM → 写 state」职责，不感知图结构。组合方式由 `pipeline/novel_pipeline.py` 通过 LangGraph 完成。详见 [Pipeline 流程详解](pipeline.md)。
