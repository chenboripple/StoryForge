"""路由聚合：统一只暴露 v1 API。"""

from __future__ import annotations

from fastapi import APIRouter

# 版本化的 API 路由
from web_console.routes.v1 import v1_router

# 主 API 路由器 - 包含所有版本
api_router = APIRouter()

# 仅包含 v1 API
api_router.include_router(v1_router)
