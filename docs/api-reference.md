# API 参考

## Core 模型 (core/models/)

数据模型按领域分组，并统一从 `core.models` 重新导出。

### `core/models/content/` - 创作相关模型

```python
from core.models import (
    NovelMeta, PipelineStage,
    Outline, ChapterOutline, VolumeOutline,
    Chapter, ChapterStatus,
    Review, ReviewRecord,
    Proofread, ProofreadRecord,
)
```

### `core/models/world/` - 世界设定模型

```python
from core.models import Character, CharacterGraph, WorldSetting
```

### `core/models/agent/` - Agent 通信模型

```python
from core.models import AgentMessage, RoutingSuggestion
```

### `core/models/extraction/` - 萃取相关模型

```python
from core.models import (
    ChapterAnalysis,
    ExtractedEntity,
    ExtractedCharacter,
    ExtractedLocation,
    ExtractedForeshadowing,
    CharacterUpdate,
    WorldUpdate,
)
```

### `core/models/ip/` - IP 相关模型

```python
from core.models import CharacterIP, StoryBible
```

### `core/models/video/` - 视频相关模型

```python
from core.models import (
    VideoScript, VisualBible, AssetManifest,
    VideoRenderPlan, ConsistencyReport,
    VideoOutput, VideoState,
)
```

## Core 核心模块

### `core/config.py` - 统一配置

配置文件固定位置：`~/.storyforge/storyforge.yaml`

```python
from core.config import get_config, StoryForgeConfig

config = get_config()

# 访问配置
config.llm.provider        # LLM 配置
config.storage.data_dir    # 存储配置
config.server.port         # 服务器配置
config.security.max_upload_size  # 安全配置
config.pipeline.max_review_rounds  # Pipeline 配置
config.console.max_running_tasks   # 控制台配置
```

### `core/storage/` - 存储管理

统一存储管理器，存储位置由 `config.storage.data_dir` 决定。

**目录结构**：
```
{data_dir}/
├── index.json            # 小说清单索引
└── novels/
    └── {novel_id}/       # 单本小说目录
        ├── novel_meta.json
    ├── outline.json
    ├── characters.json
    ├── world_setting.json
        ├── chapters.json
        ├── reviews.json
    ├── proofreads.json
    ├── chapter_analyses.json
    ├── story_bible.json
    ├── video_state.json
        ├── video_script.json                # 镜头剧本
        ├── visual_bible.json                # 视觉圣经 / 人物视觉档
    ├── video_manifest.json              # 视频资产索引
        ├── video_consistency_report.json    # 一致性检查报告
    ├── video_render_plan.json           # 渲染计划
    ├── video_output.json                # 最终输出元数据
        └── ...
```

**使用方式**：
```python
from core.storage import StorageManager
from core.config import get_config

config = get_config()
sm = StorageManager(config.storage)

sm.create_novel(novel_id, title="", genre="", concept="", target_word_count=3000)
sm.load_novel_meta(novel_id)
sm.save_chapters(novel_id, chapters)
sm.load_chapters(novel_id)
sm.list_novels()
sm.delete_novel(novel_id)
```

## API 端点 (web_console/routes/)

### API 版本管理

- **统一 API**：`/api/v1/` 前缀

### 通用端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/health` | GET | 健康检查 |
| `/api/v1/config` | GET | 配置摘要 |
| `/api/v1/novels` | GET | 小说清单 |
| `/api/v1/novels` | POST | 创建小说 |
| `/api/v1/novels/reorder` | POST | 重排小说列表顺序 |
| `/api/v1/novels/{novel_id}` | GET | 单个小说完整状态 |
| `/api/v1/novels/{novel_id}/context` | GET | 小说大纲/世界观/时间线上下文 |
| `/api/v1/novels/{novel_id}/chapters` | GET | 章节列表 |
| `/api/v1/novels/{novel_id}/chapters/{chapter_num}` | GET | 章节内容 + 审稿/校对 |
| `/api/v1/novels/{novel_id}/characters` | GET | 小说角色列表（需 project_dir） |
| `/api/v1/novels/{novel_id}/cover` | GET | 小说封面资料 |
| `/api/v1/novels/{novel_id}/cover/generate` | POST | 生成小说封面（异步视觉任务） |
| `/api/v1/novels/{novel_id}/characters/{character_id}/visuals` | GET | 角色形象档案（主形象/艺术照/视频立体图） |
| `/api/v1/novels/{novel_id}/characters/{character_id}/visuals/generate` | POST | 提交角色图片生成任务（支持 main/gallery/video） |
| `/api/v1/novels/{novel_id}/characters/{character_id}/visuals/finalize` | POST | 设置/取消角色形象定稿 |
| `/api/v1/novels/{novel_id}/chapters/generate` | POST | 生成指定章节 |
| `/api/v1/novels/{novel_id}/chapters/next` | POST | 生成当前下一章 |
| `/api/v1/novels/{novel_id}/chapters/{chapter_num}/revise` | POST | 重新生成指定章节 |
| `/api/v1/novels/{novel_id}/chapters/proofread` | POST | 提交章节/卷/全书校对任务 |
| `/api/v1/novels/{novel_id}/proposals` | GET | 渐进式披露提案列表 |
| `/api/v1/novels/{novel_id}/context-decisions` | GET | 上下文加载决策日志 |
| `/api/v1/tasks` | GET | 任务列表 |
| `/api/v1/tasks` | POST | 启动新任务 |
| `/api/v1/tasks/{task_id}` | GET | 任务详情 |
| `/api/v1/tasks/{task_id}/stop` | POST | 停止任务 |
| `/api/v1/tasks/{task_id}` | DELETE | 删除任务 |
| `/api/v1/import/formats` | GET | 列出支持的导入格式 |
| `/api/v1/import/upload` | POST | 上传并解析文件 |
| `/api/v1/import/save` | POST | 保存导入内容 |
| `/api/v1/ip/{novel_id}/story_bible` | GET | 获取 story bible |
| `/api/v1/ip/{novel_id}/character/{character_id}` | GET | 获取角色 IP |
| `/api/v1/templates` | GET/POST | 模板管理 |
| `/api/v1/ai/generate` | POST | AI 辅助生成 |
| `/api/v1/video/{novel_id}/state` | GET | 获取视频状态 |
| `/api/v1/video/{novel_id}/script` | GET | 获取视频剧本 |
| `/api/v1/video/{novel_id}/script/generate` | POST | 生成视频剧本 |
| `/api/v1/video/{novel_id}/visual_bible` | GET | 获取视觉圣经 |
| `/api/v1/video/{novel_id}/visual_bible/generate` | POST | 生成视觉圣经 |
| `/api/v1/video/{novel_id}/consistency` | GET | 获取一致性报告 |
| `/api/v1/video/{novel_id}/consistency/check` | POST | 运行一致性检查 |

### 兼容策略

当前不再提供 `/api/*` 旧前缀兼容端点：
- 访问 `/api/*`（非 `/api/v1/*`）会返回 `410 Gone`
- `/api/v1/*` 下不存在的路径返回 `404 Not Found`

### `GET /api/v1/health`

返回服务健康状态及当前配置摘要。

**响应**：
```json
{
    "status": "ok",
    "config_path": "/path/to/.storyforge/storyforge.yaml",
    "data_dir": "/path/to/data",
    "running_tasks": 0,
    "queued_tasks": 0
}
```

### `GET /api/v1/novels`

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
        "approved_chapters": 1
    }
]
```

说明：当传入 `project_dir` 查询参数时，返回形态为 `{ "novels": [...] }`，并包含项目目录下可发现的角色等扩展信息。

### `GET /api/v1/novels/{novel_id}`

返回单个小说的索引信息与角色列表。

**响应**：`NovelMeta.to_index_entry()` 结果 + `characters`

**错误**：
| 状态码 | 说明 |
|--------|------|
| 404 | 小说不存在 |

### `GET /api/v1/novels/{novel_id}/chapters`

返回章节列表（带状态、字数和最新审稿分数）。

### 角色形象端点

#### `GET /api/v1/novels/{novel_id}/characters/{character_id}/visuals`

返回角色形象资料。

**响应**：

```json
{
    "novel_id": "demo_001",
    "character_id": "char_001",
    "profile": {
        "character_id": "char_001",
        "character_name": "林砚",
        "main_image": null,
        "gallery_images": [],
        "video_images": [],
        "finalized": false
    }
}
```

#### `POST /api/v1/novels/{novel_id}/characters/{character_id}/visuals/generate`

提交角色图片生成任务。实际生成在视觉任务 worker 中异步执行，可通过 `GET /api/v1/tasks/{task_id}` 追踪，并通过 `GET /api/v1/novels/{novel_id}/characters/{character_id}/visuals` 读取最终资料。

**请求体**：

```json
{
    "prompt": "夜景街头，黑色风衣",
    "slot_type": "gallery",
    "index": null,
    "style": "电影感",
    "image_preset": "1080p",
    "aspect_ratio": "3:4",
    "regenerate_all": false
}
```

字段说明：
- `slot_type`: `main | gallery | video`
- `index`: 可选，重生成某张图片时传入
- `regenerate_all`: 仅 `video` 生效，为 `true` 时会清空后重生成固定视角组图

流程约束：
- `gallery` 和 `video` 生成前必须已有 `main_image`
- `video` 全量重生成时会输出固定视角图片集合

**响应**：

```json
{
    "task_id": "7a8c...",
    "status": "queued",
    "task_kind": "character_visual",
    "novel_id": "demo_001",
    "character_id": "char_001"
}
```

#### `POST /api/v1/novels/{novel_id}/characters/{character_id}/visuals/finalize`

设置角色形象定稿状态。

**请求体**：

```json
{
    "finalized": true
}
```

### 小说封面端点

#### `GET /api/v1/novels/{novel_id}/cover`

返回当前小说封面资料；若尚未生成，返回空封面结构。

#### `POST /api/v1/novels/{novel_id}/cover/generate`

提交小说封面生成任务。

**响应**：

```json
{
    "task_id": "4d5e...",
    "status": "queued",
    "task_kind": "novel_cover",
    "novel_id": "demo_001"
}
```

### 章节任务端点

#### `POST /api/v1/novels/{novel_id}/chapters/generate`

提交指定章节生成任务。若请求体未提供 `chapter_num`，默认使用小说当前章节。

#### `POST /api/v1/novels/{novel_id}/chapters/next`

按当前 `meta.current_chapter` 提交下一章生成任务。

#### `POST /api/v1/novels/{novel_id}/chapters/{chapter_num}/revise`

为指定章节重新提交生成/修订任务。

#### `POST /api/v1/novels/{novel_id}/chapters/proofread`

提交校对任务。

**请求体**：

```json
{
    "scope": "chapter",
    "chapter_num": 3,
    "volume_num": null
}
```

其中 `scope` 仅支持 `chapter | volume | book`。

### 任务端点

#### `POST /api/v1/tasks`

启动新任务（`pipeline` 或 `ip`）。视觉任务不通过该端点创建，而是由小说封面/角色形象端点提交。

约束与校验：
- `project_dir` 必须存在，且不能是文件系统根目录 `/`
- `pipeline` 任务的 `command` 必须通过模板白名单校验（默认命令 + 当前项目已保存模板命令）

**请求体**：
```json
{
    "task_type": "pipeline|ip",
    "novel_id": "demo_001",
    "command": "python examples/demo_pipeline.py",
    "project_dir": "/path/to/project",
    "force_regenerate": false
}
```

#### `GET /api/v1/tasks/{task_id}`

获取任务详情，包含日志尾巴。

#### `GET /api/v1/tasks`

返回三组任务：`tasks`、`ip_tasks`、`visual_tasks`。

#### `POST /api/v1/tasks/{task_id}/stop`

停止运行中的任务。

### 导入端点

#### `POST /api/v1/import/upload`

上传并解析文件（支持 text/epub/pdf/image）。

**安全特性**：
- 文件大小验证（默认 50MB）
- 文件扩展名白名单验证
- 流式写入临时文件（避免一次性读入内存）
- 安全的临时文件处理与清理
- 文件名清理

#### `POST /api/v1/import/save`

保存解析后的内容为新小说。

### 健康与配置端点

#### `GET /api/v1/health`

返回服务状态、配置路径、数据目录和任务队列长度。

#### `GET /api/v1/config`

返回控制台任务并发配置摘要：

```json
{
    "max_running_tasks": 3,
    "configured_max_running_tasks": 3,
    "running_tasks": 0,
    "queued_tasks": 0
}
```

## web_console 架构

### `web_console/app.py` - FastAPI 入口

FastAPI 应用生命周期管理：
- 启动时初始化 TaskRegistry
- 注册默认任务执行器
- 加载任务状态
- 启动调度线程
- 关闭时清理资源

### `web_console/runtime/registry.py` - TaskRegistry

任务状态封装类，可注入、可测试：

```python
from web_console.runtime.registry import TaskRegistry
from pathlib import Path

registry = TaskRegistry(Path("/path/to/storage"))
registry.load_state()
registry.start_dispatcher()

# 注册任务执行器
def my_runner(task_id: str):
    pass

registry.register_runner("my_type", my_runner)
```

### `web_console/middleware/` - 中间件

- **RequestIdMiddleware**：请求 ID 生成与传递
- **错误处理**：统一错误响应格式，包含 `request_id`；非 debug 模式不回传原始异常细节

### `web_console/security.py` - 安全工具

```python
from web_console.security import (
    safe_novel_id, validate_path_safe, safe_join_path,
    get_allowed_extensions, validate_file_extension,
    validate_file_size, sanitize_filename, get_upload_type
)
```

## Agents (agents/)

### `agents/creation_agents.py`

```python
class WriterAgent(BaseAgent):
    def invoke(self, state) -> NovelState

class ReviewerAgent(BaseAgent):
    def invoke(self, state) -> NovelState

class ReviserAgent(BaseAgent):
    def invoke(self, state) -> NovelState

class ProofreaderAgent(BaseAgent):
    def invoke(self, state) -> NovelState
```

## Pipeline (pipeline/)

### `pipeline/novel_pipeline.py`

```python
from pipeline.novel_pipeline import NovelPipeline, create_pipeline

pipeline = create_pipeline(
    llm_client=llm,
    use_memory=True,
    use_outline_refinement=True,
    use_message_bus=True,
    use_agent_routing=False
)

result = pipeline.run(state)
checkpoints = pipeline.list_checkpoints(novel_id="demo_001")
result = pipeline.resume(novel_id="demo_001", chapter=1)
```

## 错误响应格式

统一错误响应：

```json
{
    "success": false,
    "error_code": "1000|1001|1004|1005|...",
    "message": "错误描述",
    "details": [],
    "timestamp": "2026-05-12T10:00:00",
    "request_id": "abc123",
    "path": "/api/v1/novels/demo_001"
}
```

说明：
- `RequestValidationError` 等已知错误会包含字段级 `details`
- 未捕获异常在 `server.debug=false` 时通常返回空 `details`，`server.debug=true` 时会附带异常类型与消息
