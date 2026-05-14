# 配置系统说明

StoryForge 使用单一 YAML 配置文件，所有运行配置都从该文件读取。

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

storage:
    data_dir: ~/.storyforge/data

server:
    host: 127.0.0.1
    port: 8787
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

完整配置示例与更多说明见 [docs/config-example.md](config-example.md)。

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
├── index.json         # 小说清单索引
└── novels/
    ├── demo_001.json  # 单个小说完整状态
    └── demo_002.json
```

---

### 服务器配置 (`server.*`)

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `server.host` | 监听地址 | `127.0.0.1` |
| `server.port` | 端口 | `8787` |
| `server.cors_origins` | 允许跨域的源（默认仅本地前端） | `["http://localhost:3000", "http://127.0.0.1:3000"]` |
| `server.cors_allow_credentials` | CORS 是否允许携带凭据 | `false` |
| `server.debug` | 服务调试开关（影响错误详情暴露） | `false` |

---

### Pipeline 配置 (`pipeline.*`)

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `pipeline.max_review_rounds` | 最大审稿轮次 | `3` |
| `pipeline.default_target_word_count` | 默认单章字数目标 | `3000` |

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
