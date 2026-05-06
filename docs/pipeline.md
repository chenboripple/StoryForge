# Pipeline 流程详解

## 图结构

StoryForge 使用 LangGraph 构建 Pipeline，以 `NovelState` 为共享状态，节点之间通过条件边和循环边实现复杂的审稿-修改闭环。

```mermaid
graph TD
    START([开始]) --> writer[writer<br/>写作]
    writer --> reviewer[reviewer<br/>审稿]
    reviewer -->|条件路由| router{}
    router -->|approve<br/>≥85分| proofreader[proofreader<br/>校对]
    router -->|revise<br/>60-84分| reviser[reviser<br/>修改]
    router -->|rewrite<br/><60分| writer
    router -->|max_retries| proofreader
    reviser --> reviewer
    proofreader -->|条件路由| prouter{}
    prouter -->|pass| knowledge_extractor[knowledge_extractor<br/>萃取]
    prouter -->|fail| reviser
    knowledge_extractor --> ip_designer[ip_designer<br/>IP生成]
    ip_designer --> END([结束])
```

## 节点列表

| 节点 | 对应 Agent | 职责 |
|------|-----------|------|
| `writer` | `WriterAgent` | 基于大纲创作章节 |
| `reviewer` | `ReviewerAgent` | 从叙事结构/人物/文学性三维度审稿并评分 |
| `reviser` | `ReviserAgent` | 根据最新审稿意见修改章节 |
| `proofreader` | `ProofreaderAgent` | 最终校对，检查错字、逻辑、一致性 |
| `knowledge_extractor` | 占位 | 萃取章节知识（阶段二，待实现） |
| `ip_designer` | 占位 | 生成 IP 资产（阶段三，待实现） |

## 路由逻辑

### 审稿路由（`_review_router`）

```python
score = latest_review.score
review_round = state.review_round
max_rounds = state.max_review_rounds  # 默认 3（来自配置）
```

| 条件 | 路由 | 说明 |
|------|------|------|
| `review_round >= max_rounds` | `max_retries` → `proofreader` | 超轮次强制放行，避免死循环 |
| `score >= 85` | `approve` → `proofreader` | 高分通过 |
| `60 <= score < 85` | `revise` → `reviser` | 需修改 |
| `score < 60` | `rewrite` → `writer` | 重写 |

### 校对路由（`_proofread_router`）

| 条件 | 路由 | 说明 |
|------|------|------|
| `status == APPROVED` | `pass` → `knowledge_extractor` | 校对通过 |
| `review_round >= max_rounds + 2` | `pass` → `knowledge_extractor` | 校对也超次，强制放行 |
| 其他 | `fail` → `reviser` | 返回修改 |

## 循环控制

审稿-修改循环通过 `review_round` 计数器控制：

1. `WriterAgent.invoke` 在每次写作时重置 `review_round = 0`
2. `ReviewerAgent.invoke` 在每次审稿时 `review_round += 1`
3. `ReviserAgent.invoke` 不修改轮次，修改后回到 `reviewer` 节点再次计数

最大轮次默认值来自配置 `pipeline.max_review_rounds`（默认 3），也可在 `NovelState.max_review_rounds` 中覆盖。

## 公共接口

### `NovelPipeline.__init__(llm_client)` — 构造 Pipeline

```python
from pipeline.novel_pipeline import NovelPipeline

pipeline = NovelPipeline(llm_client=my_llm)
```

### `create_pipeline(llm_client)` — 工厂函数（推荐）

```python
from pipeline.novel_pipeline import create_pipeline

pipeline = create_pipeline(llm_client=my_llm)
```

### `NovelPipeline.run(state)` — 单章创作

```python
from pipeline.novel_pipeline import create_pipeline

pipeline = create_pipeline(llm_client=my_llm)
result = pipeline.run(state)
```

- 入口节点固定为 `writer`
- 自动处理 LangGraph 返回 dict → `NovelState` 的转换（`from_dict` 安全过滤）
- 返回最终状态，包含完整的章节内容和审稿/校对记录

### `NovelPipeline.run_batch(state, chapters)` — 批量创作

```python
results = pipeline.run_batch(state, chapters=[1, 2, 3])
# results[1] → 第1章的 NovelState
# results[2] → 第2章的 NovelState
```

- 每章使用 `state.copy()` 深拷贝，**各章状态完全隔离**
- 不阻塞：每章独立运行，失败不影响其他章节

### `NovelPipeline.visualize()` — 图结构可视化

```python
print(pipeline.visualize())  # 输出 Mermaid 语法
```

## 与 Storage 集成

Pipeline 本身不依赖 Storage，可通过以下模式保存结果：

```python
from core.config import get_config
from core.llm_factory import create_llm_client
from pipeline.novel_pipeline import create_pipeline
from backend import storage

# 1. 加载配置与构造组件
config = get_config()
llm = create_llm_client(config.llm)
pipeline = create_pipeline(llm_client=llm)

# 2. 运行 Pipeline
result = pipeline.run(state)

# 3. 持久化到 Storage
storage.save_novel(result)
```

完整示例见 `examples/demo_pipeline.py`，支持 `--save` 选项一键保存：

```bash
python examples/demo_pipeline.py --save
```

## 回调监控

Pipeline 本身不直接提供回调，但每个 Agent 节点支持通过 `add_callback` 注册钩子：

```python
def on_event(event: str, data: dict):
    print(f"[{event}] {data}")

writer.add_callback(on_event)
reviewer.add_callback(on_event)
```

全部回调事件：
- `llm_request` / `llm_response` — LLM 调用前后
- `chapter_written` — 章节写作完成
- `chapter_reviewed` — 审稿完成
- `chapter_revised` — 修改完成
- `chapter_proofread` — 校对完成
