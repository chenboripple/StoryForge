# 配置系统说明

StoryForge 使用单一 YAML 配置文件，所有运行配置都从该文件读取。

## 当前实现

- 当前配置文件固定为 `~/.storyforge/storyforge.yaml`。
- `llm`、`models`、`model_routing`、`storage`、`server`、`pipeline`、`console` 都从同一文件加载。
- 临时创建的 Agent 仍受该配置文件控制。

## 后续计划

1. 为视频 provider、图像 provider、向量 provider 补充更完整的字段说明。
2. 为 Web Console 暴露更清晰的配置摘要和运行态检查接口。

核心原则：所有 Agent（包含临时创建的 Agent）使用什么模型，都由用户在 `~/.storyforge/storyforge.yaml` 决定。

---

## 配置文件 (YAML)

### 用途
- FastAPI API 网关服务（web_console）
- 数据存储
- Pipeline 配置

### 配置文件位置

- 文件：`~/.storyforge/storyforge.yaml`
- 加载入口：`core/config.py`
- 适用范围：FastAPI 网关（web_console）、Pipeline、模型路由

### 配置文件示例

```yaml
llm:
    provider: mock
    model: gpt-4o-mini
    api_key: ""
    base_url: ""
    temperature: 0.7
    timeout: 60
    extra: {}

models:
    - name: writer-main
      provider: openai
      model: gpt-4o-mini
      api_key: ""
      base_url: ""
      temperature: 0.8
      timeout: 60
      max_tokens: 4096
      enabled: true
      cost_per_1k_input: 0.15
      cost_per_1k_output: 0.60
      task_preferences:
          writing: 0.95
          outline: 0.9

    - name: reviewer-fast
      provider: anthropic
      model: claude-3-5-sonnet-latest
      api_key: ""
      temperature: 0.3
      timeout: 45
      max_tokens: 4096
      enabled: true
      task_preferences:
          review: 0.95
          extraction: 0.9

model_providers:
        - name: provider_a
            provider: anthropic
            api_key: ""
            base_url: ""
            timeout: 60

        - name: provider_b
            provider: anthropic
            api_key: ""
            base_url: ""
            timeout: 60

# 通过 provider_name 复用 provider 配置，避免重复写 base_url/api_key
models:
        - name: writer-main
            provider_name: provider_a
            model: gpt-4o-mini
            temperature: 0.8

        - name: reviewer-fast
            provider_name: provider_b
            model: claude-3-5-sonnet-latest
            temperature: 0.3

model_routing:
    task_mapping:
        writing: [writer-main, reviewer-fast]
        review: [reviewer-fast, writer-main]
        proofreading: [reviewer-fast, writer-main]
        extraction: [reviewer-fast, writer-main]
        outline: [writer-main, reviewer-fast]
        ip_generation: [writer-main, reviewer-fast]
        general: [reviewer-fast, writer-main]

    # 可选：固定 Agent 的默认偏好；未配置的 Agent 自动走 task_mapping
    agent_preferences:
        墨川: writer-main
        青锋: reviewer-fast

    # 成功率监控 + 自动降级
    auto_downgrade: true
    min_success_rate: 0.6
    health_min_calls: 5
    failure_cooldown_sec: 180

storage:
    data_dir: ~/.storyforge/data

server:
    host: 127.0.0.1
    port: 5089
    cors_origins:
        - "http://localhost:3000"
        - "http://127.0.0.1:3000"
    cors_allow_credentials: false
    debug: false

pipeline:
    max_review_rounds: 3
    default_target_word_count: 3000

console:
    max_running_tasks: 3
    default_command: "python examples/demo_pipeline.py"
    template_file: "~/.storyforge/templates.yaml"

debug:
    output_dir: "debug_output"
```

### 视频提供商配置（可选）

如果启用了视频/图像/向量服务，建议在配置文件中添加 `video` 小节来指定 provider、api_key 与相关参数。示例：

```yaml
video:
    image_provider: mock        # image provider 名称（mock / stability / openai_images / ...）
    video_provider: mock        # video provider 名称（mock / vendor_x / ...）
    embedding_provider: mock    # 向量嵌入提供商（mock / openai / sentence-transformers）
    api_keys:
        image: ""
        video: ""
        embedding: ""
    extra: {}
```

说明：
- `image_provider` / `video_provider` / `embedding_provider` 对应仓库中 `core.video.providers` 定义的抽象接口。当前仓库包含占位（stub）实现；接入真实服务需要在此处填写 provider 名称与密钥，并在运行时由 `llm_factory` / provider 工厂选择具体实现。
- 配置文件仍位于 `~/.storyforge/storyforge.yaml`，并且不应提交到 Git（请把密钥保存在配置文件中，配置文件不会被仓库追踪）。

**注意**：配置文件放在用户主目录，不会被任何 Git 仓库追踪，可安全填写 API 密钥。

完整配置示例与更多说明见 [config-example.md](config-example.md)。

---

## 配置项详解（YAML）

### LLM 配置 (`llm.*`)

| 字段 | 说明 | 可选值 | 默认值 |
|------|------|--------|--------|
| `llm.provider` | LLM 提供商 | `mock` / `openai` / `anthropic` | `mock` |
| `llm.model` | 模型名称 | 模型 ID（如 `gpt-4o-mini`、`claude-3-opus`） | `gpt-4o-mini` |
| `llm.api_key` | API 密钥 | 你的 API Key | `""` |
| `llm.base_url` | 自定义 endpoint | 留空使用官方默认 | `""` |
| `llm.temperature` | 采样温度 | 0.0 - 2.0 | `0.7` |
| `llm.timeout` | 请求超时（秒） | 正整数 | `60` |
| `llm.extra` | 透传 SDK 的额外参数 | Dict | `{}` |

说明：`llm` 仍可用于直接 `llm_factory` 场景；当前 `ModelRouter` 实现依赖 `models + model_routing`（及可选 `model_providers`），不自动回退到单 `llm`。

---

### 多模型路由配置 (`models.*` + `model_routing.*`)

| 字段 | 说明 | 是否必填 |
|------|------|----------|
| `models` | 预定义模型池（可多个 provider） | 推荐 |
| `model_providers` | provider 连接配置池（可被多个 model 复用） | 推荐 |
| `models[].name` | 路由别名（供 task_mapping/agent_preferences 引用） | 是 |
| `models[].provider_name` | 复用的 provider 配置名（推荐） | 否 |
| `models[].provider` | `mock/openai/anthropic/azure/local/custom` | 是 |
| `models[].model` | 真实模型 ID | 是 |
| `models[].task_preferences` | 任务偏好分（0-1） | 否 |
| `model_routing.task_mapping` | 每种任务的候选模型优先级列表 | 推荐 |
| `model_routing.agent_preferences` | 每个 Agent 的默认模型偏好（可选） | 否 |
| `model_routing.auto_downgrade` | 启用自动降级 | 否 |
| `model_routing.min_success_rate` | 最低成功率阈值 | 否 |
| `model_routing.health_min_calls` | 开始应用成功率判断的最小调用数 | 否 |
| `model_routing.failure_cooldown_sec` | 连续失败后的冷却时长（秒） | 否 |

临时 Agent 说明：

- 临时创建的 Agent 不需要预先定义在 `agent_preferences`。
- 临时 Agent 可以在运行时传 `preferred_model`，优先级高于 `agent_preferences`。
- 若未传 `preferred_model`，将按 `task_mapping` 自动路由，并在失败时自动降级。

provider 复用说明：

- 你可以配置“一个 provider 多个 model”，仅在 `model_providers` 写一次 `api_key/base_url`。
- 也可以配置“多个 provider + 多模型”，每个 model 用 `provider_name` 选择连接来源。
- 映射层只需要写 model 名（`task_mapping` / `agent_preferences`），无需重复 provider 连接参数。

运行要求：

- 走 `ModelRouter` 路径时，必须存在至少一个可用模型（来自 `models` 顶层定义或 `model_providers[].models` 展开）。
- 若映射中引用了不存在的模型名，启动路由时会报错。

#### 示例：OpenAI / Azure OpenAI

```yaml
llm:
    provider: openai
    model: gpt-4o-mini
    api_key: "sk-..."
    temperature: 0.7
```

#### 示例：OpenAI 兼容接口（DeepSeek / vLLM）

```yaml
llm:
    provider: openai
    model: deepseek-chat
    api_key: "sk-..."
    base_url: "https://api.deepseek.com/v1"
```

#### 示例：Anthropic Claude

```yaml
llm:
    provider: anthropic
    model: claude-3-opus-20240229
    api_key: "sk-ant..."
    temperature: 0.7
    extra:
        max_tokens: 4096  # Claude 需要指定
```

#### 示例：Mock（用于本地测试）

```yaml
llm:
    provider: mock
    # model/api_key 等被忽略
```

---

### 存储配置 (`storage.*`)

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `storage.data_dir` | 小说数据目录（完全由配置决定） | `~/.storyforge/data` |

**路径解析规则**（按优先级）：

| 写法 | 解析方式 | 示例 |
|------|----------|------|
| 绝对路径 | 直接使用 | `/var/lib/storyforge/data` |
| `~/...` | 相对用户主目录展开 | `~/.storyforge/data` → `/Users/you/.storyforge/data` |
| 相对路径 | 相对于配置文件所在目录 | 配置文件 `~/.storyforge/storyforge.yaml`，`data_dir: data` → `~/.storyforge/data` |

> 设计意图：data 目录与项目代码完全解耦，便于多项目共享数据、统一备份。

**目录结构**：
```
~/.storyforge/data/
├── index.json
└── novels/
    └── demo_001/
        ├── novel_meta.json
        ├── outline.json
        ├── characters.json
        ├── world_setting.json
        ├── chapters.json
        ├── reviews.json
        ├── proofreads.json
        ├── chapter_analyses.json
        ├── story_bible.json
        └── ...
```

---

### 服务器配置 (`server.*`)

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `server.host` | 监听地址 | `127.0.0.1` |
| `server.port` | 端口 | `5089` |
| `server.cors_origins` | 允许跨域的源（默认仅本地前端） | `["http://localhost:3000", "http://127.0.0.1:3000"]` |
| `server.cors_allow_credentials` | CORS 是否允许携带凭据 | `false` |
| `server.debug` | 服务调试开关（影响错误详情暴露） | `false` |

---

### Pipeline 配置 (`pipeline.*`)

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `pipeline.max_review_rounds` | 最大审稿轮次 | `3` |
| `pipeline.default_target_word_count` | 默认单章字数目标 | `3000` |

### 控制台配置 (`console.*`)

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `console.max_running_tasks` | 控制台任务并发上限 | `3` |
| `console.default_command` | 默认允许的 pipeline 命令模板 | `python examples/demo_pipeline.py` |
| `console.template_file` | 命令模板存储文件 | `~/.storyforge/templates.yaml` |

### 调试配置 (`debug.*`)

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `debug.output_dir` | 调试输出目录 | `debug_output` |

---

## Python API

### YAML 配置 (core.config)

```python
from core.config import get_config, load_config, reset_config

# 获取配置（带缓存）
config = get_config()

# 强制重新加载
config = get_config(reload=True)

# 注意：load_config(path) 的 path 参数目前仅保留兼容，不参与路径选择。
# 实际总是从 ~/.storyforge/storyforge.yaml 加载。
config = load_config()

# 清空缓存（测试用）
reset_config()

# 访问配置
print(config.llm.provider)
print(config.server.port)
print(config.data_dir_abs)  # data_dir 的绝对路径
```

### 诊断命令

```bash
# 查看当前 YAML 配置（含来源）
python -m core.config
```
