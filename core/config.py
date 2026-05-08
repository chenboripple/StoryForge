"""
StoryForge - 配置加载

配置文件位置（按优先级）：
  1. $STORYFORGE_CONFIG 指定的路径
  2. ~/.storyforge/storyforge.yaml               （用户级，推荐）
  3. <project_root>/.storyforge/storyforge.yaml  （项目级）
  4. 内置默认值

配置项包括：大模型、存储位置、服务器端口、Pipeline 行为等。
不依赖系统环境变量。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, Any, Dict

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None


_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ==================== 数据结构 ====================

@dataclass
class LLMConfig:
    provider: str = "mock"           # mock | openai | anthropic
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = ""               # 自定义 endpoint（例如代理或私有部署）
    temperature: float = 0.7
    timeout: int = 60
    extra: Dict[str, Any] = field(default_factory=dict)  # 透传 SDK 额外参数


@dataclass
class StorageConfig:
    data_dir: str = "~/.storyforge/data"  # 相对路径相对于配置文件目录解析


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 5089
    cors_origins: str = "*"


@dataclass
class PipelineConfig:
    max_review_rounds: int = 3
    default_target_word_count: int = 3000


@dataclass
class ConsoleConfig:
    max_running_tasks: int = 3
    default_command: str = "python examples/demo_pipeline.py"
    template_file: str = "~/.storyforge/templates.json"

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
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    console: ConsoleConfig = field(default_factory=ConsoleConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)
    config_path: Optional[str] = None     # 加载来源（None 表示使用默认值）

    @property
    def data_dir_abs(self) -> str:
        """返回绝对路径的 data_dir。

        路径解析规则：
        - 绝对路径：直接使用
        - ~/ 开头：相对于用户主目录展开
        - 相对路径：相对于配置文件所在目录解析；若无配置文件则相对于当前工作目录
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


# ==================== 加载逻辑 ====================

def _candidate_paths() -> list[str]:
    paths = []
    env_path = os.environ.get("STORYFORGE_CONFIG")
    if env_path:
        paths.append(env_path)
    paths.append(os.path.join(os.path.expanduser("~"), ".storyforge", "storyforge.yaml"))
    paths.append(os.path.join(_PROJECT_ROOT, ".storyforge", "storyforge.yaml"))
    return paths


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
        path: 显式指定的配置文件路径。如果为 None，按候选路径查找。
    """
    cfg = StoryForgeConfig()

    target_path = path or _resolve_config_path()
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
    _merge_section(cfg.pipeline, raw.get("pipeline", {}))
    _merge_section(cfg.console, raw.get("console", {}))
    _merge_section(cfg.debug, raw.get("debug", {}))

    cfg.config_path = target_path
    return cfg


# ==================== 全局单例 ====================

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
