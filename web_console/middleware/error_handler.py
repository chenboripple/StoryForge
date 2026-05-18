"""
Error Handler Middleware
统一错误处理中间件，定义标准错误响应格式
"""
from typing import Any, Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from core.config import get_config


def _extract_request_id(request: Optional[Request]) -> Optional[str]:
    """从请求中提取 request_id（如果有）。"""
    if request is None:
        return None
    return getattr(request.state, "request_id", None)


class ErrorCode(str, Enum):
    """错误码枚举"""
    # 通用错误 (1xxx)
    UNKNOWN = "1000"
    VALIDATION_ERROR = "1001"
    UNAUTHORIZED = "1002"
    FORBIDDEN = "1003"
    NOT_FOUND = "1004"
    CONFLICT = "1005"

    # 存储相关 (2xxx)
    STORAGE_ERROR = "2000"
    FILE_NOT_FOUND = "2001"
    FILE_EXISTS = "2002"

    # 任务相关 (3xxx)
    TASK_ERROR = "3000"
    TASK_NOT_FOUND = "3001"
    TASK_ALREADY_RUNNING = "3002"

    # 小说相关 (4xxx)
    NOVEL_ERROR = "4000"
    NOVEL_NOT_FOUND = "4001"
    NOVEL_EXISTS = "4002"
    CHAPTER_NOT_FOUND = "4003"


@dataclass
class ErrorDetail:
    """错误详情"""
    field: Optional[str] = None
    message: str = ""
    code: Optional[str] = None


@dataclass
class ErrorResponse:
    """标准错误响应格式"""
    success: bool = False
    error_code: str = ErrorCode.UNKNOWN
    message: str = "An error occurred"
    details: List[ErrorDetail] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    request_id: Optional[str] = None
    path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "error_code": self.error_code,
            "message": self.message,
            "details": [
                {k: v for k, v in d.__dict__.items() if v is not None}
                for d in self.details
            ],
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "path": self.path,
        }


class StoryForgeError(Exception):
    """StoryForge 基础异常类"""
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = ErrorCode.UNKNOWN

    def __init__(
        self,
        message: str = "An error occurred",
        details: Optional[List[ErrorDetail]] = None,
    ):
        self.message = message
        self.details = details or []
        super().__init__(self.message)

    def to_response(self, request: Optional[Request] = None) -> ErrorResponse:
        """转换为错误响应"""
        return ErrorResponse(
            error_code=self.error_code,
            message=self.message,
            details=self.details,
            path=str(request.url.path) if request else None,
            request_id=_extract_request_id(request),
        )


class NotFoundError(StoryForgeError):
    """资源未找到错误"""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = ErrorCode.NOT_FOUND

    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ):
        details = []
        if resource_type or resource_id:
            details.append(
                ErrorDetail(
                    field=resource_type or "resource",
                    message=f"Resource not found: {resource_id or 'unknown'}",
                )
            )
        super().__init__(message, details)


class ValidationError(StoryForgeError):
    """验证错误"""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = ErrorCode.VALIDATION_ERROR

    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[List[ErrorDetail]] = None,
        field_errors: Optional[Dict[str, str]] = None,
    ):
        if field_errors and not details:
            details = [
                ErrorDetail(field=field, message=msg)
                for field, msg in field_errors.items()
            ]
        super().__init__(message, details)


class ConflictError(StoryForgeError):
    """冲突错误（资源已存在等）"""
    status_code = status.HTTP_409_CONFLICT
    error_code = ErrorCode.CONFLICT

    def __init__(
        self,
        message: str = "Resource conflict",
        details: Optional[List[ErrorDetail]] = None,
    ):
        super().__init__(message, details)


class InternalServerError(StoryForgeError):
    """服务器内部错误"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = ErrorCode.UNKNOWN


def setup_error_handlers(app: FastAPI) -> None:
    """为 FastAPI 应用设置统一错误处理器"""

    @app.exception_handler(StoryForgeError)
    async def storyforge_error_handler(request: Request, exc: StoryForgeError):
        """处理 StoryForge 自定义异常"""
        error_resp = exc.to_response(request)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_resp.to_dict(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        """处理 FastAPI 请求验证错误"""
        details = []
        for err in exc.errors():
            # 获取字段路径
            loc = err.get("loc", [])
            field = ".".join(str(x) for x in loc if x != "body")
            if not field:
                field = "body"

            details.append(ErrorDetail(
                field=field,
                message=err.get("msg", "Invalid value"),
                code=err.get("type"),
            ))

        error_resp = ErrorResponse(
            error_code=ErrorCode.VALIDATION_ERROR,
            message="Request validation failed",
            details=details,
            path=str(request.url.path),
            request_id=_extract_request_id(request),
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=error_resp.to_dict(),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """处理所有未捕获的异常"""
        cfg = get_config()
        details = []
        if cfg.server.debug:
            details.append(ErrorDetail(message=f"{exc.__class__.__name__}: {exc}"))

        error_resp = ErrorResponse(
            error_code=ErrorCode.UNKNOWN,
            message="An unexpected error occurred",
            details=details,
            path=str(request.url.path),
            request_id=_extract_request_id(request),
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_resp.to_dict(),
        )
