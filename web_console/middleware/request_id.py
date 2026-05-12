"""请求ID中间件 - 为每个请求生成唯一ID，便于追踪。"""

from __future__ import annotations

import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class RequestIdMiddleware(BaseHTTPMiddleware):
    """请求ID中间件，为每个请求生成/传递唯一ID。"""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 从请求头获取或生成新的请求ID
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id

        # 处理请求
        response: Response = await call_next(request)

        # 将请求ID添加到响应头
        response.headers["X-Request-ID"] = request_id
        return response


def get_request_id(request: Request) -> str:
    """从请求中获取请求ID（作为依赖项使用）。"""
    return getattr(request.state, "request_id", "")
