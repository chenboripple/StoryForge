# StoryForge 配置文件示例

> 本文件是 `storyforge.yaml` 的示例模板。复制下方代码块为 `~/.storyforge/storyforge.yaml`，按需修改后即可生效。

## 安装位置

推荐放置在用户主目录下：

```bash
mkdir -p ~/.storyforge
# 将下方代码块的内容写入：
~/.storyforge/storyforge.yaml
```

`deploy.sh` 首次运行时若发现 `~/.storyforge/storyforge.yaml` 不存在，会自动从本文档复制一份。

## 加载位置

配置文件固定位置：

1. `~/.storyforge/storyforge.yaml`
2. 若文件不存在，则使用内置默认值

## 完整示例

```yaml
# ==================== 大模型配置 ====================
llm:
  # provider 可选: mock | openai | anthropic
  #   mock:      内置占位响应（不调用任何 API，用于本地测试）
  #   openai:    OpenAI 或 OpenAI 兼容协议（如 DeepSeek / OpenRouter / 本地 vllm）
  #   anthropic: Anthropic Claude
  provider: mock

  # 模型名称
  model: gpt-4o-mini

  # API Key（若 provider 为 mock 可留空）
  api_key: ""

  # 自定义 endpoint（可选，留空使用官方默认）
  # 例如 OpenRouter: https://openrouter.ai/api/v1
  # 例如本地 vllm:    http://localhost:8000/v1
  base_url: ""

  # 默认采样温度（0.0-2.0）
  temperature: 0.7

  # 单次请求超时（秒）
  timeout: 60

  # 透传给底层 SDK 的额外参数（按需）
  extra:
    # max_tokens: 4096

# ==================== 存储配置 ====================
storage:
  # 小说数据目录（完全由配置决定，不依赖项目目录）
  #   - 绝对路径：直接使用，例如 /var/lib/storyforge/data
  #   - ~/ 开头：相对用户主目录展开，例如 ~/.storyforge/data
  #   - 相对路径：相对于配置文件所在目录解析
  #     例如配置文件在 ~/.storyforge/storyforge.yaml，
  #     data_dir: data → ~/.storyforge/data
  data_dir: ~/.storyforge/data

# ==================== 服务器配置 ====================
server:
  host: 0.0.0.0
  port: 8787
  cors_origins: "*"
  debug: false

# ==================== Pipeline 配置 ====================
pipeline:
  # 最大审稿轮次（超过强制进入校对）
  max_review_rounds: 3
  # 默认单章目标字数
  default_target_word_count: 3000
```

## 不同 provider 的配置示例

### OpenAI

```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  api_key: "sk-..."
  temperature: 0.7
```

### OpenAI 兼容服务（DeepSeek / OpenRouter / 本地 vLLM）

```yaml
llm:
  provider: openai
  model: deepseek-chat
  api_key: "sk-..."
  base_url: "https://api.deepseek.com/v1"
```

### Anthropic Claude

```yaml
llm:
  provider: anthropic
  model: claude-3-opus-20240229
  api_key: "sk-ant..."
  temperature: 0.7
  extra:
    max_tokens: 4096   # Claude 必须指定
```

### Mock（离线测试）

```yaml
llm:
  provider: mock
  # 其他字段可省略
```

## 安全提示

- `~/.storyforge/storyforge.yaml` **不应**被任何 Git 仓库追踪，可放心填写真实 API Key
- 配置统一放在用户主目录，避免把密钥写进仓库
