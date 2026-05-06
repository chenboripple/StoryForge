# API 参考

## Core

### `AgentPersona`

角色人设定义，所有字段自动注入 LLM 系统提示词。

```python
@dataclass
class AgentPersona:
    name: str                # 名字（如 "墨川"）
    role: str                # 角色（如 "职业小说家"）
    goal: str                # 核心目标
    backstory: str = ""      # 背景故事（影响语气与知识倾向）
    expertise: List[str]     # 专业领域（影响任务分配）
    tone: str                # 语气风格（影响输出调性）
    principles: List[str]    # 工作原则（影响决策逻辑）
    constraints: List[str]   # 限制条件（影响输出边界）
```

**方法**

- `system_prompt() -> str`
  - 生成完整的系统提示词，自动组合所有字段

---

### `BaseAgent`

所有具体 Agent 的抽象基类。

```python
class BaseAgent(ABC):
    def __init__(self, persona: AgentPersona, llm_client: Optional[Callable] = None)
```

**方法**

- `invoke(state: NovelState) -> NovelState` *(抽象)*
  - 执行 Agent 任务，必须子类实现

- `call_llm(task, context="", temperature=None, extra_system_prompt="") -> str`
  - 调用 LLM，自动注入 `persona.system_prompt()`
  - `extra_system_prompt`：追加额外系统提示，**不修改 persona 对象**（线程安全）

- `add_callback(callback: Callable[[str, dict], None])`
  - 注册回调钩子，事件类型见 [pipeline.md](pipeline.md)

---

### `Task`

CrewAI 风格的任务定义，将"做什么"与"怎么做"分离。

```python
class Task:
    def __init__(
        self,
        description: str,           # 任务描述
        expected_output: str,       # 期望输出
        agent: Optional[BaseAgent] = None,
        context_tasks: Optional[List[str]] = None
    )
```

**方法**

- `execute(state, extra_system_prompt="") -> str`
  - 调用关联 Agent 的 `call_llm` 执行任务

---

### `NovelState`

贯穿整个 Pipeline 的全局状态对象。

```python
@dataclass
class NovelState:
    # 元数据
    novel_id: str = ""
    novel_title: str = ""
    genre: str = ""
    target_word_count: int = 3000
    current_stage: PipelineStage = PipelineStage.CREATION

    # 创作层
    concept: str = ""
    outline: str = ""
    volume_outline: Dict[int, str]
    characters: List[CharacterInfo]
    chapters: Dict[int, str]              # 章节号 → 内容
    chapter_status: Dict[int, ChapterStatus]
    current_chapter: int = 1
    review_round: int = 0
    max_review_rounds: int = 3
    reviews: Dict[int, List[ReviewRecord]]          # 章节 → 审稿记录列表
    proofread_records: Dict[int, List[ProofreadRecord]]  # 章节 → 校对记录列表

    # 萃取层（预留）
    knowledge_base: Dict[str, Any]

    # IP 生成层（预留）
    character_ips: Dict[str, Dict]
    visual_assets: Dict[str, List[Dict]]

    # 控制字段
    error_message: str = ""
    human_feedback: Optional[str] = None
    should_pause: bool = False
```

**方法**

- `get_current_chapter_status() -> ChapterStatus`
- `get_latest_review() -> Optional[ReviewRecord]` — 当前章节最新审稿记录
- `can_continue_review() -> bool` — 是否未超最大轮次
- `to_context_string() -> str` — 生成供 Agent 使用的上下文字符串
- `copy() -> NovelState` — 深拷贝，用于批量创作隔离状态
- `to_dict() -> dict` — **序列化为 JSON 友好的字典**（用于 storage 与 API 输出）
- `to_index_entry() -> dict` — **生成轻量索引条目**（用于清单页）
- `from_dict(data: dict) -> NovelState` *(classmethod)* — 安全构造，自动反序列化嵌套对象（角色、状态枚举、审稿记录等）

---

### 辅助类

#### `ChapterStatus`

```python
class ChapterStatus(Enum):
    PENDING = "pending"           # 待写作
    DRAFT = "draft"               # 初稿完成
    IN_REVIEW = "in_review"       # 审稿中
    REVISING = "revising"         # 修改中
    PROOFREADING = "proofreading" # 校对中
    APPROVED = "approved"         # 已通过
    REJECTED = "rejected"         # 被驳回
```

#### `PipelineStage`

```python
class PipelineStage(Enum):
    CREATION = "creation"         # 创作层
    EXTRACTION = "extraction"     # 萃取层
    IP_GENERATION = "ip_generation"  # IP 生成层
```

#### `ReviewRecord`

```python
@dataclass
class ReviewRecord:
    round: int                  # 审稿轮次
    reviewer: str               # 审稿人
    score: int                  # 0-100
    comments: str               # 完整审稿意见
    passed: bool                # 是否通过
    timestamp: Optional[str]
```

#### `ProofreadRecord`

```python
@dataclass
class ProofreadRecord:
    round: int                  # 校对轮次
    proofreader: str            # 校对人
    comments: str               # 校对意见
    passed: bool                # 是否通过
    timestamp: Optional[str]
```

#### `CharacterInfo`

```python
@dataclass
class CharacterInfo:
    name: str
    age: Optional[int] = None
    appearance: str = ""
    personality: str = ""
    background: str = ""
    goals: List[str]
    relationships: Dict[str, str]
    classic_lines: List[str]
```

---

## Config（配置系统）

### `get_config()` / `load_config()`

加载并缓存全局配置。详细字段说明见 [config.md](config.md)。

```python
from core.config import get_config, load_config, reset_config

# 加载（带缓存）
config = get_config()

# 强制重新加载
config = get_config(reload=True)

# 显式指定路径
config = load_config("/path/to/custom.yaml")

# 清空缓存
reset_config()
```

### `StoryForgeConfig`

```python
@dataclass
class StoryForgeConfig:
    llm: LLMConfig
    storage: StorageConfig
    server: ServerConfig
    pipeline: PipelineConfig
    config_path: Optional[str]    # 加载来源（None 表示使用默认值）

    @property
    def data_dir_abs(self) -> str  # data_dir 的绝对路径
```

### 子配置

```python
@dataclass
class LLMConfig:
    provider: str = "mock"       # mock | openai | anthropic
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    timeout: int = 60
    extra: Dict[str, Any]

@dataclass
class StorageConfig:
    data_dir: str = "./data"

@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 5089
    cors_origins: str = "*"

@dataclass
class PipelineConfig:
    max_review_rounds: int = 3
    default_target_word_count: int = 3000
```

---

## LLM Factory

### `create_llm_client(cfg: Optional[LLMConfig] = None) -> Callable`

根据配置创建 LLM 客户端。

```python
from core.config import get_config
from core.llm_factory import create_llm_client

config = get_config()
llm = create_llm_client(config.llm)

# 调用
result = llm("请创作一段...", temperature=0.8)
```

**返回值签名**

```python
def llm(prompt: str, temperature: Optional[float] = None) -> str
```

**支持的 provider**

| provider | 说明 | 依赖 |
|----------|------|------|
| `mock` | 内置占位响应 | 无 |
| `openai` | OpenAI / OpenAI 兼容协议 | `pip install openai` |
| `anthropic` | Anthropic Claude | `pip install anthropic` |

---

## Agents

### `WriterAgent`

```python
class WriterAgent(BaseAgent):
    def __init__(self, llm_client=None)
    def invoke(self, state: NovelState) -> NovelState
```

- 使用 `MochuanPersona`（墨川）
- 上下文包含：小说信息、大纲前500字、前5个角色、最近两章结尾200字
- 输出：完整章节正文（不含标题和章节号）
- 副作用：`chapters[current_chapter]` 写入内容，`chapter_status` → `DRAFT`，`review_round` 重置为 0

### `ReviewerAgent`

```python
class ReviewerAgent(BaseAgent):
    def __init__(self, llm_client=None)
    def invoke(self, state: NovelState) -> NovelState
```

- 使用 `QingfengPersona`（青锋）
- 上下文包含：小说信息、角色设定、本章前1500字、历史审稿记录
- 输出解析：提取总体评分（多重正则匹配 + 兜底），判断是否通过（≥85分且显式标注"通过"）
- 副作用：`reviews[current_chapter]` 追加 `ReviewRecord`，`chapter_status` 更新，`review_round += 1`

### `ReviserAgent`

```python
class ReviserAgent(BaseAgent):
    def __init__(self, llm_client=None)
    def invoke(self, state: NovelState) -> NovelState
```

- 使用 `MochuanPersona`，通过 `extra_system_prompt` 临时追加"当前任务是根据编辑意见修改"提示
- 上下文包含：当前章节完整内容、最新审稿意见、已修改轮次
- 输出：完整的修改后章节正文
- 副作用：`chapters[current_chapter]` 更新内容，`chapter_status` → `REVISING`

### `ProofreaderAgent`

```python
class ProofreaderAgent(BaseAgent):
    def __init__(self, llm_client=None)
    def invoke(self, state: NovelState) -> NovelState
```

- 使用 `YanqingPersona`（砚清）
- 上下文包含：章节完整内容、角色名单（用于一致性检查）
- 输出解析：检查 `【总体评价】通过` 或精确匹配 `"通过"`
- 副作用：`proofread_records[current_chapter]` 追加 `ProofreadRecord`（与 `reviews` 字段分离），`chapter_status` 更新

---

## Pipeline

### `NovelPipeline`

```python
class NovelPipeline:
    def __init__(self, llm_client: Callable = None)
    def run(self, initial_state: NovelState) -> NovelState
    def run_batch(self, state: NovelState, chapters: list) -> Dict[int, NovelState]
    def visualize(self) -> str
```

### `create_pipeline`

```python
def create_pipeline(llm_client: Callable = None) -> NovelPipeline
```

工厂函数，创建预配置好的 Pipeline 实例。

**LLM Client 签名**

```python
def llm_client(prompt: str, temperature: Optional[float] = None) -> str:
    """
    prompt: 完整 prompt（已包含 system_prompt + context + task）
    temperature: 可选温度覆盖
    return: LLM 生成的文本
    """
```

---

## Storage（存储层）

### `backend.storage`

JSON 文件存储层，存储位置由 `config.storage.data_dir` 决定。

**目录结构**

```
<data_dir>/
├── index.json         # 小说清单索引
└── novels/
    └── <novel_id>.json  # 单个小说完整状态
```

### 函数

```python
from backend import storage

# 保存
storage.save_novel(state: NovelState) -> None

# 加载
storage.load_novel(novel_id: str) -> Optional[NovelState]

# 列出（来自 index.json）
storage.list_novels() -> List[dict]

# 仅更新索引
storage.update_novel_index(state: NovelState) -> None

# 删除
storage.delete_novel(novel_id: str) -> bool

# 重建索引（扫描 novels/ 目录）
storage.rebuild_index() -> int
```

---

## HTTP API（Web 后端）

详见 [Web API 端点](#web-api-端点)。

### Web API 端点

后端通过 Flask 提供，由 `backend/app.py` 定义。

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/novels` | GET | 小说清单 |
| `/api/novels/<novel_id>` | GET | 单个小说完整状态 |
| `/api/novels/<novel_id>/chapters` | GET | 章节列表 |
| `/api/novels/<novel_id>/chapters/<chapter_num>` | GET | 章节内容 + 审稿/校对 |

#### `GET /api/health`

返回服务健康状态及当前配置摘要。

**响应**

```json
{
  "status": "ok",
  "config_path": "/path/to/.storyforge/storyforge.yaml",
  "data_dir": "/path/to/data"
}
```

#### `GET /api/novels`

返回小说清单（轻量索引）。

**响应**

```json
[
  {
    "novel_id": "demo_001",
    "novel_title": "熵塔",
    "genre": "科幻末日",
    "concept": "末日后的世界...",
    "current_stage": "creation",
    "current_chapter": 1,
    "total_chapters": 1,
    "approved_chapters": 1,
    "character_count": 2
  }
]
```

#### `GET /api/novels/<novel_id>`

返回单个小说的完整状态（即 `NovelState.to_dict()` 输出）。

**响应**：完整 `NovelState` JSON

**错误**

| 状态码 | 含义 |
|--------|------|
| 404 | 小说不存在 |

#### `GET /api/novels/<novel_id>/chapters`

返回章节列表（带状态、字数和最新审稿分数）。

**响应**

```json
{
  "novel_id": "demo_001",
  "current_chapter": 1,
  "chapters": [
    {
      "chapter_num": 1,
      "status": "approved",
      "word_count": 601,
      "preview": "林晚站在观测塔的废墟上...",
      "review_rounds": 2,
      "latest_score": 88,
      "latest_passed": true
    }
  ]
}
```

#### `GET /api/novels/<novel_id>/chapters/<chapter_num>`

返回章节正文 + 完整审稿/校对记录。

**响应**

```json
{
  "novel_id": "demo_001",
  "chapter_num": 1,
  "status": "approved",
  "content": "（章节正文）",
  "word_count": 601,
  "reviews": [
    {
      "round": 1,
      "reviewer": "青锋",
      "score": 78,
      "comments": "...",
      "passed": false,
      "timestamp": "2026-05-05T10:12:00"
    }
  ],
  "proofread_records": [
    {
      "round": 1,
      "proofreader": "砚清",
      "comments": "...",
      "passed": true,
      "timestamp": "2026-05-05T12:05:00"
    }
  ]
}
```

**错误**

| 状态码 | 含义 |
|--------|------|
| 404 | 小说或章节不存在 |
