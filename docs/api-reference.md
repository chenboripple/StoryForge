# API 参考

## Core 模型 (core/models/)

数据模型按领域分组：

### `core/models/content/` - 内容相关模型

```python
from core.models import (
    NovelMeta, PipelineStage,
    Outline, ChapterOutline, VolumeOutline,
    Chapter, ChapterStatus,
    ReviewRecord, ProofreadRecord
)
```

### `core/models/world/` - 世界设定模型

```python
from core.models import CharacterInfo, WorldSetting
```

### `core/models/agent/` - Agent 相关模型

```python
from core.models import AgentPersona, AgentMessage, MessageBus
```

### `core/models/extraction/` - 萃取相关模型

```python
from core.models import ChapterAnalysis, StoryEvent, CharacterArc, WorldState, Inconsistency, StoryMemory
```

### `core/models/ip/` - IP 相关模型

```python
from core.models import IPAssets, StoryBible
```

### `core/models/video/` - 视频相关模型

```python
from core.models import (
    VideoScript, VisualBible, VideoRenderPlan,
    VideoOutput, ConsistencyReport
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
        ├── chapters.json
        ├── reviews.json
        ├── video_script.json                # 镜头剧本
        ├── visual_bible.json                # 视觉圣经 / 人物视觉档
        ├── video_render_plan.json           # 渲染计划
        ├── video_output.json                # 最终输出元数据
        ├── video_consistency_report.json    # 一致性检查报告
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
| `/api/v1/novels/{novel_id}` | GET | 单个小说完整状态 |
| `/api/v1/novels/{novel_id}/chapters` | GET | 章节列表 |
| `/api/v1/novels/{novel_id}/chapters/{chapter_num}` | GET | 章节内容 + 审稿/校对 |
| `/api/v1/novels/{novel_id}/characters` | GET | 小说角色列表（需 project_dir） |
| `/api/v1/novels/{novel_id}/characters/{character_id}/visuals` | GET | 角色形象档案（主形象/艺术照/视频立体图） |
| `/api/v1/novels/{novel_id}/characters/{character_id}/visuals/generate` | POST | 生成角色图片（支持 main/gallery/video） |
| `/api/v1/novels/{novel_id}/characters/{character_id}/visuals/finalize` | POST | 设置/取消角色形象定稿 |
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

说明：当传入 `project_dir` 查询参数时，返回形态为 `{ "novels": [...] }`。

### `GET /api/v1/novels/{novel_id}`

返回单个小说的完整状态。

**响应**：完整小说元数据 + 章节列表

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

按槽位生成角色图片。

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

#### `POST /api/v1/novels/{novel_id}/characters/{character_id}/visuals/finalize`

设置角色形象定稿状态。

**请求体**：

```json
{
    "finalized": true
}
```

### 任务端点

#### `POST /api/v1/tasks`

启动新任务（pipeline 或 ip）。

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
