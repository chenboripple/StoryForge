"""
StoryForge - Agent 基类
支持结构化输出（JSON mode）、记忆系统、错误处理
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, Union
from abc import ABC, abstractmethod
from datetime import datetime
import json

from core.schema import ReviewResult, ProofreadResult, ChapterContent
from core.memory import StoryMemory
from core.utils.errors import ErrorHandler, RetryWithBackoff


@dataclass
class AgentMessage:
    """Agent 间消息"""
    sender: str                      # 发送者名称
    msg_type: str                    # 消息类型：issue / suggestion / info / warning
    content: str                     # 消息内容
    target: Optional[str] = None     # 目标 Agent（None 表示广播）
    chapter: Optional[int] = None    # 相关章节
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    priority: str = "normal"         # low / normal / high / urgent


class MessageBus:
    """
    Agent 间消息总线
    
    支持：
    1. 发布/订阅模式
    2. 按消息类型过滤
    3. 按目标 Agent 定向投递
    4. 消息持久化（用于断点续跑）
    """
    
    def __init__(self):
        self._messages: List[AgentMessage] = []
        self._subscribers: Dict[str, List[Callable]] = {}
        self._type_subscribers: Dict[str, List[Callable]] = {}
    
    def publish(self, message: AgentMessage):
        """发布消息"""
        self._messages.append(message)
        
        # 通知特定目标订阅者
        if message.target and message.target in self._subscribers:
            for callback in self._subscribers[message.target]:
                callback(message)
        
        # 通知类型订阅者
        if message.msg_type in self._type_subscribers:
            for callback in self._type_subscribers[message.msg_type]:
                callback(message)
        
        # 通知广播订阅者（target为None的订阅者）
        if None in self._subscribers:
            for callback in self._subscribers[None]:
                callback(message)
    
    def subscribe(self, agent_name: Optional[str], callback: Callable):
        """
        订阅消息
        
        Args:
            agent_name: 订阅哪个 Agent 的消息（None 表示订阅所有）
            callback: 回调函数，接收 AgentMessage
        """
        if agent_name not in self._subscribers:
            self._subscribers[agent_name] = []
        self._subscribers[agent_name].append(callback)
    
    def subscribe_by_type(self, msg_type: str, callback: Callable):
        """按消息类型订阅"""
        if msg_type not in self._type_subscribers:
            self._type_subscribers[msg_type] = []
        self._type_subscribers[msg_type].append(callback)
    
    def get_messages(
        self,
        agent: Optional[str] = None,
        msg_type: Optional[str] = None,
        chapter: Optional[int] = None,
        since: Optional[str] = None
    ) -> List[AgentMessage]:
        """查询历史消息"""
        result = self._messages
        
        if agent:
            result = [m for m in result if m.sender == agent or m.target == agent]
        if msg_type:
            result = [m for m in result if m.msg_type == msg_type]
        if chapter:
            result = [m for m in result if m.chapter == chapter]
        if since:
            result = [m for m in result if m.timestamp >= since]
        
        return result
    
    def get_unread_for_agent(self, agent_name: str) -> List[AgentMessage]:
        """获取指定 Agent 的未读消息（target为该Agent或广播）"""
        return [
            m for m in self._messages
            if m.target == agent_name or m.target is None
        ]
    
    def to_dict(self) -> List[Dict]:
        """序列化所有消息"""
        return [
            {
                "sender": m.sender,
                "msg_type": m.msg_type,
                "content": m.content,
                "target": m.target,
                "chapter": m.chapter,
                "timestamp": m.timestamp,
                "priority": m.priority
            }
            for m in self._messages
        ]
    
    @classmethod
    def from_dict(cls, data: List[Dict]) -> 'MessageBus':
        """从序列化数据恢复"""
        bus = cls()
        for item in data:
            bus.publish(AgentMessage(**item))
        return bus


@dataclass
class AgentPersona:
    """CrewAI 风格的角色人设（保持兼容）"""
    
    name: str
    role: str
    goal: str
    backstory: str = ""
    expertise: List[str] = field(default_factory=list)
    tone: str = "专业、客观"
    principles: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    
    def system_prompt(self) -> str:
        """生成系统提示词"""
        prompt = f"""你是{self.name}，{self.role}。

【背景】
{self.backstory}

【目标】
{self.goal}

【专业领域】
{self._format_list(self.expertise)}

【语气风格】
{self.tone}
"""
        
        if self.principles:
            prompt += f"\n【工作原则】\n{self._format_list(self.principles)}"
        
        if self.constraints:
            prompt += f"\n【限制条件】\n{self._format_list(self.constraints)}"
        
        prompt += "\n\n现在，请以你的身份开始工作。"
        
        return prompt
    
    def _format_list(self, items: List[str]) -> str:
        if not items:
            return "无"
        return "\n".join(f"- {item}" for item in items)
    
    def __repr__(self) -> str:
        return f"AgentPersona(name='{self.name}', role='{self.role}')"


class BaseAgent(ABC):
    """
    重构后的 Agent 基类
    
    改进：
    1. 结构化输出：支持 JSON mode
    2. 记忆集成：自动注入 StoryMemory 上下文
    3. 错误处理：装饰器自动捕获异常
    4. Prompt 组装：支持动态上下文注入
    """
    
    def __init__(
        self,
        persona: AgentPersona,
        llm_client: Optional[Callable] = None,
        memory: Optional[StoryMemory] = None,
        error_handler: Optional[ErrorHandler] = None,
        use_json_mode: bool = False,  # 是否要求 LLM 输出 JSON
        message_bus: Optional[MessageBus] = None,  # Agent 间通信总线
        state: Optional[Any] = None  # 可选：直接绑定 state 用于无 message_bus 场景
    ):
        self.persona = persona
        self.llm_client = llm_client
        self.memory = memory
        self.error_handler = error_handler or ErrorHandler()
        self.use_json_mode = use_json_mode
        self.message_bus = message_bus  # 消息总线
        self.state = state  # 可选：直接绑定 state
        self.callbacks: List[Callable] = []
        self.retry_executor = RetryWithBackoff(
            max_retries=self.error_handler.max_retries + 1,
            base_delay=1.0
        )

        # 如果提供了消息总线，自动订阅相关消息
        if self.message_bus:
            self._setup_message_subscriptions()
    
    def _setup_message_subscriptions(self):
        """设置消息订阅（子类可覆盖）"""
        # 默认订阅与自己相关的消息
        self.message_bus.subscribe(self.persona.name, self._on_message)
        # 订阅广播消息
        self.message_bus.subscribe(None, self._on_broadcast)
    
    def _on_message(self, message: AgentMessage):
        """处理定向消息（子类可覆盖）"""
        print(f"📨 [{self.persona.name}] 收到来自 {message.sender} 的消息: {message.content[:100]}...")
    
    def _on_broadcast(self, message: AgentMessage):
        """处理广播消息（子类可覆盖）"""
        pass  # 默认忽略广播
    
    def publish_message(
        self,
        msg_type: str,
        content: str,
        target: Optional[str] = None,
        chapter: Optional[int] = None,
        priority: str = "normal"
    ):
        """发布消息到总线（同时持久化到 state 如果可用）"""
        chapter = chapter or getattr(self, '_current_chapter', None)

        # 1. 发布到 MessageBus
        if self.message_bus:
            message = AgentMessage(
                sender=self.persona.name,
                msg_type=msg_type,
                content=content,
                target=target,
                chapter=chapter,
                priority=priority
            )
            self.message_bus.publish(message)

        # 2. 持久化到 state（无 MessageBus 或作为备份）
        if self.state and hasattr(self.state, 'add_agent_message'):
            self.state.add_agent_message(
                sender=self.persona.name,
                msg_type=msg_type,
                content=content,
                target=target,
                chapter=chapter,
                priority=priority
            )
    
    def get_messages_from_bus(
        self,
        msg_type: Optional[str] = None,
        chapter: Optional[int] = None
    ) -> List[AgentMessage]:
        """从总线获取与自己相关的消息"""
        if not self.message_bus:
            return []
        return self.message_bus.get_messages(
            agent=self.persona.name,
            msg_type=msg_type,
            chapter=chapter
        )

    def get_messages_from_state(
        self,
        msg_type: Optional[str] = None,
        chapter: Optional[int] = None,
        limit: int = 10
    ) -> List[Dict]:
        """从 state 获取消息（MessageBus 不可用时的回退）"""
        if not self.state or not hasattr(self.state, 'get_agent_messages'):
            return []
        return self.state.get_agent_messages(
            msg_type=msg_type,
            chapter=chapter,
            limit=limit
        )

    def suggest_route(
        self,
        suggested_node: str,
        reason: str,
        confidence: float = 0.8,
        chapter: Optional[int] = None
    ):
        """Agent 建议下一步路由（存入 state）"""
        chapter = chapter or getattr(self, '_current_chapter', None)
        if self.state and hasattr(self.state, 'add_routing_suggestion'):
            self.state.add_routing_suggestion(
                suggested_by=self.persona.name,
                suggested_node=suggested_node,
                reason=reason,
                confidence=confidence,
                chapter=chapter
            )
        # 同时作为消息发布
        self.publish_message(
            msg_type="routing_suggestion",
            content=f"建议下一步：{suggested_node}。原因：{reason}",
            chapter=chapter,
            priority="high"
        )

    def _get_agent_messages_for_prompt(
        self,
        state: Any,
        msg_type: Optional[str] = None,
        limit: int = 5
    ) -> str:
        """获取 Agent 消息用于 prompt 上下文"""
        messages = []

        # 优先从 MessageBus 获取
        if self.message_bus:
            bus_messages = self.message_bus.get_messages(
                agent=self.persona.name,
                msg_type=msg_type,
                chapter=getattr(state, 'current_chapter', None)
            )
            for m in bus_messages[-limit:]:
                messages.append(f"[{m.sender}] {m.msg_type}: {m.content}")

        # 从 state 获取（回退）
        if not messages and hasattr(state, 'get_agent_messages'):
            state_messages = state.get_agent_messages(
                msg_type=msg_type,
                chapter=getattr(state, 'current_chapter', None),
                limit=limit
            )
            for m in state_messages:
                messages.append(f"[{m['sender']}] {m['msg_type']}: {m['content']}")

        if not messages:
            return ""

        return "\n".join(["\n【来自其他 Agent 的消息】"] + messages)
    
    def add_callback(self, callback: Callable):
        self.callbacks.append(callback)
    
    def _notify(self, event: str, data: dict):
        for callback in self.callbacks:
            callback(event, data)
    
    def _notify_bus(self, event_type: str, data: dict):
        """向消息总线发布事件（供其他 Agent 订阅）"""
        if self.message_bus:
            self.message_bus.publish(AgentMessage(
                sender=self.persona.name,
                msg_type=event_type,
                content=str(data),
                chapter=data.get('chapter')
            ))
    
    @abstractmethod
    def invoke(self, state: Any) -> Any:
        """执行 Agent 任务（子类实现）"""
        pass
    
    def _call_llm(
        self,
        task: str,
        context: str = "",
        temperature: Optional[float] = None,
        json_schema: Optional[str] = None,
        max_retries: int = 2
    ) -> Union[str, Dict]:
        """
        调用 LLM，支持结构化输出
        
        Args:
            task: 任务描述
            context: 上下文
            temperature: 温度
            json_schema: JSON 格式要求（如 ReviewResult 的 schema）
            max_retries: 解析失败时重试次数
        """
        # 组装 prompt
        prompt = self._assemble_prompt(task, context, json_schema)
        return self._call_llm_raw(
            prompt=prompt,
            json_mode=json_schema is not None,
            task=task,
            temperature=temperature,
            max_retries=max_retries
        )

    def _call_llm_raw(
        self,
        prompt: str,
        json_mode: bool = False,
        task: str = "",
        temperature: Optional[float] = None,
        max_retries: int = 2
    ) -> Union[str, Dict]:
        """统一 LLM 调用入口：重试 + JSON 解析兜底 + 事件通知"""
        if not self.llm_client:
            raise ValueError(f"{self.persona.name} 未配置 LLM 客户端")

        self._notify("llm_request", {
            "agent": self.persona.name,
            "task": (task or "raw_prompt")[:100],
            "json_mode": json_mode
        })

        def _invoke_once():
            if temperature is None:
                return self.llm_client(prompt)
            try:
                return self.llm_client(prompt, temperature=temperature)
            except TypeError:
                return self.llm_client(prompt)

        raw_result = self.retry_executor.execute(_invoke_once)
        result: Union[str, Dict] = raw_result

        if json_mode:
            result = self._parse_json_result(str(raw_result), max_retries)

        self._notify("llm_response", {
            "agent": self.persona.name,
            "result_length": len(str(result))
        })

        return result
    
    def _assemble_prompt(
        self,
        task: str,
        context: str,
        json_schema: Optional[str] = None
    ) -> str:
        """组装完整 prompt"""
        parts = [
            self.persona.system_prompt(),
            "\n========== 任务上下文 ==========",
            context,
            "\n========== 当前任务 ==========",
            task,
        ]
        
        if json_schema:
            parts.append("\n========== 输出格式要求 ==========")
            parts.append(json_schema)
            parts.append("\n请严格按照上述 JSON 格式输出，不要输出其他内容。")
        else:
            parts.append("\n请直接输出结果，不需要解释你的思考过程。")
        
        return "\n".join(parts)
    
    def _parse_json_result(self, result: str, max_retries: int) -> Dict:
        """解析 JSON 输出，失败时重试"""
        import json
        
        for attempt in range(max_retries + 1):
            try:
                # 尝试提取 JSON 块
                json_str = self._extract_json(result)
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                if attempt < max_retries:
                    print(f"⚠️ JSON 解析失败，尝试修复... ({e})")
                    result = self._fix_json(result)
                else:
                    raise ValueError(f"无法解析 LLM 输出为 JSON: {result[:200]}")
        
        return {}
    
    def _extract_json(self, text: str) -> str:
        """从文本中提取 JSON 块"""
        # 尝试找 ```json ... ``` 代码块
        import re
        
        # 匹配 markdown JSON 代码块
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return match.group(1)
        
        # 匹配普通代码块
        match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            return match.group(1)
        
        # 尝试找 { ... } 包裹的内容
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0)
        
        # 如果都没找到，返回原文
        return text.strip()
    
    def _fix_json(self, text: str) -> str:
        """尝试修复常见的 JSON 格式问题"""
        # 1. 去掉可能的 BOM
        text = text.lstrip('\ufeff')
        # 2. 去掉尾部逗号
        text = text.replace(',\n}', '\n}').replace(',]', ']')
        # 3. 处理单引号
        text = text.replace("'", '"')
        return text
    
    def _build_memory_context(self, state: Any) -> str:
        """构建记忆上下文（如果 memory 存在）"""
        if not self.memory:
            return ""
        
        chapter = getattr(state, 'current_chapter', 1)
        return self.memory.build_context_for_chapter(chapter)
