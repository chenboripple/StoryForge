"""
StoryForge - 配置加载

配置文件位置：
    ~/.storyforge/storyforge.yaml

配置项包括：大模型、存储位置、服务器端口、Pipeline行为等。
不依赖系统环境变量。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

_DEFAULT_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".storyforge", "storyforge.yaml")


# -----------------------------------------------------------------------------
# 安全配置
# -----------------------------------------------------------------------------

# 安全常量
DEFAULT_MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_UPLOAD_TYPES = {
    "text": [".txt", ".md", ".markdown", ".html", ".htm", ".rst", ".org"],
    "epub": [".epub"],
    "pdf": [".pdf"],
    "image": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp"],
}


# -----------------------------------------------------------------------------
# 配置数据类
# -----------------------------------------------------------------------------

@dataclass
class LLMConfig:
    provider: str = "mock"  # mock | openai | anthropic
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""  # 自定义 endpoint（例如代理或私有部署）
    temperature: float = 0.7
    timeout: int = 60
    extra: Dict[str, Any] = field(default_factory=dict)  # 透传 SDK 额外参数


@dataclass
class ModelSpecConfig:
    """多模型配置项（兼容 llm 的扩展版）。"""

    name: str = ""
    # 可选：引用 model_providers 里的 provider 配置名
    provider_name: str = ""
    provider: str = "mock"  # mock | openai | anthropic | azure | local | custom
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.7
    timeout: int = 60
    max_tokens: int = 4096
    enabled: bool = True
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    # key 为 TaskType 的 value 字符串（如 writing/review）
    task_preferences: Dict[str, float] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelProviderConfig:
    """模型供应商配置（可被多个 model 复用）。"""

    name: str = ""
    provider: str = "anthropic"  # mock | openai | anthropic | azure | local | custom
    api_key: str = ""
    base_url: str = ""
    timeout: int = 60
    extra: Dict[str, Any] = field(default_factory=dict)
    # 可选：直接在 provider 下声明多个模型（避免重复 provider_name）。
    models: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ModelRoutingConfig:
    """模型路由策略配置。"""

    # per-task 映射：task -> [model_name...]
    task_mapping: Dict[str, List[str]] = field(default_factory=dict)
    # per-agent 偏好：agent_name -> model_name
    agent_preferences: Dict[str, str] = field(default_factory=dict)
    # 自动降级（健康检测 + 冷却）
    auto_downgrade: bool = True
    min_success_rate: float = 0.6
    health_min_calls: int = 5
    failure_cooldown_sec: int = 180


@dataclass
class StorageConfig:
    data_dir: str = "~/.storyforge/data"  # 相对路径相对于配置文件目录解析


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8787
    cors_origins: Optional[List[str]] = field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
    )
    cors_allow_credentials: bool = False
    debug: bool = False


@dataclass
class SecurityConfig:
    """安全相关配置。"""
    max_upload_size: int = DEFAULT_MAX_UPLOAD_SIZE  # 最大上传字节数
    allowed_upload_extensions: Optional[List[str]] = None  # None 表示使用默认


@dataclass
class PipelineConfig:
    max_review_rounds: int = 3
    default_target_word_count: int = 3000


@dataclass
class ConsoleConfig:
    max_running_tasks: int = 3
    default_command: str = "python examples/demo_pipeline.py"
    template_file: str = "~/.storyforge/templates.yaml"

    @property
    def template_file_abs(self) -> str:
        path = self.template_file
        if path.startswith("~"):
            return os.path.expanduser(path)
        return path


@dataclass
class DebugConfig:
    output_dir: str = "debug_output"


@dataclass
class StoryForgeConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    model_providers: List[ModelProviderConfig] = field(default_factory=list)
    models: List[ModelSpecConfig] = field(default_factory=list)
    model_routing: ModelRoutingConfig = field(default_factory=ModelRoutingConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    console: ConsoleConfig = field(default_factory=ConsoleConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    config_path: Optional[str] = None  # 加载来源（None 表示使用默认值）

    @property
    def data_dir_abs(self) -> str:
        """返回绝对路径的 data_dir。

        路径解析规则：
            绝对路径：直接使用
            ~/ 开头：相对于用户主目录展开
            相对路径：相对于配置文件目录解析；若无配置文件则相对于当前工作目录
        """
        path = self.storage.data_dir

        # 处理 ~/ 开头的路径
        if path.startswith("~"):
            return os.path.normpath(os.path.expanduser(path))

        # 绝对路径直接返回
        if os.path.isabs(path):
            return os.path.normpath(path)

        # 相对路径：相对于配置文件目录或当前工作目录
        if self.config_path:
            base_dir = os.path.dirname(os.path.abspath(self.config_path))
        else:
            base_dir = os.getcwd()

        return os.path.normpath(os.path.join(base_dir, path))


# -----------------------------------------------------------------------------
# 加载逻辑
# -----------------------------------------------------------------------------

def _candidate_paths() -> List[str]:
    return [_DEFAULT_CONFIG_PATH]


def _resolve_config_path() -> Optional[str]:
    for p in _candidate_paths():
        if p and os.path.isfile(p):
            return p
    return None


def _merge_section(target_obj, data: Dict[str, Any]) -> None:
    """把 dict 中的字段合并到 dataclass 实例（仅覆盖已存在字段）。"""
    if not isinstance(data, dict):
        return
    for key, value in data.items():
        if hasattr(target_obj, key):
            setattr(target_obj, key, value)


def _parse_models(raw_models: Any) -> List[ModelSpecConfig]:
    """解析 models 列表，忽略非法项。"""
    result: List[ModelSpecConfig] = []
    if not isinstance(raw_models, list):
        return result

    for item in raw_models:
        if not isinstance(item, dict):
            continue
        m = ModelSpecConfig()
        _merge_section(m, item)
        if not m.name:
            # 未指定 name 时回退为 model，确保可引用。
            m.name = m.model
        result.append(m)
    return result


def _parse_model_providers(raw_providers: Any) -> List[ModelProviderConfig]:
    """解析 model_providers 列表，忽略非法项。"""
    result: List[ModelProviderConfig] = []
    if not isinstance(raw_providers, list):
        return result

    for item in raw_providers:
        if not isinstance(item, dict):
            continue
        p = ModelProviderConfig()
        _merge_section(p, item)
        if not p.name:
            continue
        result.append(p)
    return result


def _expand_provider_models(providers: List[ModelProviderConfig]) -> List[ModelSpecConfig]:
    """把 provider 下的 models 展开为 ModelSpecConfig 列表。"""
    expanded: List[ModelSpecConfig] = []
    for p in providers:
        if not p.name:
            continue
        if not isinstance(p.models, list):
            continue
        for item in p.models:
            if not isinstance(item, dict):
                continue
            m = ModelSpecConfig(provider_name=p.name)
            _merge_section(m, item)
            if not m.name:
                m.name = m.model
            if m.name:
                expanded.append(m)
    return expanded


def load_config(path: Optional[str] = None) -> StoryForgeConfig:
    """
    加载配置。如果文件不存在或解析失败，返回默认配置（不抛异常）。

    Args:
        path: 兼容参数，未使用。配置始终从 ~/.storyforge/storyforge.yaml 读取。
    """
    cfg = StoryForgeConfig()

    target_path = _resolve_config_path()
    if not target_path:
        return cfg

    if yaml is None:
        # PyYAML 未安装，直接返回默认值
        return cfg

    try:
        with open(target_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return cfg

    if not isinstance(raw, dict):
        return cfg

    _merge_section(cfg.llm, raw.get("llm", {}))
    cfg.model_providers = _parse_model_providers(
        raw.get("model_providers", raw.get("providers", []))
    )
    top_level_models = _parse_models(raw.get("models", []))
    provider_models = _expand_provider_models(cfg.model_providers)

    # 合并规则：provider 下模型先入，顶层 models 同名可覆盖。
    merged: Dict[str, ModelSpecConfig] = {}
    for m in provider_models:
        merged[m.name] = m
    for m in top_level_models:
        merged[m.name] = m
    cfg.models = list(merged.values())
    _merge_section(cfg.model_routing, raw.get("model_routing", {}))
    _merge_section(cfg.storage, raw.get("storage", {}))
    _merge_section(cfg.server, raw.get("server", {}))
    _merge_section(cfg.security, raw.get("security", {}))
    _merge_section(cfg.pipeline, raw.get("pipeline", {}))
    _merge_section(cfg.console, raw.get("console", {}))
    _merge_section(cfg.debug, raw.get("debug", {}))

    cfg.config_path = target_path
    return cfg


# -----------------------------------------------------------------------------
# 全局单例
# -----------------------------------------------------------------------------

_cached: Optional[StoryForgeConfig] = None
_cached_mtime: Optional[float] = None


def _current_config_mtime() -> Optional[float]:
    """返回当前配置文件 mtime（不存在时返回 None）。"""
    path = _resolve_config_path()
    if not path:
        return None
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def get_config(reload: bool = False) -> StoryForgeConfig:
    """获取全局配置（带缓存，支持文件变更热加载）。"""
    global _cached, _cached_mtime

    current_mtime = _current_config_mtime()
    should_reload = reload or _cached is None or _cached_mtime != current_mtime

    if should_reload:
        new_cfg = load_config()

        # 安全策略：如果文件存在但解析失败（load_config 回退默认值且 config_path 为 None），
        # 保留上一次可用配置，避免临时编辑错误导致运行时配置被清空。
        if _cached is not None and current_mtime is not None and new_cfg.config_path is None:
            return _cached

        _cached = new_cfg
        _cached_mtime = current_mtime

    if _cached is None:
        _cached = StoryForgeConfig()
        _cached_mtime = current_mtime
    return _cached


def reset_config() -> None:
    """清空缓存（测试用）。"""
    global _cached, _cached_mtime
    _cached = None
    _cached_mtime = None
