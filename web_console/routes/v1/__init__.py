"""
API v1 Routes - 版本化的 API 路由
所有 v1 端点都挂载在 /api/v1 前缀下
"""
from __future__ import annotations

from fastapi import APIRouter

from web_console.routes.v1 import (
    health,
    ai,
    templates,
    tasks,
    novels,
    progressive,
    import_,
    ip,
    video,
)

# v1 API 路由聚合
v1_router = APIRouter(prefix="/api/v1", tags=["v1"])

v1_router.include_router(health.router)
v1_router.include_router(ai.router)
v1_router.include_router(templates.router)
v1_router.include_router(tasks.router)
v1_router.include_router(novels.router)
v1_router.include_router(progressive.router)
v1_router.include_router(import_.router)
v1_router.include_router(ip.router)
v1_router.include_router(video.router)
