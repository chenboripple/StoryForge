"""
StoryForge - 结构化输出 Schema
定义所有 LLM 输出的数据结构，确保类型安全
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import json


class ReviewVerdict(Enum):
    """审稿结论"""
    PASS = "pass"           # 通过
    REVISE = "revise"       # 需修改
    REWRITE = "rewrite"     # 重写


@dataclass
class DimensionScore:
    """维度评分"""
    name: str
    score: int          # 0-100
    weight: float       # 权重（如 0.3）
    comment: str = ""   # 该维度评语


@dataclass
class ReviewIssue:
    """审稿问题"""
    severity: str       # "fatal" | "improvement" | "highlight"
    location: str       # 问题位置（如"第3段"）
    description: str    # 问题描述
    suggestion: str     # 修改建议


@dataclass
class ReviewResult:
    """结构化审稿结果"""
    total_score: int
    dimensions: List[DimensionScore]
    issues: List[ReviewIssue]
    verdict: ReviewVerdict
    summary: str = ""   # 总体评语
    
    def to_json(self) -> str:
        """序列化为 JSON"""
        return json.dumps({
            "total_score": self.total_score,
            "dimensions": [
                {"name": d.name, "score": d.score, "weight": d.weight, "comment": d.comment}
                for d in self.dimensions
            ],
            "issues": [
                {"severity": i.severity, "location": i.location, 
                 "description": i.description, "suggestion": i.suggestion}
                for i in self.issues
            ],
            "verdict": self.verdict.value,
            "summary": self.summary
        }, ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "ReviewResult":
        """从 JSON 反序列化"""
        data = json.loads(json_str)
        return cls(
            total_score=data["total_score"],
            dimensions=[DimensionScore(**d) for d in data["dimensions"]],
            issues=[ReviewIssue(**i) for i in data["issues"]],
            verdict=ReviewVerdict(data["verdict"]),
            summary=data.get("summary", "")
        )


@dataclass
class ProofreadIssue:
    """校对问题"""
    type: str           # "typo" | "consistency" | "logic" | "format"
    location: str       # 位置
    original: str       # 原文
    correction: str     # 修改建议
    explanation: str = ""  # 说明


@dataclass
class ProofreadResult:
    """结构化校对结果"""
    passed: bool
    issues: List[ProofreadIssue]
    summary: str = ""
    
    def to_json(self) -> str:
        return json.dumps({
            "passed": self.passed,
            "issues": [
                {"type": i.type, "location": i.location, "original": i.original,
                 "correction": i.correction, "explanation": i.explanation}
                for i in self.issues
            ],
            "summary": self.summary
        }, ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "ProofreadResult":
        data = json.loads(json_str)
        return cls(
            passed=data["passed"],
            issues=[ProofreadIssue(**i) for i in data["issues"]],
            summary=data.get("summary", "")
        )


@dataclass
class ChapterContent:
    """章节内容（替代简单的 str）"""
    text: str
    version: int = 1
    word_count: int = 0
    generated_at: str = ""
    modified_at: str = ""
    
    def __post_init__(self):
        if self.word_count == 0:
            self.word_count = len(self.text)


# Prompt 模板：要求 LLM 输出 JSON
REVIEW_JSON_PROMPT = """
请严格按照以下 JSON 格式输出审稿结果（不要输出其他内容）：

{
  "total_score": <0-100的总评分>,
  "dimensions": [
    {"name": "叙事结构", "score": <0-100>, "weight": 0.3, "comment": "..."},
    {"name": "人物一致性", "score": <0-100>, "weight": 0.3, "comment": "..."},
    {"name": "文学性", "score": <0-100>, "weight": 0.3, "comment": "..."},
    {"name": "市场潜力", "score": <0-100>, "weight": 0.1, "comment": "..."}
  ],
  "issues": [
    {"severity": "fatal", "location": "第X段", "description": "...", "suggestion": "..."},
    {"severity": "improvement", "location": "第X段", "description": "...", "suggestion": "..."},
    {"severity": "highlight", "location": "第X段", "description": "...", "suggestion": "保持"}
  ],
  "verdict": "pass|revise|rewrite",
  "summary": "总体评语"
}

评分标准：
- ≥85分：pass（通过）
- 60-84分：revise（需修改）
- <60分：rewrite（重写）
"""

PROOFREAD_JSON_PROMPT = """
请严格按照以下 JSON 格式输出校对结果（不要输出其他内容）：

{
  "passed": true|false,
  "issues": [
    {"type": "typo|consistency|logic|format", "location": "第X段", 
     "original": "原文", "correction": "修改", "explanation": "说明"}
  ],
  "summary": "总体评价"
}

如果无错误，issues 为空数组，passed 为 true。
"""
