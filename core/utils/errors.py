"""
StoryForge - 错误处理与重试机制
"""

import traceback
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from functools import wraps


@dataclass
class AgentError:
    """Agent 错误记录"""
    agent_name: str
    error_type: str
    error_message: str
    traceback: str
    state_snapshot: dict = field(default_factory=dict)
    recoverable: bool = False  # 是否可恢复


class ErrorHandler:
    """
    错误处理器
    
    职责：
    1. 捕获 Agent 异常
    2. 记录错误上下文
    3. 尝试恢复或回滚
    """
    
    def __init__(self):
        self.errors: list = []
        self.max_retries: int = 2
    
    def handle(self, agent_name: str, state: Any, error: Exception) -> Any:
        """
        处理错误，返回修复后的状态或抛出
        """
        error_record = AgentError(
            agent_name=agent_name,
            error_type=type(error).__name__,
            error_message=str(error),
            traceback=traceback.format_exc(),
            state_snapshot=self._snapshot_state(state),
            recoverable=self._is_recoverable(error)
        )
        self.errors.append(error_record)
        
        print(f"❌ [{agent_name}] 错误: {error_record.error_message}")
        
        if error_record.recoverable:
            # 尝试修复状态
            return self._recover_state(state, error_record)
        else:
            # 不可恢复，标记错误
            state.error_message = f"[{agent_name}] {error_record.error_message}"
            return state
    
    def _snapshot_state(self, state: Any) -> dict:
        """创建状态快照"""
        try:
            return {
                "current_chapter": getattr(state, 'current_chapter', None),
                "stage": getattr(state, 'current_stage', None),
                "chapter_status": dict(getattr(state, 'chapter_status', {})),
            }
        except:
            return {}
    
    def _is_recoverable(self, error: Exception) -> bool:
        """判断错误是否可恢复"""
        recoverable_types = [
            'TimeoutError',
            'ConnectionError',
            'RateLimitError',
        ]
        return type(error).__name__ in recoverable_types
    
    def _recover_state(self, state: Any, error: AgentError) -> Any:
        """尝试恢复状态"""
        # 可恢复错误：通常只需重试
        # 这里可以添加指数退避等逻辑
        return state


def with_error_handler(handler: ErrorHandler):
    """装饰器：为 Agent.invoke 添加错误处理"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, state: Any) -> Any:
            agent_name = getattr(self, 'persona', None)
            agent_name = agent_name.name if agent_name else func.__name__
            
            try:
                return func(self, state)
            except Exception as e:
                return handler.handle(agent_name, state, e)
        return wrapper
    return decorator


class RetryWithBackoff:
    """带退避的重试器"""
    
    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数，带重试"""
        import time
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt)  # 指数退避
                    print(f"⚠️ 第{attempt + 1}次失败，{delay}秒后重试...")
                    time.sleep(delay)
        
        raise last_error
