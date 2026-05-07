"""
StoryForge - LLM 客户端工厂

根据 LLMConfig 创建符合 (prompt: str, temperature: float = None) -> str 签名的可调用对象。

支持的 provider:
  - mock     : 内置占位响应，无需 API key
  - openai   : OpenAI 兼容协议（需 pip install openai）
  - anthropic: Anthropic Claude（需 pip install anthropic）
"""

from __future__ import annotations

from typing import Callable, Optional

from core.config import LLMConfig, get_config


def _build_mock_client(_cfg: LLMConfig) -> Callable:
    """Mock LLM 客户端：根据 prompt 关键字返回占位文本。"""
    def mock(prompt: str, temperature: Optional[float] = None) -> str:
        if "创作" in prompt or "写作" in prompt:
            return "（mock 章节内容）这是一段由占位 LLM 生成的章节内容。"
        if "审稿" in prompt:
            return "【总体评分】85分\n\n【是否通过】通过"
        if "校对" in prompt:
            return "【总体评价】通过"
        if "修改" in prompt:
            return "（mock 修改后内容）"
        return "收到任务，处理完成。"
    return mock


def _build_openai_client(cfg: LLMConfig) -> Callable:
    """OpenAI 兼容协议客户端。"""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "使用 openai provider 需要先安装：pip install openai"
        ) from e

    kwargs = {}
    if cfg.api_key:
        kwargs["api_key"] = cfg.api_key
    if cfg.base_url:
        kwargs["base_url"] = cfg.base_url
    if cfg.timeout:
        kwargs["timeout"] = cfg.timeout

    client = OpenAI(**kwargs)

    def call(prompt: str, temperature: Optional[float] = None) -> str:
        temp = temperature if temperature is not None else cfg.temperature
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temp,
            **cfg.extra,
        )
        return resp.choices[0].message.content or ""

    return call


def _build_anthropic_client(cfg: LLMConfig) -> Callable:
    """Anthropic Claude 客户端。"""
    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "使用 anthropic provider 需要先安装：pip install anthropic"
        ) from e

    kwargs = {}
    if cfg.api_key:
        kwargs["api_key"] = cfg.api_key
    if cfg.base_url:
        kwargs["base_url"] = cfg.base_url
    if cfg.timeout:
        kwargs["timeout"] = cfg.timeout

    client = Anthropic(**kwargs)

    def call(prompt: str, temperature: Optional[float] = None) -> str:
        temp = temperature if temperature is not None else cfg.temperature
        max_tokens = cfg.extra.get("max_tokens", 4096)
        resp = client.messages.create(
            model=cfg.model,
            max_tokens=max_tokens,
            temperature=temp,
            messages=[{"role": "user", "content": prompt}],
        )
        # Anthropic 返回 list[ContentBlock]
        return "".join(
            getattr(block, "text", "") for block in resp.content
        )

    return call


_BUILDERS = {
    "mock": _build_mock_client,
    "openai": _build_openai_client,
    "anthropic": _build_anthropic_client,
}


def create_llm_client(cfg: Optional[LLMConfig] = None) -> Callable:
    """
    根据配置创建 LLM 客户端（callable）。

    Args:
        cfg: LLMConfig；若为 None，使用全局配置

    Returns:
        callable(prompt: str, temperature: Optional[float] = None) -> str
    """
    if cfg is None:
        cfg = get_config().llm

    provider = (cfg.provider or "mock").lower()
    builder = _BUILDERS.get(provider)
    if builder is None:
        raise ValueError(
            f"不支持的 LLM provider: {provider!r}（可用: {list(_BUILDERS)}）"
        )
    return builder(cfg)
