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


def _load_user_config() -> dict[str, Any]:
    if not USER_CONFIG_FILE.exists():
        return {}
    try:
        data = json.loads(USER_CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _config_get(config: dict[str, Any], path: str) -> Any:
    current: Any = config
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _required_value(env_name: str, config: dict[str, Any], config_path: str) -> Any:
    env_value = os.getenv(env_name)
    if env_value is not None and str(env_value).strip() != "":
        return env_value

    config_value = _config_get(config, config_path)
    if config_value is not None and str(config_value).strip() != "":
        return config_value

    raise RuntimeError(
        f"缺少必填配置: {config_path} (env: {env_name}). "
        f"请在 {USER_CONFIG_FILE} 或环境变量中设置。"
    )


def _required_int(
    env_name: str,
    config: dict[str, Any],
    config_path: str,
    minimum: int | None = None,
) -> int:
    raw = _required_value(env_name, config, config_path)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"配置必须是整数: {config_path}，当前值: {raw}") from exc

    if minimum is not None and value < minimum:
        raise RuntimeError(f"配置必须 >= {minimum}: {config_path}，当前值: {value}")
    return value


def _required_str(env_name: str, config: dict[str, Any], config_path: str) -> str:
    raw = _required_value(env_name, config, config_path)
    value = str(raw).strip()
    if not value:
        raise RuntimeError(f"配置不能为空: {config_path}")
    return value


def _required_path(env_name: str, config: dict[str, Any], config_path: str) -> Path:
    raw = _required_str(env_name, config, config_path)
    return Path(raw).expanduser().resolve()


@lru_cache(maxsize=1)
def get_settings() -> StoryForgeSettings:
    user_config = _load_user_config()

    console = ConsoleSettings(
        max_running_tasks=_required_int(
            "STORYFORGE_MAX_RUNNING_TASKS",
            user_config,
            "console.max_running_tasks",
            minimum=1,
        ),
        default_command=_required_str(
            "STORYFORGE_DEFAULT_COMMAND",
            user_config,
            "console.default_command",
        ),
        template_file=_required_path(
            "STORYFORGE_TEMPLATE_FILE",
            user_config,
            "console.template_file",
        ),
    )

    debug = DebugSettings(
        output_dir=_required_path(
            "STORYFORGE_DEBUG_DIR",
            user_config,
            "debug.output_dir",
        ),
    )

    pipeline = PipelineSettings(
        default_target_word_count=_required_int(
            "STORYFORGE_DEFAULT_TARGET_WORD_COUNT",
            user_config,
            "pipeline.default_target_word_count",
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
