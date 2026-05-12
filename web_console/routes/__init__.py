"""路由聚合：把按领域拆分的 APIRouter 汇总成单个 router。

app.py 只需 `from web_console.routes import api_router` 然后
`app.include_router(api_router)` 即可。

同时支持版本化的 API (v1) 和旧版 API（向后兼容）。
"""

from __future__ import annotations

from fastapi import APIRouter

# 版本化的 API 路由
from web_console.routes.v1 import v1_router

# 旧版路由（保持向后兼容）
from web_console.routes import (
    ai,
    health,
    import_,
    ip,
    novels,
    tasks,
    templates,
    video,
)

# 主 API 路由器 - 包含所有版本
api_router = APIRouter()

# 包含 v1 版本的 API
api_router.include_router(v1_router)

# 旧版 API（向后兼容）- 仍然在 /api/ 下可用
legacy_router = APIRouter(prefix="/api", tags=["legacy"])
legacy_router.include_router(health.router)
legacy_router.include_router(ai.router)
legacy_router.include_router(templates.router)
legacy_router.include_router(tasks.router)
legacy_router.include_router(novels.router)
legacy_router.include_router(import_.router)
legacy_router.include_router(ip.router)
legacy_router.include_router(video.router)
api_router.include_router(legacy_router)
