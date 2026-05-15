# StoryForge 配置文件示例

> 本文件是 `storyforge.yaml` 的示例模板。复制下方代码块为 `~/.storyforge/storyforge.yaml`，按需修改后即可生效。

> 约定：所有 Agent 使用什么模型，均由该配置文件控制（包含临时创建的 Agent）。

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

# ==================== 多模型路由（可选，推荐） ====================
# 说明：如果配置了 models，ModelRouter 将优先使用这里；
# 当前实现中，ModelRouter 需要可用的 models/model_providers 配置；
# llm 主要用于直接 llm_factory 场景，不作为 ModelRouter 的自动回退来源。
model_providers:
  - name: provider_a
    provider: anthropic
    api_key: ""
    base_url: ""
    timeout: 60
    extra:
      max_tokens: 4096

  - name: provider_b
    provider: anthropic
    api_key: ""
    base_url: ""
    timeout: 60

models:
  - name: writer-main
    provider_name: provider_a
    model: gpt-4o-mini
    temperature: 0.8
    timeout: 60
    max_tokens: 4096
    enabled: true
    cost_per_1k_input: 0.15
    cost_per_1k_output: 0.60
    task_preferences:
      writing: 0.95
      outline: 0.9
      review: 0.75

  - name: reviewer-fast
    provider_name: provider_a
    model: claude-3-5-sonnet-latest
    temperature: 0.3
    timeout: 45
    max_tokens: 4096
    enabled: true
    task_preferences:
      review: 0.95
      extraction: 0.9
      proofreading: 0.85

  - name: proofreader-cheap
    provider_name: provider_b
    model: gpt-4o-mini
    temperature: 0.1
    timeout: 30
    max_tokens: 2048
    enabled: true
    task_preferences:
      proofreading: 0.95
      general: 0.8

model_routing:
  # per-task 映射（按优先级从左到右）
  task_mapping:
    writing: [writer-main, reviewer-fast]
    outline: [writer-main, reviewer-fast]
    review: [reviewer-fast, writer-main]
    proofreading: [proofreader-cheap, reviewer-fast]
    extraction: [reviewer-fast, writer-main]
    ip_generation: [writer-main, reviewer-fast]
    general: [proofreader-cheap, writer-main]

  # per-agent 偏好（可选，不要求每个 agent 都配置）
  # 未命中的 agent 会走 task_mapping 默认路由。
  agent_preferences:
    墨川: writer-main
    青锋: reviewer-fast
    砚清: proofreader-cheap

  # 成功率监控 + 自动降级
  auto_downgrade: true
  min_success_rate: 0.6
  health_min_calls: 5
  failure_cooldown_sec: 180

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
  host: 127.0.0.1
  port: 8787
  cors_origins:
    - "http://localhost:3000"
    - "http://127.0.0.1:3000"
  cors_allow_credentials: false
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

## 多模型说明

- 支持 `model_providers + models` 两层结构：
  - `model_providers` 统一配置 provider / api_key / base_url
  - `models` 通过 `provider_name` 复用 provider，仅填写 model 名和差异参数
- `ModelRouter` 路径下需确保存在可用 `models`；否则路由初始化会失败。
- `preferred_model` 是可选覆盖，不要求每个 Agent 预先定义。
- 若某 Agent 没有配置 `agent_preferences`，系统会按 `task_mapping` 自动选主模型并带 fallback。
- 路由器会统计成功率，并在连续失败或低成功率时自动降级到备选模型。
- 临时 Agent 也走同一套规则：运行时可传 `preferred_model`，否则按 `task_mapping` 自动路由。

## 安全提示

- `~/.storyforge/storyforge.yaml` **不应**被任何 Git 仓库追踪，可放心填写真实 API Key
- 配置统一放在用户主目录，避免把密钥写进仓库
