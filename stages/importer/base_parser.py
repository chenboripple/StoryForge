"""
StoryForge - 文件解析器基类
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class FileFormat(Enum):
    """支持的文件格式"""
    TXT = "txt"
    MD = "md"
    EPUB = "epub"
    PDF = "pdf"
    IMAGE = "image"
    UNKNOWN = "unknown"


@dataclass
class ChapterImport:
    """导入的章节"""
    chapter_num: int
    title: str
    content: str
    word_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportResult:
    """导入结果"""
    success: bool
    novel_title: str = "未命名"
    author: str = ""
    genre: str = ""
    total_chapters: int = 0
    total_word_count: int = 0
    chapters: List[ChapterImport] = field(default_factory=list)
    raw_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class BaseParser(ABC):
    """
    文件解析器基类

    职责：
    1. 解析文件内容
    2. 提取章节结构
    3. 返回标准化的 ImportResult
    """

    # 支持的文件扩展名
    supported_extensions: set = set()

    @classmethod
    def can_parse(cls, filepath: str) -> bool:
        """判断是否能解析该文件"""
        ext = filepath.lower().rsplit(".", 1)[-1] if "." in filepath else ""
        return ext in cls.supported_extensions

    @abstractmethod
    def parse(self, filepath: str, **options) -> ImportResult:
        """
        解析文件

        Args:
            filepath: 文件路径
            **options: 解析选项（如章节分隔规则等）

        Returns:
            ImportResult 导入结果
        """
        pass

    def _split_chapters(self, text: str, pattern: Optional[str] = None) -> List[Dict[str, str]]:
        """
        按章节分割文本

        支持的分隔模式：
        - 第X章 / 第X章：标题
        - Chapter X / Chapter X: Title
        - # 标题（Markdown 格式）
        """
        import re

        # 默认章节分隔正则
        patterns = [
            r"第\s*[一二三四五六七八九十百零0-9]+\s*章[：:、\s]*[^\n]*",
            r"Chapter\s+[0-9IVX]+[.:、\s]*[^\n]*",
        ]

        if pattern:
            patterns = [pattern]

        # 尝试所有模式，选择匹配最多的
        best_result = None
        best_count = 0

        for pat in patterns:
            matches = list(re.finditer(pat, text, re.IGNORECASE))
            if len(matches) > best_count:
                best_count = len(matches)
                best_result = matches

        if not best_result or best_count < 1:
            # 没有章节结构，整篇作为一个章节
            return [{"title": "全文", "content": text}]

        chapters = []
        for i, match in enumerate(best_result):
            title = match.group(0).strip()
            start = match.end()
            end = best_result[i + 1].start() if i + 1 < len(best_result) else len(text)
            content = text[start:end].strip()
            if content:  # 跳过空内容章节
                chapters.append({
                    "title": title,
                    "content": content
                })

        return chapters if chapters else [{"title": "全文", "content": text}]

    def _detect_title(self, text: str) -> str:
        """从文本开头检测小说标题"""
        lines = text.strip().split("\n")
        for line in lines[:20]:
            line = line.strip()
            if line and len(line) < 100:
                # 排除常见非标题行
                if not line.startswith(("作者", "简介", "封面", "目录")):
                    return line
        return "未命名"

    def _count_words(self, text: str) -> int:
        """统计字数（中文字符 + 英文单词）"""
        import re
        chinese_chars = len(re.findall(r"[\u4e00-\u9fa5]", text))
        english_words = len(re.findall(r"[a-zA-Z]+", text))
        return chinese_chars + english_words
