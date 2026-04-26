"""StoryForge 统一配置入口。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_int(name: str, default: int, minimum: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        value = default
    else:
        try:
            value = int(raw)
        except ValueError:
            value = default
    if minimum is not None:
        value = max(minimum, value)
    return value


def _env_path(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    if not raw:
        return default
    return Path(raw).expanduser().resolve()


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
    console: ConsoleSettings
    debug: DebugSettings
    pipeline: PipelineSettings


@lru_cache(maxsize=1)
def get_settings() -> StoryForgeSettings:
    console = ConsoleSettings(
        max_running_tasks=_env_int("STORYFORGE_MAX_RUNNING_TASKS", 2, minimum=1),
        default_command=os.getenv("STORYFORGE_DEFAULT_COMMAND", "python3 examples/debug_pipeline.py"),
        template_file=_env_path(
            "STORYFORGE_TEMPLATE_FILE",
            PROJECT_ROOT / "web_console" / "templates.json",
        ),
    )

    debug = DebugSettings(
        output_dir=_env_path("STORYFORGE_DEBUG_DIR", PROJECT_ROOT / "debug_output"),
    )

    pipeline = PipelineSettings(
        default_target_word_count=_env_int("STORYFORGE_DEFAULT_TARGET_WORD_COUNT", 3000, minimum=500),
    )

    return StoryForgeSettings(
        project_root=PROJECT_ROOT,
        console=console,
        debug=debug,
        pipeline=pipeline,
    )
