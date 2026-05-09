# API 参考

## Core (core/)

### `core/agent.py`

#### AgentMessage

```python
@dataclass
class AgentMessage:
    sender: str
    msg_type: str          # "issue" / "suggestion" / "info" / "warning"
    content: str
    target: Optional[str]  # None 表示广播
    chapter: Optional[int]
    timestamp: str
    priority: str          # "low" / "normal" / "high" / "urgent"
```

#### MessageBus

```python
class MessageBus:
    def publish(self, message: AgentMessage)
    def subscribe(self, agent_name: Optional[str], callback: Callable)
    def subscribe_by_type(self, msg_type: str, callback: Callable)
    def get_messages(
        self,
        agent: Optional[str] = None,
        msg_type: Optional[str] = None,
        chapter: Optional[int] = None,
        since: Optional[str] = None
    ) -> List[AgentMessage]
    def get_unread_for_agent(self, agent_name: str) -> List[AgentMessage]
    def to_dict(self) -> List[Dict]
    @classmethod
    def from_dict(cls, data: List[Dict]) -> MessageBus
```

#### AgentPersona

```python
@dataclass
class AgentPersona:
    name: str
    role: str
    goal: str
    backstory: str = ""
    expertise: List[str] = field(default_factory=list)
    tone: str = "专业、客观"
    principles: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)

    def system_prompt(self) -> str
```

#### BaseAgent

```python
class BaseAgent(ABC):
    def __init__(
        self,
        persona: AgentPersona,
        llm_client: Optional[Callable] = None,
        memory: Optional[StoryMemory] = None,
        error_handler: Optional[ErrorHandler] = None,
        use_json_mode: bool = False,
        message_bus: Optional[MessageBus] = None
    ):
        # ...

    @abstractmethod
    def invoke(self, state: Any) -> Any

    def _call_llm(
        self,
        task: str,
        context: str = "",
        temperature: Optional[float] = None,
        json_schema: Optional[str] = None,
        max_retries: int = 2
    ) -> Union[str, Dict]

    def _call_llm_raw(
        self,
        prompt: str,
        json_mode: bool = False,
        task: str = "",
        temperature: Optional[float] = None,
        max_retries: int = 2
    ) -> Union[str, Dict]

    def publish_message(
        self,
        msg_type: str,
        content: str,
        target: Optional[str] = None,
        chapter: Optional[int] = None,
        priority: str = "normal"
    )

    def get_messages_from_bus(
        self,
        msg_type: Optional[str] = None,
        chapter: Optional[int] = None
    ) -> List[AgentMessage]

    def add_callback(self, callback: Callable)
    def _notify(self, event: str, data: dict)
```

### `core/state.py`

#### ChapterStatus (Enum)

```python
class ChapterStatus(Enum):
    PENDING = "pending"
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    REVISING = "revising"
    PROOFREADING = "proofreading"
    APPROVED = "approved"
    REJECTED = "rejected"
```

#### PipelineStage (Enum)

```python
class PipelineStage(Enum):
    CREATION = "creation"
    EXTRACTION = "extraction"
    IP_GENERATION = "ip_generation"
```

#### ReviewRecord

```python
@dataclass
class ReviewRecord:
    round: int
    reviewer: str
    score: int
    comments: str
    passed: bool
    timestamp: str = ""
```

#### ProofreadRecord

```python
@dataclass
class ProofreadRecord:
    round: int
    proofreader: str
    comments: str
    passed: bool
    timestamp: str = ""
```

#### CharacterInfo

```python
@dataclass
class CharacterInfo:
    name: str
    age: Optional[int] = None
    appearance: str = ""
    personality: str = ""
    background: str = ""
    goals: List[str] = field(default_factory=list)
    relationships: Dict[str, str] = field(default_factory=dict)
    classic_lines: List[str] = field(default_factory=list)
```

#### NovelState

```python
@dataclass
class NovelState:
    # 元数据
    novel_id: str = ""
    novel_title: str = ""
    genre: str = ""
    target_word_count: int = DEFAULT_SETTINGS.pipeline.default_target_word_count
    current_stage: PipelineStage = PipelineStage.CREATION

    # 创作层
    concept: str = ""
    outline: str = ""
    volume_outline: Dict[int, str] = field(default_factory=dict)
    characters: List[CharacterInfo] = field(default_factory=list)
    chapters: Dict[int, Any] = field(default_factory=dict)
    chapter_status: Dict[int, ChapterStatus] = field(default_factory=dict)
    current_chapter: int = 1
    review_round: int = 0
    max_review_rounds: int = 3
    reviews: Dict[int, List[Any]] = field(default_factory=dict)
    structured_reviews: Dict[int, List[Any]] = field(default_factory=dict)
    proofread_results: Dict[int, List[Any]] = field(default_factory=dict)
    proofread_records: Dict[int, List[Any]] = field(default_factory=dict)
    proofread_scope: str = "chapter"
    proofread_context: Dict[str, Any] = field(default_factory=dict)

    # 萃取层
    knowledge_base: Dict[str, Any] = field(default_factory=dict)
    chapter_analyses: Dict[int, Any] = field(default_factory=dict)

    # IP 层
    character_ips: Dict[str, Dict] = field(default_factory=dict)
    visual_assets: Dict[str, List[Dict]] = field(default_factory=dict)
    story_bible: Optional[Any] = None

    # 兼容容器
    creation: Dict[str, Any] = field(default_factory=dict)

    # 控制字段
    error_message: str = ""
    human_feedback: Optional[str] = None
    should_pause: bool = False

    def get_current_chapter_status(self) -> ChapterStatus
    def get_latest_review(self) -> Optional[Any]
    def can_continue_review(self) -> bool
    def to_context_string(self) -> str
    def copy(self) -> NovelState
    def to_dict(self) -> dict
    def to_index_entry(self) -> dict
    @classmethod
    def from_dict(cls, data: dict) -> NovelState
```

### `core/schema.py`

#### ReviewVerdict (Enum)

```python
class ReviewVerdict(Enum):
    PASS = "pass"
    REVISE = "revise"
    REWRITE = "rewrite"
```

#### DimensionScore

```python
@dataclass
class DimensionScore:
    name: str
    score: int
    comment: str
```

#### ReviewIssue

```python
@dataclass
class ReviewIssue:
    severity: str          # "S" / "A" / "B" / "C"
    location: str
    description: str
    suggestion: str
```

#### ReviewResult

```python
@dataclass
class ReviewResult:
    total_score: int
    dimensions: List[DimensionScore]
    issues: List[ReviewIssue]
    verdict: ReviewVerdict
    summary: str
    ai_flavor_score: int = 5
    ai_flavor_level: str = "medium"
```

#### ProofreadIssue

```python
@dataclass
class ProofreadIssue:
    level: str             # "error" / "warning" / "suggestion"
    category: str          # "typo" / "consistency" / "timeline" / ...
    location: str
    description: str
    fix: str = ""
```

#### ProofreadResult

```python
@dataclass
class ProofreadResult:
    passed: bool
    issues: List[ProofreadIssue]
    summary: str
    verdict: str = "需返修"  # "可发布" / "可交付" / "需返修"
```

#### ChapterContent

```python
@dataclass
class ChapterContent:
    text: str
    version: int = 1
    word_count: int = 0
    generated_at: str = ""
    modified_at: str = ""
```

#### JSON Schema 提示词

```python
REVIEW_JSON_PROMPT     # ReviewResult 的 JSON Schema
PROOFREAD_JSON_PROMPT  # ProofreadResult 的 JSON Schema
```

### `core/memory.py`

#### StoryEvent

```python
@dataclass
class StoryEvent:
    chapter: int
    description: str
    characters: List[str]
    timestamp: str = ""
```

#### CharacterArc

```python
@dataclass
class CharacterArc:
    name: str
    current_state: str
    changes: List[str]
```

#### WorldState

```python
@dataclass
class WorldState:
    location: str
    time: str
    rules: Dict[str, str]
```

#### Inconsistency

```python
@dataclass
class Inconsistency:
    severity: str          # "error" / "warning"
    description: str
    location: str = ""
```

#### StoryMemory

```python
class StoryMemory:
    def __init__(self)
    def initialize_from_outline(
        self,
        characters: List[CharacterInfo],
        world_setting: Optional[str] = None
    )
    def add_event(self, event: StoryEvent)
    def update_character(self, arc: CharacterArc)
    def update_world(self, state: WorldState)
    def check_consistency(self, chapter: int, text: str) -> List[Inconsistency]
    def build_context_for_chapter(self, chapter: int) -> str
```

### `core/prompt_assembler.py`

#### PromptAssembler

```python
class PromptAssembler:
    def assemble_writer_prompt(
        self,
        persona: AgentPersona,
        chapter_plan: Optional[Any],
        context: str,
        memory_context: str = "",
        humanization: bool = True
    ) -> str

    def assemble_reviewer_prompt(
        self,
        persona: AgentPersona,
        chapter_content: str,
        chapter_plan: Optional[Any],
        characters: List[CharacterInfo],
        previous_chapter: str = ""
    ) -> str

    def assemble_proofreader_prompt(
        self,
        persona: AgentPersona,
        chapter_content: str,
        characters: List[CharacterInfo],
        world_setting: Optional[str] = None,
        scope: str = "chapter",
        project_docs: Optional[Dict[str, Any]] = None
    ) -> str
```

### `core/config.py` (YAML 配置 - backend 用)

```python
@dataclass
class LLMConfig:
    provider: str = "mock"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    timeout: int = 60
    extra: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StorageConfig:
    data_dir: str = "~/.storyforge/data"

@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8787
    cors_origins: str = "*"

@dataclass
class PipelineConfig:
    max_review_rounds: int = 3
    default_target_word_count: int = 3000

@dataclass
class StoryForgeConfig:
    llm: LLMConfig
    storage: StorageConfig
    server: ServerConfig
    pipeline: PipelineConfig
    config_path: Optional[str] = None

    @property
    def data_dir_abs(self) -> str

# 加载函数
def load_config(path: Optional[str] = None) -> StoryForgeConfig
def get_config(reload: bool = False) -> StoryForgeConfig
def reset_config() -> None
```

### `core/config.py`（统一 YAML 配置）

配置文件固定位置：`~/.storyforge/storyforge.yaml`

```python
@dataclass
class ConsoleConfig:
    max_running_tasks: int = 3
    default_command: str = "python examples/demo_pipeline.py"
    template_file: str = "~/.storyforge/templates.json"

@dataclass
class DebugConfig:
    output_dir: str = "debug_output"

@dataclass
class StoryForgeConfig:
    llm: LLMConfig
    storage: StorageConfig
    server: ServerConfig
    pipeline: PipelineConfig
    console: ConsoleConfig
    debug: DebugConfig

def load_config(path: Optional[str] = None) -> StoryForgeConfig
def get_config(reload: bool = False) -> StoryForgeConfig
def reset_config() -> None
```

## Agents (agents/)

### `agents/creation_agents.py`

```python
class WriterAgent(BaseAgent):
    def __init__(
        self,
        llm_client=None,
        memory: StoryMemory = None,
        error_handler=None,
        prompt_assembler: PromptAssembler = None
    )
    def invoke(self, state) -> NovelState

class ReviewerAgent(BaseAgent):
    def __init__(
        self,
        llm_client=None,
        memory: StoryMemory = None,
        error_handler=None,
        prompt_assembler: PromptAssembler = None
    )
    def invoke(self, state) -> NovelState

class ReviserAgent(BaseAgent):
    def __init__(
        self,
        llm_client=None,
        memory: StoryMemory = None,
        error_handler=None,
        prompt_assembler: PromptAssembler = None
    )
    def invoke(self, state) -> NovelState

class ProofreaderAgent(BaseAgent):
    def __init__(
        self,
        llm_client=None,
        memory: StoryMemory = None,
        error_handler=None,
        prompt_assembler: PromptAssembler = None
    )
    def invoke(self, state) -> NovelState

# 预定义人设
MochuanPersona()     # 墨川 - 作家
QingfengPersona()   # 青锋 - 编辑
YanqingPersona()    # 砚清 - 校对
```

## Pipeline (pipeline/)

### `pipeline/novel_pipeline.py`

```python
class NovelPipeline:
    def __init__(
        self,
        llm_client: Callable = None,
        use_memory: bool = True,
        use_outline_refinement: bool = True,
        use_extraction: bool = True,
        use_ip_generation: bool = True,
        checkpoint_dir: Optional[str] = None,
        ip_output_dir: str = "./ip_assets"
    )
    def run(self, initial_state: NovelState) -> NovelState
    def run_batch(self, state: NovelState, chapters: list) -> Dict[int, NovelState]
    def resume(self, novel_id: str, chapter: int, from_node: Optional[str] = None) -> NovelState
    def load_checkpoint(self, novel_id: str, chapter: int) -> Optional[NovelState]
    def list_checkpoints(self, novel_id: Optional[str] = None) -> list
    def visualize(self) -> str

def create_pipeline(
    llm_client: Callable = None,
    use_memory: bool = True,
    use_outline_refinement: bool = True
) -> NovelPipeline
```

## Stages (stages/)

### `stages/outline/outline_generator.py`

```python
class OutlineGenerator:
    def __init__(self, llm_client=None)
    def generate_chapter_outline(
        self,
        novel_title: str,
        volume_outline: str,
        current_chapter: int,
        characters: List[CharacterInfo],
        target_words: int
    ) -> Dict[str, Any]
```

### `stages/extraction/knowledge_extractor.py`

```python
@dataclass
class ChapterAnalysis:
    chapter: int
    events: List[StoryEvent]
    new_characters: List[str]
    new_foreshadowing: List[str]
    summary: str

class KnowledgeExtractor:
    def __init__(self, llm_client=None, memory=None)
    def extract(self, chapter: int, chapter_content: str) -> ChapterAnalysis
```

### `stages/ip_generation/ip_generator.py`

```python
@dataclass
class StoryBible:
    title: str
    characters: List[Dict[str, Any]]
    key_scenes: List[Dict[str, Any]]
    world_setting: Dict[str, Any]
    timeline: List[str]
    derived_settings: List[Dict[str, Any]]

class IPGenerator:
    def __init__(self, llm_client=None, output_dir="./ip_assets")
    def generate(
        self,
        title: str,
        chapters: Dict[int, str],
        chapter_analyses: Optional[Dict[int, ChapterAnalysis]] = None
    ) -> StoryBible
```

## Storage (core/storage/)

### `core/storage/manager.py`

统一存储管理器，存储位置由 `config.storage.data_dir` 决定。

**目录结构**：
```
{data_dir}/
├── index.json            # 小说清单索引
└── novels/
    └── {novel_id}/       # 单本小说目录
    ├── novel_meta.json
    ├── chapters.json
    ├── reviews.json
    ├── video_script.json                # 镜头剧本
    ├── visual_bible.json                # 视觉圣经 / 人物视觉档
    ├── video_render_plan.json           # 渲染计划
    ├── video_output.json                # 最终输出元数据
    ├── video_consistency_report.json    # 一致性检查报告
    └── ...
```

**函数**：

```python
from core.storage import get_storage_manager

sm = get_storage_manager()

sm.create_novel(novel_id: str, title: str = "", genre: str = "", concept: str = "", target_word_count: int = 3000)
sm.load_novel_meta(novel_id: str)
sm.save_chapters(novel_id: str, chapters: Dict[int, Chapter])
sm.load_chapters(novel_id: str)
sm.list_novels() -> List[dict]
sm.delete_novel(novel_id: str) -> bool
sm.rebuild_index() -> int
```

### `backend/app.py` (Flask API, deprecated)

`backend/app.py` 已下线，不再承载业务 API；仅返回迁移提示（HTTP 410）。
原有 API 已并入 `web_console/app.py`（FastAPI，默认端口 8787）。

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/novels` | GET | 小说清单 |
| `/api/novels/<novel_id>` | GET | 单个小说完整状态 |
| `/api/novels/<novel_id>/chapters` | GET | 章节列表 |
| `/api/novels/<novel_id>/chapters/<chapter_num>` | GET | 章节内容 + 审稿/校对 |

#### `GET /api/health`

返回服务健康状态及当前配置摘要。

**响应**：
```json
{
    "status": "ok",
    "config_path": "/path/to/.storyforge/storyforge.yaml",
    "data_dir": "/path/to/data"
}
```

#### `GET /api/novels`

返回小说清单（轻量索引）。

**响应**：
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

**错误**：
| 状态码 | 含义 |
|--------|------|
| 404 | 小说不存在 |

#### `GET /api/novels/<novel_id>/chapters`

返回章节列表（带状态、字数和最新审稿分数）。

**响应**：
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

**响应**：
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

**错误**：
| 状态码 | 含义 |
|--------|------|
| 404 | 小说或章节不存在 |

## web_console (FastAPI)

### `web_console/app.py`

FastAPI 操作界面，默认端口 8787。

功能：
- 启动任务
- 查看状态
- 查看日志
- 停止任务
- 模板保存
- 并发上限控制
- 日志下载
- 人物 IP 操作区（手动触发）
- 统一业务 API 网关（包含原 backend 接口）

依赖注入策略：每请求 scoped（通过 `Depends` 创建独立 `StorageManager`）。

启动命令：
```bash
uvicorn web_console.app:app --reload --port 8787
```

### Video API

web_console 提供视频生成功能的操作接口（实验性）：

- `POST /api/video/script/generate`：根据指定小说生成镜头剧本与视觉圣经草稿。
    - 请求示例：
        ```json
        {
            "novel_id": "demo_001",
            "chapter": 1,
            "include_assets": true
        }
        ```
    - 返回：任务接受结果（含生成的 `video_script_id` / `visual_bible_id` 引用，或错误信息）。

- `POST /api/video/consistency/check`：对已有剧本/视觉圣经/镜头资产运行量化一致性检查，返回 `ConsistencyReport`。
    - 请求示例：
        ```json
        {
            "novel_id": "demo_001",
            "script_id": "...",
            "thresholds": {"face_consistency": 0.85}
        }
        ```
    - 返回：`ConsistencyReport`（包含 `metrics`, `issues`, `fallback_reasons`，以及是否触发自动回退）。

- `GET /api/video/consistency/{novel_id}`：查询指定小说最近一次一致性检查报告（若有）。

数据模型摘要（core/models/video_assets.py）:

- `VideoScript`：镜头序列与元数据
- `VisualBible`：人物视觉简介与场景参考
- `VideoRenderPlan`：镜头渲染计划与片段列表
- `VideoOutput`：最终视频输出元数据（文件引用）
- `ConsistencyReport`：一致性指标、阈值与回退原因

存储位置：由 `config.storage.data_dir` 决定，视频产物以 `video_*` 文件名由 `StorageManager` 管理（例如 `video_script.json`, `visual_bible.json`, `video_consistency_report.json`）。

