"""
兼容层 - 校对模型
新代码请使用: from core.models.content import Proofread, ProofreadRecord, ...
"""
from __future__ import annotations

from core.models.content.proofread import (
    Proofread,
    ProofreadRecord,
    ProofreadIssue,
    ProofreadIssueType,
)

__all__ = [
    "Proofread",
    "ProofreadRecord",
    "ProofreadIssue",
    "ProofreadIssueType",
]
