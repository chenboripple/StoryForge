"""
NovelForge - Agent 基类与 CrewAI 风格角色系统
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable
from abc import ABC, abstractmethod

from core.state import NovelState


@dataclass
class AgentPersona:
    """
    CrewAI 风格的角色人设
    
    设计原则：
    1. 人设不是装饰，会注入系统提示词直接影响 LLM 输出
    2. 每个字段都有明确的工程用途
    3. 支持动态生成 prompt，便于调试和迭代
    """
    
    # 身份标识
    name: str                                   # 名字（墨川）
    role: str                                   # 角色（小说家）
    
    # 目标驱动
    goal: str                                   # 核心目标
    
    # 背景故事（影响 LLM 的语气和知识倾向）
    backstory: str = ""                         
    
    # 专业能力（影响任务分配和工具使用）
    expertise: List[str] = field(default_factory=list)
    
    # 语气风格（影响输出文本的调性）
    tone: str = "专业、客观"
    
    # 工作原则（影响决策逻辑）
    principles: List[str] = field(default_factory=list)
    
    # 限制条件（影响输出边界）
    constraints: List[str] = field(default_factory=list)
    
    def system_prompt(self) -> str:
        """
        生成完整的系统提示词
        
        面试时可以讲：这是"角色即提示词工程"的设计，
        把产品层面的"人设"直接转化为工程层面的"系统提示词"
        """
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
        """格式化列表为字符串"""
        if not items:
            return "无"
        return "\n".join(f"- {item}" for item in items)
    
    def __repr__(self) -> str:
        return f"AgentPersona(name='{self.name}', role='{self.role}')"


class BaseAgent(ABC):
    """
    Agent 基类
    
    设计原则：
    1. 每个 Agent 是纯函数：输入 State，输出新 State
    2. 不直接调用 LLM，通过 llm_client 抽象，便于切换模型
    3. 支持回调钩子，便于调试和监控
    """
    
    def __init__(
        self,
        persona: AgentPersona,
        llm_client: Optional[Callable] = None
    ):
        self.persona = persona
        self.llm_client = llm_client
        self.callbacks: List[Callable] = []
    
    def add_callback(self, callback: Callable):
        """添加回调（用于日志、监控等）"""
        self.callbacks.append(callback)
    
    def _notify(self, event: str, data: dict):
        """通知所有回调"""
        for callback in self.callbacks:
            callback(event, data)
    
    @abstractmethod
    def invoke(self, state: NovelState) -> NovelState:
        """
        执行 Agent 任务
        
        Args:
            state: 当前全局状态
            
        Returns:
            更新后的全局状态
        """
        pass
    
    def _call_llm(
        self,
        task: str,
        context: str = "",
        temperature: Optional[float] = None
    ) -> str:
        """
        调用 LLM，自动注入人设
        
        Args:
            task: 具体任务描述
            context: 任务上下文（来自 State）
            temperature: 覆盖默认温度
        """
        if not self.llm_client:
            raise ValueError(f"{self.persona.name} 未配置 LLM 客户端")
        
        prompt = f"""{self.persona.system_prompt()}

========== 任务上下文 ==========
{context}

========== 当前任务 ==========
{task}

请直接输出结果，不需要解释你的思考过程。"""
        
        self._notify("llm_request", {
            "agent": self.persona.name,
            "task": task[:100]  # 截断用于日志
        })
        
        result = self.llm_client(prompt, temperature=temperature)
        
        self._notify("llm_response", {
            "agent": self.persona.name,
            "result_length": len(result)
        })
        
        return result


class Task:
    """
    CrewAI 风格的任务定义
    
    把"做什么"和"怎么做"分离：
    - Task 定义"做什么"（描述、期望输出）
    - Agent 定义"怎么做"（角色、能力）
    """
    
    def __init__(
        self,
        description: str,
        expected_output: str,
        agent: Optional[BaseAgent] = None,
        context_tasks: Optional[List[str]] = None
    ):
        self.description = description
        self.expected_output = expected_output
        self.agent = agent
        self.context_tasks = context_tasks or []
    
    def execute(self, state: NovelState) -> str:
        """执行任务"""
        if not self.agent:
            raise ValueError(f"任务 '{self.description}' 未分配 Agent")
        
        context = state.to_context_string()
        
        return self.agent._call_llm(
            task=self.description,
            context=context
        )
