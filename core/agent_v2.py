"""
StoryForge - Agent 基类
支持结构化输出（JSON mode）、记忆系统、错误处理
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, Union
from abc import ABC, abstractmethod
import json

from core.schema import ReviewResult, ProofreadResult, ChapterContent
from core.memory import StoryMemory
from core.utils.errors import ErrorHandler, with_error_handler


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
        use_json_mode: bool = False  # 是否要求 LLM 输出 JSON
    ):
        self.persona = persona
        self.llm_client = llm_client
        self.memory = memory
        self.error_handler = error_handler or ErrorHandler()
        self.use_json_mode = use_json_mode
        self.callbacks: List[Callable] = []
    
    def add_callback(self, callback: Callable):
        self.callbacks.append(callback)
    
    def _notify(self, event: str, data: dict):
        for callback in self.callbacks:
            callback(event, data)
    
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
        if not self.llm_client:
            raise ValueError(f"{self.persona.name} 未配置 LLM 客户端")
        
        # 组装 prompt
        prompt = self._assemble_prompt(task, context, json_schema)
        
        self._notify("llm_request", {
            "agent": self.persona.name,
            "task": task[:100],
            "json_mode": json_schema is not None
        })
        
        # 调用 LLM
        result = self.llm_client(prompt, temperature=temperature)
        
        # 如果要求 JSON，尝试解析
        if json_schema:
            result = self._parse_json_result(result, max_retries)
        
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
