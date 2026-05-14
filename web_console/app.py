"""StoryForge 控制台 FastAPI 网关入口（v1-only）。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from core.config import get_config
from web_console.middleware import RequestIdMiddleware, setup_error_handlers
from web_console.routes import api_router
from web_console.runtime.registry import TaskRegistry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理：启动时初始化，关闭时清理。"""
    cfg = get_config()
    storage_dir = Path(cfg.data_dir_abs)
    registry = TaskRegistry(storage_dir)

    def run_task(task_id: str):
        registry._run_task(task_id)

    registry.register_runner("pipeline", run_task)

    # 注册 ip runner
    from web_console.services.ip import register_ip_runner
    register_ip_runner(registry)

    registry.load_state()
    registry.start_dispatcher()
    app.state.task_registry = registry

    yield  # 应用运行

    # 关闭时
    await app.state.task_registry.shutdown()


# 创建 FastAPI 应用
app = FastAPI(
    title="StoryForge Console",
    description="StoryForge 多 Agent 小说创作平台 API",
    version="0.3.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "v1", "description": "API v1 版本端点"},
        {"name": "health", "description": "健康检查端点"},
        {"name": "novels", "description": "小说管理端点"},
        {"name": "tasks", "description": "任务管理端点"},
    ],
)

# 添加中间件
app.add_middleware(RequestIdMiddleware)

# CORS中间件配置
cfg = get_config()
cors_origins_cfg = cfg.server.cors_origins
if isinstance(cors_origins_cfg, str):
    # 兼容历史配置写法，避免将 "*" 误当作 list 使用。
    if cors_origins_cfg.strip() == "*":
        cors_origins = ["*"]
    else:
        cors_origins = [x.strip() for x in cors_origins_cfg.split(",") if x.strip()]
elif isinstance(cors_origins_cfg, list):
    cors_origins = cors_origins_cfg
else:
    cors_origins = []

if cors_origins:
    # 配置了允许域名
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cfg.server.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # 未配置时使用最小默认值（仅本地前端常见地址）。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=cfg.server.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 设置统一错误处理器
setup_error_handlers(app)

# 仅包含 v1 路由
app.include_router(api_router)

# 前端静态文件托管
_CLIENT_BUILD = (Path(__file__).resolve().parent.parent / "client" / "build")
_CLIENT_INDEX = _CLIENT_BUILD / "index.html"


@app.get("/", include_in_schema=False)
async def root():
    if _CLIENT_INDEX.exists():
        return FileResponse(_CLIENT_INDEX, media_type="text/html")
    return JSONResponse(
        status_code=404,
        content={
            "error": "前端构建产物不存在",
            "hint": "请先在 client/ 下执行 `npm install && npm run build`",
            "expected_path": str(_CLIENT_INDEX),
            "api_versions": {
                "v1": "/api/v1",
            },
            "docs": "/docs",
        },
    )


@app.get("/api", include_in_schema=False)
async def api_index():
    """v1-only 模式下，/api 不再作为兼容入口。"""
    return JSONResponse(
        status_code=410,
        content={
            "error": "gone",
            "message": "legacy API prefix removed; use /api/v1",
            "docs": "/docs",
        },
    )


@app.get("/api/v1", include_in_schema=False)
async def api_v1_index():
    """v1 API 根路径。"""
    return {
        "version": "v1",
        "status": "active",
        "endpoints": {
            "health": "/api/v1/health",
            "config": "/api/v1/config",
            "novels": "/api/v1/novels",
            "progressive": "/api/v1/novels/{novel_id}/proposals",
            "tasks": "/api/v1/tasks",
            "templates": "/api/v1/templates",
            "ai": "/api/v1/ai",
            "import": "/api/v1/import",
            "ip": "/api/v1/ip",
            "video": "/api/v1/video",
        },
    }


@app.api_route(
    "/api/{legacy_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def legacy_api_gone(legacy_path: str):
    # /api/v1/* 交给已注册 v1 路由处理；这里只拦截历史路径并明确返回 410。
    if legacy_path == "v1" or legacy_path.startswith("v1/"):
        return JSONResponse(status_code=404, content={"error": "not found"})
    return JSONResponse(
        status_code=410,
        content={
            "error": "gone",
            "message": "legacy API path removed; use /api/v1/*",
            "requested_path": f"/api/{legacy_path}",
        },
    )


if _CLIENT_BUILD.exists():
    # 优先挂 /static 目录（CRA 构建产物里的 hashed 资源），避免和 / 上的 SPA fallback 冲突。
    _STATIC_DIR = _CLIENT_BUILD / "static"
    if _STATIC_DIR.exists():
        from fastapi.staticfiles import StaticFiles
        app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str, request: Request):
        # API 路径不走 SPA fallback，让 router 自己 404。
        if full_path.startswith("api/") or full_path == "api":
            return JSONResponse(status_code=404, content={"error": "not found"})

        # 真实存在的静态文件（manifest、favicon、robots 等）直接服务。
        candidate = _CLIENT_BUILD / full_path
        if candidate.is_file():
            return FileResponse(candidate)

        # 其余 GET 请求统一回 index.html，交给 React Router 处理。
        if _CLIENT_INDEX.exists():
            return FileResponse(_CLIENT_INDEX, media_type="text/html")
        return JSONResponse(status_code=404, content={"error": "not found"})
