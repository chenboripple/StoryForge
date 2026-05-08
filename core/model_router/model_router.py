"""
StoryForge - 模型路由层

职责：
1. 根据任务类型自动选择最合适的模型
2. 支持模型故障自动切换
3. 统一管理多个 LLM Provider
4. 支持流式输出和 Token 控制
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Iterator
from enum import Enum
import time
import json


class TaskType(Enum):
    """任务类型"""
    WRITING = "writing"           # 写作（需要创意）
    REVIEW = "review"             # 审稿（需要分析能力）
    PROOFREAD = "proofread"       # 校对（需要精确）
    IP_GENERATION = "ip_generation"  # IP生成（需要结构化）
    OUTLINE = "outline"           # 大纲生成（需要规划能力）
    EXTRACTION = "extraction"     # 知识萃取（需要理解能力）
    GENERAL = "general"           # 通用任务


class ModelProvider(Enum):
    """模型提供商"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    LOCAL = "local"
    CUSTOM = "custom"


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    provider: ModelProvider
    model_id: str  # 实际的模型 ID（如 gpt-4, claude-3-opus）
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    timeout: int = 60
    retry_count: int = 3
    retry_delay: float = 1.0
    # 任务偏好（该模型擅长的任务类型，权重越高越优先）
    task_preferences: Dict[TaskType, float] = field(default_factory=dict)
    # 成本估算（每 1K tokens）
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    # 是否启用
    enabled: bool = True
    # 失败次数（自动统计）
    _failure_count: int = 0
    # 最后失败时间
    _last_failure: Optional[float] = None


@dataclass
class RoutingResult:
    """路由结果"""
    model_name: str
    model_config: ModelConfig
    task_type: TaskType
    fallback_chain: List[str] = field(default_factory=list)


class ModelRouter:
    """
    模型路由器

    使用示例：
    ```python
    router = ModelRouter()
    
    # 注册模型
    router.register_model(ModelConfig(
        name="gpt-4",
        provider=ModelProvider.OPENAI,
        model_id="gpt-4",
        task_preferences={
            TaskType.WRITING: 0.9,
            TaskType.OUTLINE: 0.8
        }
    ))
    
    # 获取模型
    result = router.route(TaskType.WRITING)
    model = router.get_client(result.model_name)
    
    # 调用
    response = model("prompt", temperature=0.7)
    ```
    """

    # 默认任务-模型映射
    DEFAULT_TASK_MAPPING: Dict[TaskType, List[str]] = {
        TaskType.WRITING: ["gpt-4", "claude-3-opus", "gpt-3.5-turbo"],
        TaskType.REVIEW: ["claude-3-opus", "gpt-4", "claude-3-sonnet"],
        TaskType.PROOFREAD: ["gpt-4", "claude-3-sonnet", "gpt-3.5-turbo"],
        TaskType.IP_GENERATION: ["claude-3-opus", "gpt-4", "gpt-3.5-turbo"],
        TaskType.OUTLINE: ["gpt-4", "claude-3-opus", "gpt-3.5-turbo"],
        TaskType.EXTRACTION: ["gpt-4", "claude-3-sonnet", "gpt-3.5-turbo"],
        TaskType.GENERAL: ["gpt-3.5-turbo", "claude-3-sonnet"]
    }

    def __init__(self, config_path: Optional[str] = None):
        self.models: Dict[str, ModelConfig] = {}
        self.clients: Dict[str, Callable] = {}
        self.task_mapping: Dict[TaskType, List[str]] = self.DEFAULT_TASK_MAPPING.copy()
        self._load_config(config_path)
    
    def register_model(
        self,
        config: ModelConfig,
        client: Optional[Callable] = None
    ):
        """
        注册模型
        
        Args:
            config: 模型配置
            client: 模型客户端（如果为 None，会自动创建）
        """
        self.models[config.name] = config
        
        if client:
            self.clients[config.name] = client
        else:
            self.clients[config.name] = self._create_client(config)
        
        print(f"✅ 注册模型: {config.name} ({config.model_id})")
    
    def route(self, task_type: TaskType, preferred_model: Optional[str] = None) -> RoutingResult:
        """
        为任务选择最合适的模型
        
        Args:
            task_type: 任务类型
            preferred_model: 优先使用的模型（如果可用）
        
        Returns:
            RoutingResult: 包含选中的模型和备用链
        """
        # 1. 如果指定了优先模型且可用，直接使用
        if preferred_model and preferred_model in self.models:
            config = self.models[preferred_model]
            if config.enabled and self._is_model_healthy(config):
                return RoutingResult(
                    model_name=preferred_model,
                    model_config=config,
                    task_type=task_type,
                    fallback_chain=self._build_fallback_chain(task_type, exclude=[preferred_model])
                )
        
        # 2. 根据任务类型选择模型
        candidates = self.task_mapping.get(task_type, [])
        
        # 3. 评分排序
        scored_models = []
        for model_name in candidates:
            if model_name not in self.models:
                continue
            
            config = self.models[model_name]
            if not config.enabled:
                continue
            
            if not self._is_model_healthy(config):
                continue
            
            # 计算分数
            score = self._calculate_score(config, task_type)
            scored_models.append((model_name, score))
        
        # 4. 按分数排序
        scored_models.sort(key=lambda x: x[1], reverse=True)
        
        if not scored_models:
            raise RuntimeError(f"没有可用的模型用于任务: {task_type.value}")
        
        # 5. 返回最佳模型
        best_model = scored_models[0][0]
        fallback_chain = [name for name, _ in scored_models[1:]]
        
        return RoutingResult(
            model_name=best_model,
            model_config=self.models[best_model],
            task_type=task_type,
            fallback_chain=fallback_chain
        )
    
    def call(
        self,
        task_type: TaskType,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        preferred_model: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        调用模型（自动路由 + 故障切换）
        
        Args:
            task_type: 任务类型
            prompt: 提示词
            temperature: 温度（覆盖默认值）
            max_tokens: 最大 Token（覆盖默认值）
            preferred_model: 优先使用的模型
            **kwargs: 其他参数
        
        Returns:
            str: 模型输出
        """
        # 路由
        result = self.route(task_type, preferred_model)
        
        # 尝试主模型
        models_to_try = [result.model_name] + result.fallback_chain
        
        last_error = None
        for model_name in models_to_try:
            try:
                return self._call_model(
                    model_name=model_name,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
            except Exception as e:
                last_error = e
                self._record_failure(model_name)
                print(f"⚠️ 模型 {model_name} 调用失败: {e}")
                
                if model_name != models_to_try[-1]:
                    print(f"🔄 切换到备用模型...")
                    time.sleep(1)  # 短暂延迟后重试
        
        # 所有模型都失败
        raise RuntimeError(f"所有模型调用失败。最后错误: {last_error}")
    
    def stream(
        self,
        task_type: TaskType,
        prompt: str,
        temperature: Optional[float] = None,
        preferred_model: Optional[str] = None,
        **kwargs
    ) -> Iterator[str]:
        """
        流式调用模型
        
        Args:
            task_type: 任务类型
            prompt: 提示词
            temperature: 温度
            preferred_model: 优先使用的模型
            **kwargs: 其他参数
        
        Yields:
            str: 流式输出片段
        """
        result = self.route(task_type, preferred_model)
        client = self.clients.get(result.model_name)
        
        if not client:
            raise RuntimeError(f"模型 {result.model_name} 未初始化")
        
        # 检查客户端是否支持流式输出
        if hasattr(client, 'stream'):
            yield from client.stream(prompt, temperature=temperature, **kwargs)
        else:
            # 不支持流式，一次性返回
            yield client(prompt, temperature=temperature, **kwargs)
    
    def get_client(self, model_name: str) -> Callable:
        """获取指定模型的客户端"""
        return self.clients.get(model_name)
    
    def list_models(self) -> List[Dict]:
        """列出所有已注册的模型"""
        return [
            {
                "name": name,
                "provider": config.provider.value,
                "model_id": config.model_id,
                "enabled": config.enabled,
                "healthy": self._is_model_healthy(config),
                "task_preferences": {k.value: v for k, v in config.task_preferences.items()}
            }
            for name, config in self.models.items()
        ]
    
    def update_task_mapping(self, task_type: TaskType, model_names: List[str]):
        """更新任务-模型映射"""
        self.task_mapping[task_type] = model_names
    
    def _create_client(self, config: ModelConfig) -> Callable:
        """根据配置创建模型客户端"""
        # 这里可以根据 provider 类型创建不同的客户端
        # 简化实现：返回一个包装函数
        
        def client(prompt: str, temperature: Optional[float] = None, **kwargs) -> str:
            """默认客户端（需要外部注入实际实现）"""
            raise NotImplementedError(
                f"模型 {config.name} 的客户端未实现。"
                f"请通过 register_model 传入 client 参数。"
            )
        
        return client
    
    def _calculate_score(self, config: ModelConfig, task_type: TaskType) -> float:
        """计算模型对任务的匹配分数"""
        score = 0.0
        
        # 1. 任务偏好分数（0-1）
        preference = config.task_preferences.get(task_type, 0.5)
        score += preference * 50
        
        # 2. 健康度分数（根据失败次数降低）
        health_score = max(0, 30 - config._failure_count * 10)
        score += health_score
        
        # 3. 成本分数（成本越低越好）
        cost_score = max(0, 20 - (config.cost_per_1k_input + config.cost_per_1k_output) * 100)
        score += cost_score
        
        return score
    
    def _is_model_healthy(self, config: ModelConfig) -> bool:
        """检查模型是否健康"""
        # 如果最近 5 分钟内失败超过 3 次，认为不健康
        if config._failure_count >= 3:
            if config._last_failure and time.time() - config._last_failure < 300:
                return False
        
        return True
    
    def _record_failure(self, model_name: str):
        """记录模型失败"""
        if model_name in self.models:
            config = self.models[model_name]
            config._failure_count += 1
            config._last_failure = time.time()
    
    def _build_fallback_chain(self, task_type: TaskType, exclude: List[str] = None) -> List[str]:
        """构建备用模型链"""
        exclude = exclude or []
        candidates = self.task_mapping.get(task_type, [])
        
        fallback = []
        for model_name in candidates:
            if model_name in exclude:
                continue
            if model_name not in self.models:
                continue
            config = self.models[model_name]
            if not config.enabled:
                continue
            fallback.append(model_name)
        
        return fallback
    
    def _call_model(
        self,
        model_name: str,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """调用指定模型"""
        client = self.clients.get(model_name)
        if not client:
            raise RuntimeError(f"模型 {model_name} 未注册")
        
        config = self.models[model_name]
        
        # 使用模型默认参数
        temp = temperature if temperature is not None else config.temperature
        tokens = max_tokens if max_tokens is not None else config.max_tokens
        
        # 调用
        return client(prompt, temperature=temp, max_tokens=tokens, **kwargs)
    
    def _load_config(self, _config_path: Optional[str] = None):
        """从 StoryForge 主配置加载模型配置（~/.storyforge/storyforge.yaml）。"""
        # 延迟导入，避免模块初始化阶段的循环依赖。
        from core.config import get_config

        cfg = get_config()
        if not cfg.llm.api_key:
            return

        provider_map = {
            "openai": ModelProvider.OPENAI,
            "anthropic": ModelProvider.ANTHROPIC,
            "azure": ModelProvider.AZURE,
            "local": ModelProvider.LOCAL,
            "custom": ModelProvider.CUSTOM,
        }
        provider = provider_map.get((cfg.llm.provider or "").lower(), ModelProvider.CUSTOM)

        model_name = cfg.llm.model or f"{cfg.llm.provider}-default"
        self.register_model(ModelConfig(
            name=model_name,
            provider=provider,
            model_id=model_name,
            api_key=cfg.llm.api_key,
            api_base=cfg.llm.base_url or None,
            temperature=cfg.llm.temperature,
            timeout=cfg.llm.timeout,
            task_preferences={
                TaskType.WRITING: 0.8,
                TaskType.OUTLINE: 0.8,
                TaskType.REVIEW: 0.8,
                TaskType.PROOFREAD: 0.8,
                TaskType.IP_GENERATION: 0.8,
                TaskType.EXTRACTION: 0.8,
                TaskType.GENERAL: 0.8,
            },
            enabled=True,
        ))

        for task in TaskType:
            self.task_mapping[task] = [model_name]
    
    def save_config(self, config_path: str):
        """保存配置到文件"""
        data = {
            'models': [
                {
                    'name': config.name,
                    'provider': config.provider.value,
                    'model_id': config.model_id,
                    'api_key': config.api_key,
                    'api_base': config.api_base,
                    'max_tokens': config.max_tokens,
                    'temperature': config.temperature,
                    'timeout': config.timeout,
                    'retry_count': config.retry_count,
                    'task_preferences': {k.value: v for k, v in config.task_preferences.items()},
                    'cost_per_1k_input': config.cost_per_1k_input,
                    'cost_per_1k_output': config.cost_per_1k_output,
                    'enabled': config.enabled
                }
                for config in self.models.values()
            ],
            'task_mapping': {
                k.value: v
                for k, v in self.task_mapping.items()
            }
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ========== 便捷函数 ==========

def create_default_router() -> ModelRouter:
    """创建默认路由器（使用 StoryForge YAML 配置）。"""
    router = ModelRouter()
    return router
