"""
Proofread - 校对数据
校对记录、问题列表
"""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

from ..base import BaseModel


class ProofreadIssueType(Enum):
    """校对问题类型"""
    TYPO = "typo"             # 错别字/语法
    CONSISTENCY = "consistency"  # 一致性（人名、地点前后不一致）
    LOGIC = "logic"           # 逻辑问题
    FORMAT = "format"         # 格式问题
    STYLE = "style"           # 文风问题


@dataclass
class ProofreadIssue(BaseModel):
    """校对问题"""
    issue_type: str = "typo"     # "typo" | "consistency" | "logic" | "format"
    location: str = ""           # 位置
    original: str = ""           # 原文
    correction: str = ""         # 修改建议
    explanation: str = ""        # 说明


@dataclass
class ProofreadRecord(BaseModel):
    """校对记录（单轮）"""
    novel_id: str = ""
    chapter_num: int = 1
    round: int = 1
    proofreader: str = ""        # 校对Agent名
    issues: List[ProofreadIssue] = field(default_factory=list)
    passed: bool = False
    summary: str = ""            # 总体评语
    scope: str = "chapter"       # "chapter" | "volume" | "book" | "project_docs"
    timestamp: str = ""


@dataclass
class Proofread(BaseModel):
    """章节校对汇总"""
    novel_id: str = ""
    chapter_num: int = 1
    records: List[ProofreadRecord] = field(default_factory=list)
    total_issues: int = 0
    final_passed: bool = False

    def add_record(self, record: ProofreadRecord):
        """添加校对记录"""
        self.records.append(record)
        self.total_issues += len(record.issues)
        if record.passed:
            self.final_passed = True

    def get_latest(self) -> Optional[ProofreadRecord]:
        """获取最新校对记录"""
        return self.records[-1] if self.records else None

    def get_issues_by_type(self, issue_type: str) -> List[ProofreadIssue]:
        """按类型获取问题"""
        issues = []
        for record in self.records:
            for issue in record.issues:
                if issue.issue_type == issue_type:
                    issues.append(issue)
        return issues

    def to_index_entry(self):
        """轻量索引"""
        latest = self.get_latest()
        return {
            "chapter_num": self.chapter_num,
            "proofread_rounds": len(self.records),
            "total_issues": self.total_issues,
            "latest_passed": latest.passed if latest else None,
        }
