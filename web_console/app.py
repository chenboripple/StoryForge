"""StoryForge 控制台 FastAPI 网关入口。

职责仅限三件事：
1. 实例化 FastAPI 应用，按领域聚合 router；
2. 启动后台任务调度器（恢复状态、起 dispatcher 线程）；
3. 把 client/build 的 React 产物挂到根路径（含 SPA fallback）。

业务实现在 web_console.services；运行期状态在 web_console.runtime；
路由按领域在 web_console.routes/*。
"""

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
    # 启动时
    cfg = get_config()
    storage_dir = Path(cfg.data_dir_abs)
    registry = TaskRegistry(storage_dir)

    # 注册默认的 pipeline runner
    def run_task(task_id: str):
        registry._run_task(task_id)

    registry.register_runner("pipeline", run_task)

    # 导入 ip services 来注册 ip runner
    try:
        import web_console.services.ip
    except ImportError:
        pass

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
        {"name": "legacy", "description": "旧版 API（向后兼容）"},
        {"name": "health", "description": "健康检查端点"},
        {"name": "novels", "description": "小说管理端点"},
        {"name": "tasks", "description": "任务管理端点"},
    ],
)

# 添加中间件
app.add_middleware(RequestIdMiddleware)

# CORS中间件配置
cfg = get_config()
if cfg.server.cors_origins:
    # 配置了具体的允许域名
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.server.cors_origins,
        allow_credentials=cfg.server.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    # 保持旧行为：允许所有（兼容现有部署）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 设置统一错误处理器
setup_error_handlers(app)

# 包含所有路由（版本化 + 向后兼容）
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
                "legacy": "/api",
            },
            "docs": "/docs",
        },
    )


@app.get("/api", include_in_schema=False)
async def api_index():
    """API 根路径，列出可用版本。"""
    return {
        "versions": {
            "v1": {
                "path": "/api/v1",
                "status": "active",
                "docs": "/api/v1/docs",
            },
            "legacy": {
                "path": "/api",
                "status": "deprecated",
            },
        },
        "docs": "/docs",
    }


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
            "tasks": "/api/v1/tasks",
            "templates": "/api/v1/templates",
            "ai": "/api/v1/ai",
            "import": "/api/v1/import",
            "ip": "/api/v1/ip",
            "video": "/api/v1/video",
        },
    }


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
