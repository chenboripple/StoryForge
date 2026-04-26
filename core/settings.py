"""StoryForge 统一配置入口。"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
USER_CONFIG_FILE = Path.home() / ".storyforge" / "config.json"


def _load_user_config() -> dict[str, Any]:
    if not USER_CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _config_get(config: dict[str, Any], path: str, default: Any) -> Any:
    current: Any = config
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _env_or_config_int(
    env_name: str,
    config: dict[str, Any],
    config_path: str,
    default: int,
    minimum: int | None = None,
) -> int:
    raw = os.getenv(env_name)
    if raw is not None:
        try:
            value = int(raw)
        except ValueError:
            value = default
    else:
        cfg_value = _config_get(config, config_path, default)
        try:
            value = int(cfg_value)
        except (TypeError, ValueError):
            value = default

    if minimum is not None:
        value = max(minimum, value)
    return value


def _env_or_config_str(
    env_name: str,
    config: dict[str, Any],
    config_path: str,
    default: str,
) -> str:
    raw = os.getenv(env_name)
    if raw:
        return raw
    value = _config_get(config, config_path, default)
    return str(value) if value is not None else default


def _env_or_config_path(
    env_name: str,
    config: dict[str, Any],
    config_path: str,
    default: Path,
) -> Path:
    raw = os.getenv(env_name)
    if raw:
        return Path(raw).expanduser().resolve()

    value = _config_get(config, config_path, None)
    if value is None:
        return default

    try:
        return Path(str(value)).expanduser().resolve()
    except Exception:
        return default


@dataclass(frozen=True)
class ConsoleSettings:
    max_running_tasks: int
    default_command: str
    template_file: Path


@dataclass(frozen=True)
class DebugSettings:
    output_dir: Path


@dataclass(frozen=True)
class PipelineSettings:
    default_target_word_count: int


@dataclass(frozen=True)
class StoryForgeSettings:
    project_root: Path
    config_file: Path
    console: ConsoleSettings
    debug: DebugSettings
    pipeline: PipelineSettings


@lru_cache(maxsize=1)
def get_settings() -> StoryForgeSettings:
    user_config = _load_user_config()

    console = ConsoleSettings(
        max_running_tasks=_env_or_config_int(
            "STORYFORGE_MAX_RUNNING_TASKS",
            user_config,
            "console.max_running_tasks",
            2,
            minimum=1,
        ),
        default_command=_env_or_config_str(
            "STORYFORGE_DEFAULT_COMMAND",
            user_config,
            "console.default_command",
            "python3 examples/debug_pipeline.py",
        ),
        template_file=_env_or_config_path(
            "STORYFORGE_TEMPLATE_FILE",
            user_config,
            "console.template_file",
            PROJECT_ROOT / "web_console" / "templates.json",
        ),
    )

    debug = DebugSettings(
        output_dir=_env_or_config_path(
            "STORYFORGE_DEBUG_DIR",
            user_config,
            "debug.output_dir",
            PROJECT_ROOT / "debug_output",
        ),
    )

    pipeline = PipelineSettings(
        default_target_word_count=_env_or_config_int(
            "STORYFORGE_DEFAULT_TARGET_WORD_COUNT",
            user_config,
            "pipeline.default_target_word_count",
            3000,
            minimum=500,
        ),
    )

    return StoryForgeSettings(
        project_root=PROJECT_ROOT,
        config_file=USER_CONFIG_FILE,
        console=console,
        debug=debug,
        pipeline=pipeline,
    )
