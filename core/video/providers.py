"""
Video provider 抽象层（不绑定具体厂商）
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Dict, List, Protocol


@dataclass
class ImageGenRequest:
    prompt: str
    identity_seed: str = ""
    reference_uris: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class ImageGenResult:
    uri: str
    provider: str
    metadata: Dict[str, str]


@dataclass
class VideoGenRequest:
    prompt: str
    reference_uris: List[str] = field(default_factory=list)
    duration_sec: float = 4.0
    fps: int = 24
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class VideoGenResult:
    uri: str
    provider: str
    duration_sec: float
    fps: int
    metadata: Dict[str, str]


class ImageProvider(Protocol):
    def generate(self, req: ImageGenRequest) -> ImageGenResult:
        ...


class VideoProvider(Protocol):
    def generate(self, req: VideoGenRequest) -> VideoGenResult:
        ...


class EmbeddingProvider(Protocol):
    def embed_image(self, image_uri: str) -> List[float]:
        ...


class StubImageProvider:
    """占位 provider，后续可替换为真实服务。"""

    def generate(self, req: ImageGenRequest) -> ImageGenResult:
        digest = hashlib.sha256(req.prompt.encode("utf-8")).hexdigest()[:16]
        return ImageGenResult(
            uri=f"stub://image/{digest}",
            provider="stub-image",
            metadata=req.metadata or {},
        )


class StubVideoProvider:
    """占位 provider，后续可替换为真实服务。"""

    def generate(self, req: VideoGenRequest) -> VideoGenResult:
        digest = hashlib.sha256(req.prompt.encode("utf-8")).hexdigest()[:16]
        return VideoGenResult(
            uri=f"stub://video/{digest}",
            provider="stub-video",
            duration_sec=req.duration_sec,
            fps=req.fps,
            metadata=req.metadata or {},
        )


class StubEmbeddingProvider:
    """占位 embedding provider。"""

    def embed_image(self, image_uri: str) -> List[float]:
        # 简化：返回固定维度伪向量
        digest = hashlib.sha256(image_uri.encode("utf-8")).hexdigest()
        base = int(digest[:8], 16) % 1000
        return [(base + i) / 1000.0 for i in range(16)]
