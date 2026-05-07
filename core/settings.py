"""StoryForge 统一配置入口。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
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


def _resolve_value(env_name: str, config: dict[str, Any], config_path: str) -> tuple[Any, str]:
    env_value = os.getenv(env_name)
    if env_value is not None and str(env_value).strip() != "":
        return env_value, f"env:{env_name}"

    config_value = _config_get(config, config_path)
    if config_value is not None and str(config_value).strip() != "":
        return config_value, f"file:{USER_CONFIG_FILE}#{config_path}"

    raise RuntimeError(
        f"缺少必填配置: {config_path} (env: {env_name}). "
        f"请在 {USER_CONFIG_FILE} 或环境变量中设置。"
    )


def _required_int(
    env_name: str,
    config: dict[str, Any],
    config_path: str,
    minimum: int | None = None,
) -> tuple[int, str]:
    raw, source = _resolve_value(env_name, config, config_path)
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"配置必须是整数: {config_path}，当前值: {raw}") from exc

    if minimum is not None and value < minimum:
        raise RuntimeError(f"配置必须 >= {minimum}: {config_path}，当前值: {value}")
    return value, source


def _required_str(env_name: str, config: dict[str, Any], config_path: str) -> tuple[str, str]:
    raw, source = _resolve_value(env_name, config, config_path)
    value = str(raw).strip()
    if not value:
        raise RuntimeError(f"配置不能为空: {config_path}")
    return value, source


def _required_path(env_name: str, config: dict[str, Any], config_path: str) -> tuple[Path, str]:
    raw, source = _required_str(env_name, config, config_path)
    return Path(raw).expanduser().resolve(), source


def _build_settings() -> tuple[StoryForgeSettings, dict[str, str]]:
    user_config = _load_user_config()
    sources: dict[str, str] = {}

    console_max_running_tasks, sources["console.max_running_tasks"] = _required_int(
        "STORYFORGE_MAX_RUNNING_TASKS",
        user_config,
        "console.max_running_tasks",
        minimum=1,
    )
    console_default_command, sources["console.default_command"] = _required_str(
        "STORYFORGE_DEFAULT_COMMAND",
        user_config,
        "console.default_command",
    )
    console_template_file, sources["console.template_file"] = _required_path(
        "STORYFORGE_TEMPLATE_FILE",
        user_config,
        "console.template_file",
    )

    debug_output_dir, sources["debug.output_dir"] = _required_path(
        "STORYFORGE_DEBUG_DIR",
        user_config,
        "debug.output_dir",
    )

    pipeline_target_word_count, sources["pipeline.default_target_word_count"] = _required_int(
        "STORYFORGE_DEFAULT_TARGET_WORD_COUNT",
        user_config,
        "pipeline.default_target_word_count",
        minimum=500,
    )

    settings = StoryForgeSettings(
        project_root=PROJECT_ROOT,
        config_file=USER_CONFIG_FILE,
        console=ConsoleSettings(
            max_running_tasks=console_max_running_tasks,
            default_command=console_default_command,
            template_file=console_template_file,
        ),
        debug=DebugSettings(output_dir=debug_output_dir),
        pipeline=PipelineSettings(default_target_word_count=pipeline_target_word_count),
    )
    return settings, sources


@lru_cache(maxsize=1)
def get_settings() -> StoryForgeSettings:
    settings, _ = _build_settings()
    return settings


def get_settings_with_sources() -> tuple[StoryForgeSettings, dict[str, str]]:
    return _build_settings()


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="StoryForge 配置诊断")
    parser.add_argument("--check", action="store_true", help="仅校验配置是否完整有效，成功返回 0")
    args = parser.parse_args()

    try:
        settings, sources = get_settings_with_sources()
    except Exception as exc:
        print(f"CONFIG_INVALID: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if args.check:
        print("CONFIG_OK")
        return

    payload = {
        "settings": asdict(settings),
        "sources": sources,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
