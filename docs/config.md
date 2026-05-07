# 配置系统说明

## 配置文件

StoryForge 使用 YAML 配置文件管理所有设置（LLM、存储、服务器、Pipeline 等）。

### 配置文件位置

优先级从高到低：

1. `$STORYFORGE_CONFIG` 环境变量指定的路径
2. `~/.storyforge/storyforge.yaml`  ← **推荐位置**
3. `<项目根目录>/.storyforge/storyforge.yaml`
4. 内置默认值

### 首次运行

`deploy.sh` 会自动从 `docs/config-example.md` 提取配置模板复制到 `~/.storyforge/storyforge.yaml`：

```bash
./deploy.sh config  # 查看当前配置文件
```

### 编辑配置

编辑 `~/.storyforge/storyforge.yaml`：

```yaml
llm:
  provider: mock
  model: gpt-4o-mini
  api_key: ""
  base_url: ""
  temperature: 0.7
  timeout: 60

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

## 配置项详解

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

**覆盖方式**：可通过环境变量 `$PORT` / `$HOST` 临时覆盖

---

### Pipeline 配置 (`pipeline.*`)

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `pipeline.max_review_rounds` | 最大审稿轮次 | `3` |
| `pipeline.default_target_word_count` | 默认单章字数目标 | `3000` |

---

## Python API

### 获取配置

```python
from core.config import get_config

config = get_config()

print(config.llm.provider)
print(config.server.port)
print(config.data_dir_abs)  # data_dir 的绝对路径
```

### 重新加载配置

```python
from core.config import get_config, reset_config

reset_config()  # 清空缓存
config = get_config(reload=True)  # 强制重新加载
```

### 显式指定路径

```python
from core.config import load_config

config = load_config("/path/to/myconfig.yaml")
```

---

## 部署脚本集成

`deploy.sh` 会自动从配置读取 `server.port` 和 `server.host`：

```bash
./deploy.sh status
```

输出会显示配置文件路径：
```
========================================
      StoryForge 部署状态
========================================
配置文件: /Users/you/.storyforge/storyforge.yaml
[OK] 配置: 已加载
```
