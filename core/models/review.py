"""
Review - 审稿数据
审稿记录、评分维度、结论
"""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

from .base import BaseModel


class ReviewVerdict(Enum):
    """审稿结论"""
    PASS = "pass"         # 通过
    REVISE = "revise"     # 需修改
    REWRITE = "rewrite"   # 重写


@dataclass
class DimensionScore(BaseModel):
    """维度评分"""
    name: str = ""        # 维度名（如"叙事结构"）
    score: int = 0        # 0-100
    weight: float = 0.0   # 权重
    comment: str = ""     # 维度评语


@dataclass
class ReviewIssue(BaseModel):
    """审稿问题"""
    severity: str = ""       # "fatal" | "improvement" | "highlight"
    location: str = ""       # 位置（如"第3段"）
    description: str = ""    # 问题描述
    suggestion: str = ""     # 修改建议
    issue_type: str = ""     # 问题类型


@dataclass
class ReviewRecord(BaseModel):
    """审稿记录（单轮）"""
    novel_id: str = ""
    chapter_num: int = 1
    round: int = 1
    reviewer: str = ""       # 审稿Agent名
    total_score: int = 0     # 总分
    dimensions: List[DimensionScore] = field(default_factory=list)
    issues: List[ReviewIssue] = field(default_factory=list)
    verdict: ReviewVerdict = ReviewVerdict.REVISE
    summary: str = ""        # 总体评语
    passed: bool = False
    timestamp: str = ""


@dataclass
class Review(BaseModel):
    """章节审稿汇总"""
    novel_id: str = ""
    chapter_num: int = 1
    records: List[ReviewRecord] = field(default_factory=list)
    best_score: int = 0
    final_verdict: Optional[ReviewVerdict] = None

    def add_record(self, record: ReviewRecord):
        """添加审稿记录"""
        self.records.append(record)
        if record.total_score > self.best_score:
            self.best_score = record.total_score
        if record.verdict == ReviewVerdict.PASS:
            self.final_verdict = ReviewVerdict.PASS
        elif self.final_verdict is None:
            self.final_verdict = record.verdict

    def get_latest(self) -> Optional[ReviewRecord]:
        """获取最新审稿记录"""
        return self.records[-1] if self.records else None

    def get_issues_by_severity(self, severity: str) -> List[ReviewIssue]:
        """按严重级别获取问题"""
        issues = []
        for record in self.records:
            for issue in record.issues:
                if issue.severity == severity:
                    issues.append(issue)
        return issues

    def to_index_entry(self):
        """轻量索引"""
        latest = self.get_latest()
        return {
            "chapter_num": self.chapter_num,
            "review_rounds": len(self.records),
            "best_score": self.best_score,
            "latest_score": latest.total_score if latest else None,
            "latest_verdict": latest.verdict.value if latest else None,
            "latest_passed": latest.passed if latest else None,
        }
