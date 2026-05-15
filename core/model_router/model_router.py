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
    # provider 扩展参数
    extra: Dict[str, Any] = field(default_factory=dict)
    # 成本估算（每 1K tokens）
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    # 是否启用
    enabled: bool = True
    # 失败次数（自动统计）
    _failure_count: int = 0
    # 成功次数（自动统计）
    _success_count: int = 0
    # 调用总次数（自动统计）
    _call_count: int = 0
    # 连续失败次数（用于熔断）
    _consecutive_failures: int = 0
    # 最后失败时间
    _last_failure: Optional[float] = None
    # 熔断冷却结束时间戳
    _cooldown_until: Optional[float] = None


@dataclass
class RoutingResult:
    """路由结果"""
    model_name: str
    model_config: ModelConfig
    task_type: TaskType
    fallback_chain: List[str] = field(default_factory=list)


@dataclass
class AgentRuntimeProfile:
    """Agent 运行时路由信息。

    设计目标：
    - 支持临时创建的 Agent 在运行时声明任务类型与模型偏好。
    - 不要求所有 Agent 都在配置文件里预注册。
    """

    agent_name: str = ""
    task_type: TaskType = TaskType.GENERAL
    preferred_model: Optional[str] = None
    budget_tier: str = "medium"  # low | medium | high
    latency_sla_ms: Optional[int] = None


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
        self.agent_preferences: Dict[str, str] = {}
        self.auto_downgrade: bool = True
        self.min_success_rate: float = 0.6
        self.health_min_calls: int = 5
        self.failure_cooldown_sec: int = 180
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
    
    def route(
        self,
        task_type: TaskType,
        preferred_model: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> RoutingResult:
        """
        为任务选择最合适的模型
        
        Args:
            task_type: 任务类型
            preferred_model: 优先使用的模型（如果可用）
        
        Returns:
            RoutingResult: 包含选中的模型和备用链
        """
        effective_preferred = preferred_model
        if not effective_preferred and agent_name:
            effective_preferred = self.agent_preferences.get(agent_name)

        # 1. 如果指定了优先模型且可用，直接使用
        if effective_preferred and effective_preferred in self.models:
            config = self.models[effective_preferred]
            if config.enabled and self._is_model_healthy(config):
                return RoutingResult(
                    model_name=effective_preferred,
                    model_config=config,
                    task_type=task_type,
                    fallback_chain=self._build_fallback_chain(task_type, exclude=[effective_preferred])
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
        agent_name: Optional[str] = None,
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
        result = self.route(task_type, preferred_model, agent_name=agent_name)
        
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
        agent_name: Optional[str] = None,
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
        result = self.route(task_type, preferred_model, agent_name=agent_name)
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

    def route_for_agent(self, profile: AgentRuntimeProfile) -> RoutingResult:
        """按 Agent 运行时信息进行路由。"""
        return self.route(
            task_type=profile.task_type,
            preferred_model=profile.preferred_model,
            agent_name=profile.agent_name or None,
        )

    def call_for_agent(
        self,
        profile: AgentRuntimeProfile,
        prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> str:
        """按 Agent 运行时信息调用模型（含自动降级）。"""
        return self.call(
            task_type=profile.task_type,
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            preferred_model=profile.preferred_model,
            agent_name=profile.agent_name or None,
            **kwargs,
        )
    
    def list_models(self) -> List[Dict]:
        """列出所有已注册的模型"""
        return [
            {
                "name": name,
                "provider": config.provider.value,
                "model_id": config.model_id,
                "enabled": config.enabled,
                "healthy": self._is_model_healthy(config),
                "success_rate": self._success_rate(config),
                "calls": config._call_count,
                "cooldown_until": config._cooldown_until,
                "task_preferences": {k.value: v for k, v in config.task_preferences.items()}
            }
            for name, config in self.models.items()
        ]

    def get_health_report(self) -> Dict[str, Any]:
        """返回模型健康监控视图（用于观测成功率与自动降级状态）。"""
        return {
            "auto_downgrade": self.auto_downgrade,
            "min_success_rate": self.min_success_rate,
            "health_min_calls": self.health_min_calls,
            "failure_cooldown_sec": self.failure_cooldown_sec,
            "models": self.list_models(),
        }

    def set_agent_preference(self, agent_name: str, model_name: str):
        """设置或更新某个 Agent 的默认模型偏好。"""
        if not agent_name or not agent_name.strip():
            raise ValueError("agent_name 不能为空")
        if model_name not in self.models:
            raise ValueError(f"未注册的模型: {model_name}")
        self.agent_preferences[agent_name.strip()] = model_name

    def clear_agent_preference(self, agent_name: str):
        """清除某个 Agent 的默认模型偏好。"""
        if not agent_name:
            return
        self.agent_preferences.pop(agent_name.strip(), None)
    
    def update_task_mapping(self, task_type: TaskType, model_names: List[str]):
        """更新任务-模型映射"""
        self.task_mapping[task_type] = model_names
    
    def _create_client(self, config: ModelConfig) -> Callable:
        """根据配置创建模型客户端。"""
        from core.config import LLMConfig
        from core.llm_factory import create_llm_client

        llm_cfg = LLMConfig(
            provider=config.provider.value,
            model=config.model_id,
            api_key=config.api_key or "",
            base_url=config.api_base or "",
            temperature=config.temperature,
            timeout=config.timeout,
            extra=config.extra or {},
        )
        try:
            return create_llm_client(llm_cfg)
        except Exception as e:
            error_msg = str(e)
            def _raise_client(_prompt: str, temperature: Optional[float] = None, **kwargs) -> str:
                _ = temperature
                _ = kwargs
                raise RuntimeError(f"模型 {config.name} 客户端创建失败: {error_msg}")
            return _raise_client
    
    def _calculate_score(self, config: ModelConfig, task_type: TaskType) -> float:
        """计算模型对任务的匹配分数"""
        score = 0.0
        
        # 1. 任务偏好分数（0-1）
        preference = config.task_preferences.get(task_type, 0.5)
        score += preference * 50
        
        # 2. 健康度分数（根据失败次数降低）
        health_score = max(0, 30 - config._failure_count * 10)
        score += health_score

        # 3. 成功率分数（稳定性）
        success_score = self._success_rate(config) * 20
        score += success_score
        
        # 4. 成本分数（成本越低越好）
        cost_score = max(0, 20 - (config.cost_per_1k_input + config.cost_per_1k_output) * 100)
        score += cost_score
        
        return score
    
    def _is_model_healthy(self, config: ModelConfig) -> bool:
        """检查模型是否健康"""
        now = time.time()

        # 冷却中的模型暂不参与路由。
        if config._cooldown_until and config._cooldown_until > now:
            return False

        if not self.auto_downgrade:
            return True

        # 近阶段成功率不足时降级。
        if config._call_count >= self.health_min_calls:
            if self._success_rate(config) < self.min_success_rate:
                return False

        # 连续失败触发短时熔断。
        if config._consecutive_failures >= 3:
            if config._last_failure and now - config._last_failure < self.failure_cooldown_sec:
                return False
        
        return True

    def _success_rate(self, config: ModelConfig) -> float:
        if config._call_count <= 0:
            return 1.0
        return config._success_count / config._call_count
    
    def _record_failure(self, model_name: str):
        """记录模型失败"""
        if model_name in self.models:
            config = self.models[model_name]
            config._call_count += 1
            config._failure_count += 1
            config._consecutive_failures += 1
            config._last_failure = time.time()
            if self.auto_downgrade and config._consecutive_failures >= 3:
                config._cooldown_until = time.time() + self.failure_cooldown_sec

    def _record_success(self, model_name: str):
        """记录模型成功。"""
        if model_name in self.models:
            config = self.models[model_name]
            config._call_count += 1
            config._success_count += 1
            config._consecutive_failures = 0
            config._cooldown_until = None
    
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
        result = client(prompt, temperature=temp, max_tokens=tokens, **kwargs)
        self._record_success(model_name)
        return result
    
    def _load_config(self, _config_path: Optional[str] = None):
        """从 StoryForge 主配置加载模型配置（~/.storyforge/storyforge.yaml）。"""
        # 延迟导入，避免模块初始化阶段的循环依赖。
        from core.config import get_config

        cfg = get_config()
        loaded_any = False

        # 新格式：models + model_routing
        if getattr(cfg, "models", None):
            provider_map = {
                "openai": ModelProvider.OPENAI,
                "anthropic": ModelProvider.ANTHROPIC,
                "azure": ModelProvider.AZURE,
                "local": ModelProvider.LOCAL,
                "custom": ModelProvider.CUSTOM,
                "mock": ModelProvider.CUSTOM,
            }

            provider_profiles = {
                str(p.name): p for p in (getattr(cfg, "model_providers", None) or []) if getattr(p, "name", "")
            }

            for m in cfg.models:
                resolved_provider = (m.provider or "").lower()
                resolved_api_key = m.api_key or ""
                resolved_base_url = m.base_url or ""
                resolved_timeout = int(m.timeout)
                resolved_extra = dict(m.extra or {})

                provider_name = str(getattr(m, "provider_name", "") or "").strip()
                if provider_name:
                    profile = provider_profiles.get(provider_name)
                    if not profile:
                        raise RuntimeError(f"models[{m.name}] 引用了不存在的 provider_name: {provider_name}")

                    if getattr(profile, "provider", ""):
                        resolved_provider = str(profile.provider).lower()
                    if not resolved_api_key:
                        resolved_api_key = str(getattr(profile, "api_key", "") or "")
                    if not resolved_base_url:
                        resolved_base_url = str(getattr(profile, "base_url", "") or "")
                    if getattr(profile, "timeout", None):
                        resolved_timeout = int(profile.timeout)

                    profile_extra = dict(getattr(profile, "extra", {}) or {})
                    profile_extra.update(resolved_extra)
                    resolved_extra = profile_extra

                provider = provider_map.get(resolved_provider, ModelProvider.CUSTOM)
                task_prefs: Dict[TaskType, float] = {}
                for task_name, weight in (m.task_preferences or {}).items():
                    try:
                        task_prefs[TaskType(task_name)] = float(weight)
                    except Exception:
                        continue

                self.register_model(ModelConfig(
                    name=m.name or m.model,
                    provider=provider,
                    model_id=m.model,
                    api_key=resolved_api_key or None,
                    api_base=resolved_base_url or None,
                    max_tokens=m.max_tokens,
                    temperature=m.temperature,
                    timeout=resolved_timeout,
                    task_preferences=task_prefs,
                    extra=resolved_extra,
                    cost_per_1k_input=float(m.cost_per_1k_input or 0.0),
                    cost_per_1k_output=float(m.cost_per_1k_output or 0.0),
                    enabled=bool(m.enabled),
                ))
                loaded_any = True

            routing = getattr(cfg, "model_routing", None)
            if routing:
                self.auto_downgrade = bool(getattr(routing, "auto_downgrade", True))
                self.min_success_rate = float(getattr(routing, "min_success_rate", 0.6))
                self.health_min_calls = int(getattr(routing, "health_min_calls", 5))
                self.failure_cooldown_sec = int(getattr(routing, "failure_cooldown_sec", 180))
                self.agent_preferences = dict(getattr(routing, "agent_preferences", {}) or {})

                task_mapping = dict(getattr(routing, "task_mapping", {}) or {})
                for task_name, model_names in task_mapping.items():
                    try:
                        task = TaskType(task_name)
                    except Exception:
                        continue
                    if isinstance(model_names, list):
                        self.task_mapping[task] = [str(x) for x in model_names if str(x).strip()]

        if loaded_any:
            self._validate_mapping_references()
            return
        raise RuntimeError(
            "未加载到任何模型配置。请在 ~/.storyforge/storyforge.yaml 配置 model_providers/models。"
        )

    def _validate_mapping_references(self):
        """校验 task_mapping 与 agent_preferences 是否引用已注册模型。"""
        known = set(self.models.keys())
        missing: List[str] = []

        for task, model_names in self.task_mapping.items():
            for name in model_names:
                if name not in known:
                    missing.append(f"task_mapping.{task.value}: {name}")

        for agent_name, model_name in self.agent_preferences.items():
            if model_name not in known:
                missing.append(f"agent_preferences.{agent_name}: {model_name}")

        if missing:
            detail = "; ".join(missing)
            raise RuntimeError(f"模型映射引用了不存在的模型: {detail}")
    
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
            'model_routing': {
                'task_mapping': {
                    k.value: v
                    for k, v in self.task_mapping.items()
                },
                'agent_preferences': dict(self.agent_preferences),
                'auto_downgrade': self.auto_downgrade,
                'min_success_rate': self.min_success_rate,
                'health_min_calls': self.health_min_calls,
                'failure_cooldown_sec': self.failure_cooldown_sec,
            }
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ========== 便捷函数 ==========

def create_default_router() -> ModelRouter:
    """创建默认路由器（使用 StoryForge YAML 配置）。"""
    router = ModelRouter()
    return router
