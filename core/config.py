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


def get_config(reload: bool = False) -> StoryForgeConfig:
    """获取全局配置（带缓存）。"""
    global _cached
    if _cached is None or reload:
        _cached = load_config()
    return _cached


def reset_config() -> None:
    """清空缓存（测试用）。"""
    global _cached
    _cached = None
