# 配置系统说明

StoryForge 使用两套配置系统（历史原因，两者共存），请根据使用场景选择：

---

## 配置系统一：web_console (JSON)

### 用途
- FastAPI 操作界面
- 任务管理
- IP 生成
- 调试输出

### 配置文件位置

- 文件：`~/.storyforge/config.json`
- 加载入口：`core/settings.py`
- 优先级：环境变量 > 配置文件

### 环境变量

| 环境变量 | 配置路径 |
|----------|----------|
| `STORYFORGE_MAX_RUNNING_TASKS` | `console.max_running_tasks` |
| `STORYFORGE_DEFAULT_COMMAND` | `console.default_command` |
| `STORYFORGE_TEMPLATE_FILE` | `console.template_file` |
| `STORYFORGE_DEBUG_DIR` | `debug.output_dir` |
| `STORYFORGE_DEFAULT_TARGET_WORD_COUNT` | `pipeline.default_target_word_count` |

### 配置文件示例

```json
{
    "console": {
        "max_running_tasks": 2,
        "default_command": "python examples/debug_pipeline.py",
        "template_file": "~/work/StoryForge/web_console/templates.json"
    },
    "debug": {
        "output_dir": "~/work/StoryForge/debug_output"
    },
    "pipeline": {
        "default_target_word_count": 3000
    }
}
```

### 诊断命令

```bash
# 查看当前生效配置（含来源）
python -m core.settings

# 仅校验配置（成功返回 0，失败非 0）
python -m core.settings --check
```

---

## 配置系统二：backend (YAML)

### 用途
- Flask API 服务
- 数据存储
- Pipeline 配置

### 配置文件位置

优先级从高到低：

1. `$STORYFORGE_CONFIG` 环境变量指定的路径
2. `~/.storyforge/storyforge.yaml`  ← **推荐位置**
3. `<project_root>/.storyforge/storyforge.yaml`
4. 内置默认值

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
    host: 0.0.0.0
    port: 5089
    cors_origins: "*"

pipeline:
    max_review_rounds: 3
    default_target_word_count: 3000
```

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
| `server.host` | 监听地址 | `0.0.0.0` |
| `server.port` | 端口 | `5089` |
| `server.cors_origins` | 允许跨域的源 | `"*"` |

**覆盖方式**：可通过环境变量 `$PORT` / `$HOST` 临时覆盖（注意：仅适用于 Flask backend）。

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

# 显式指定路径
config = load_config("/path/to/myconfig.yaml")

# 清空缓存（测试用）
reset_config()

# 访问配置
print(config.llm.provider)
print(config.server.port)
print(config.data_dir_abs)  # data_dir 的绝对路径
```

### JSON 配置 (core.settings)

```python
from core.settings import get_settings, get_settings_with_sources

# 获取配置（带缓存）
settings = get_settings()

# 获取配置 + 来源信息
settings, sources = get_settings_with_sources()
print(sources)  # {"console.max_running_tasks": "file:..." , ...}

# 访问配置
print(settings.console.max_running_tasks)
print(settings.debug.output_dir)
print(settings.pipeline.default_target_word_count)
```
