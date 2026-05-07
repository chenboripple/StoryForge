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
    def __init__(
        self,
        llm_client=None,
        memory=None,
        error_handler=None,
        use_json_mode=False,
        message_bus=None
    ):
        super().__init__(
            persona=MyPersona(),
            llm_client=llm_client,
            memory=memory,
            error_handler=error_handler,
            use_json_mode=use_json_mode,
            message_bus=message_bus
        )

    def invoke(self, state):
        # 1. 从 state 读取上下文
        # 2. 调用 LLM (支持 JSON 结构化输出)
        # 3. 发布消息到 MessageBus
        # 4. 更新状态并返回
        return state
```

### 关键特性

#### 1. 结构化输出 (JSON Mode)

```python
agent = ReviewerAgent(use_json_mode=True)
result_dict = agent._call_llm(
    task="审稿",
    context="...",
    json_schema=REVIEW_JSON_PROMPT
)
# result_dict 已解析为 Python 字典
```

#### 2. 记忆集成 (Memory)

```python
from core.memory import StoryMemory

memory = StoryMemory()
agent = WriterAgent(memory=memory)

# 自动检测一致性问题
issues = memory.check_consistency(chapter, text)
# issues: [Inconsistency(severity="error", description="...")]
```

#### 3. MessageBus (Agent 间通讯)

```python
from core.agent import MessageBus, AgentMessage

bus = MessageBus()

# 发布消息
agent.publish_message(
    msg_type="suggestion",
    content="这里可以增加一个伏笔",
    target="writer",
    chapter=3,
    priority="high"
)

# 订阅消息
bus.subscribe(agent_name="writer", callback=handle_message)
bus.subscribe_by_type(msg_type="warning", callback=handle_warning)

# 查询历史
messages = bus.get_messages(agent="writer", chapter=3)
```

#### 4. 错误处理 + 重试

```python
# 自动重试（指数退避）
result = agent._call_llm_raw(prompt, json_mode=True)
# JSON 解析失败时自动尝试修复并重试
```

## LLM 调用

### 统一入口 `_call_llm_raw`

```python
def _call_llm_raw(
    self,
    prompt: str,
    json_mode: bool = False,
    task: str = "",
    temperature: Optional[float] = None,
    max_retries: int = 2
) -> Union[str, Dict]:
    # 1. 发送 llm_request 事件到 callbacks
    # 2. 重试执行 LLM 调用
    # 3. JSON 模式：解析结果，失败时尝试修复
    # 4. 发送 llm_response 事件到 callbacks
```

### JSON 提取与修复

```python
# 支持多种格式：
# - ```json {...} ```
# - ``` {...} ```
# - {...}
json_str = agent._extract_json(text)

# 自动修复常见问题：
# - 去掉 BOM
# - 去掉尾部逗号
# - 单引号转双引号
fixed = agent._fix_json(text)
```

## 内置 Agent 列表

### 1. WriterAgent（墨川）

**职责**：基于大纲创作章节

**实现特点**：
- 使用 `PromptAssembler` 动态组装 prompt
- 支持人味化规则
- 使用 `StoryMemory` 做一致性检查
- 输出为 `ChapterContent` 对象

**输入**：
- 小说信息（标题、类型）
- 大纲/卷纲
- 章节细纲（来自 `state.creation.chapter_outlines`）
- 角色设定
- 最近章节结尾
- Memory 上下文

**输出**：章节内容

**副作用**：
- 写入 `state.chapters[current_chapter]`
- 状态置为 `DRAFT`
- `review_round` 重置为 0
- 发布 `chapter_written` 事件

### 2. ReviewerAgent（青锋）

**职责**：结构化审稿 + AI 味评估

**评分维度**（8维）：
- 叙事结构（30%）
- 人物一致性（30%）
- 文学性（30%）
- 市场潜力（10%）
- 人物性格连续性
- 位置一致性
- 元叙事穿帮检测
- AI 味评估（low/medium/high）

**输出格式**：`ReviewResult` (JSON)

```python
@dataclass
class ReviewResult:
    total_score: int
    dimensions: List[DimensionScore]  # 各维度分数
    issues: List[ReviewIssue]        # 问题列表
    verdict: ReviewVerdict           # pass / revise / rewrite
    summary: str
    ai_flavor_score: int             # 1-10
    ai_flavor_level: str             # low / medium / high
```

**路由逻辑**：
- `verdict="pass"` → `approve` → proofreader
- `verdict="revise"` → `revise` → reviser
- `verdict="rewrite"` 或 `ai_flavor_level="high"` → `rewrite` → writer
- `review_round >= max_review_rounds` → `max_retries` → proofreader

**副作用**：
- 在 `state.structured_reviews` 追加结构化结果
- 兼容旧接口：在 `state.reviews` 追加 `ReviewRecord`
- `review_round += 1`
- 发布 `chapter_reviewed` 事件

### 3. ReviserAgent（墨川）

**职责**：根据审稿意见修改章节

**实现特点**：
- 复用 `MochuanPersona`（与 Writer 同一人设）
- 使用 `PromptAssembler` 动态组装修改 prompt
- 优先处理 S/A 级问题

**输入**：
- 当前章节完整内容
- 最新审稿意见
- 结构化问题列表（仅 S/A 级）
- 历史修改轮次

**输出**：完整的修改后章节正文

**副作用**：
- 更新 `state.chapters[current_chapter]`
- 状态置为 `REVISING`
- 发布 `chapter_revised` 事件

### 4. ProofreaderAgent（砚清）

**职责**：结构化校对 + 终审判定

**检查层级**（6层）：
1. 基础层：错别字、标点错误
2. 设定层：人物名字、设定一致性
3. 时间线层：时间逻辑
4. 人物层：性格连续性
5. 地理层：地理位置一致性
6. 伏笔层：伏笔回收检查

**输出格式**：`ProofreadResult` (JSON)

```python
@dataclass
class ProofreadResult:
    passed: bool
    issues: List[ProofreadIssue]
    summary: str
    verdict: str  # "可发布" / "可交付" / "需返修"
```

**终审判定**：
- "可发布"：直接进入萃取
- "可交付"：进入萃取
- "需返修"：返回修改

**副作用**：
- 在 `state.proofread_results` 追加结构化结果
- 兼容旧接口：在 `state.proofread_records` 追加 `ProofreadRecord`
- 更新章节状态
- 发布 `chapter_proofread` 事件

## 非 Agent 模块（stages/）

### OutlineGenerator

位置：`stages/outline/outline_generator.py`

职责：从卷纲生成章级细纲

输入：
- 小说标题
- 卷纲
- 当前章节号
- 角色设定
- 目标字数

输出：章级细纲（场景列表、字数分配、伏笔规划）

### KnowledgeExtractor

位置：`stages/extraction/knowledge_extractor.py`

职责：从章节提取知识

输入：章节内容

输出：
- 事件列表
- 新人物列表
- 新伏笔列表
- 更新到 `state.chapter_analyses`

### IPGenerator

位置：`stages/ip_generation/ip_generator.py`

职责：生成 IP 资产

输入：已完成章节 + 章节分析

输出：
- Story Bible
- 人物 IP 资产
- 保存到 `local_store/ip_assets/`

## 回调机制

支持添加回调钩子用于日志和监控：

```python
def on_event(event: str, data: dict):
    print(f"[{event}] {data}")

agent.add_callback(on_event)
```

回调事件类型：
- `llm_request`：LLM 调用前
- `llm_response`：LLM 响应后
- `chapter_written`：章节写作完成
- `chapter_reviewed`：审稿完成
- `chapter_revised`：修改完成
- `chapter_proofread`：校对完成

## PromptAssembler

位置：`core/prompt_assembler.py`

职责：动态组装 prompt，自动集成人味化规则

```python
from core.prompt_assembler import PromptAssembler

assembler = PromptAssembler()

# 写作用 prompt
prompt = assembler.assemble_writer_prompt(
    persona=persona,
    chapter_plan=plan,
    context=context,
    memory_context=memory_context,
    humanization=True  # 自动添加人味化规则
)

# 审稿用 prompt
prompt = assembler.assemble_reviewer_prompt(
    persona=persona,
    chapter_content=text,
    chapter_plan=plan,
    characters=characters,
    previous_chapter=prev_text
)

# 校对用 prompt
prompt = assembler.assemble_proofreader_prompt(
    persona=persona,
    chapter_content=text,
    characters=characters,
    world_setting=world_setting,
    scope="chapter"  # chapter / volume / book / project_docs
)
```

## 与 Pipeline 协作

每个 Agent 只承担「读 state → 调 LLM → 写 state」职责，不感知图结构。组合方式由 `pipeline/novel_pipeline.py` 通过 LangGraph 完成。详见 [Pipeline 流程详解](pipeline.md)。
