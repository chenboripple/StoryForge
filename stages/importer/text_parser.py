"""
StoryForge - 纯文本解析器（txt / md / html）
"""
import re
from typing import Optional

from .base_parser import BaseParser, ImportResult, ChapterImport, FileFormat


class TextParser(BaseParser):
    """
    解析纯文本文件
    支持：.txt, .md, .html, .htm, .rst
    """

    supported_extensions = {"txt", "md", "markdown", "html", "htm", "rst", "org"}

    def parse(self, filepath: str, **options) -> ImportResult:
        """解析文本文件"""
        errors = []
        warnings = []

        try:
            # 自动检测编码
            content = self._read_text(filepath)
        except Exception as e:
            return ImportResult(
                success=False,
                errors=[f"读取文件失败: {e}"]
            )

        # 检测格式
        ext = filepath.rsplit(".", 1)[-1].lower()

        # 预处理
        if ext in ("md", "markdown"):
            content = self._strip_markdown(content)
        elif ext in ("html", "htm"):
            content = self._strip_html(content)

        # 提取元数据（作者、标题等）
        metadata = self._extract_metadata(content)
        title = metadata.get("title", self._detect_title(content))

        # 分割章节
        custom_pattern = options.get("chapter_pattern")
        chapter_dicts = self._split_chapters(content, custom_pattern)

        chapters = []
        total_words = 0
        for i, ch in enumerate(chapter_dicts, 1):
            word_count = self._count_words(ch["content"])
            total_words += word_count
            chapters.append(ChapterImport(
                chapter_num=i,
                title=ch["title"],
                content=ch["content"],
                word_count=word_count,
                metadata={"source_offset": i}
            ))

        # 检查
        if len(chapters) == 1 and chapters[0].word_count > 50000:
            warnings.append("单章节字数超过5万，建议检查章节分隔是否正确")

        if not chapters or all(ch.word_count == 0 for ch in chapters):
            errors.append("未能提取到任何有效内容")
            return ImportResult(success=False, errors=errors)

        return ImportResult(
            success=True,
            novel_title=title,
            author=metadata.get("author", ""),
            genre=metadata.get("genre", ""),
            total_chapters=len(chapters),
            total_word_count=total_words,
            chapters=chapters,
            raw_text=content,
            metadata=metadata,
            errors=errors,
            warnings=warnings
        )

    def _read_text(self, filepath: str) -> str:
        """自动检测编码并读取文本"""
        # 尝试常用编码
        encodings = ["utf-8", "gbk", "gb2312", "gb18030", "big5", "shift_jis"]

        for encoding in encodings:
            try:
                with open(filepath, "r", encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue

        # 如果都失败，用 errors="replace"
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def _strip_markdown(self, text: str) -> str:
        """去除 Markdown 标记，保留纯文本"""
        # 代码块
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # 链接
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"!?\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # 粗体/斜体
        text = re.sub(r"\*\*\*([^*]+)\*\*\*", r"\1", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\*([^*]+)\*", r"\1", text)
        text = re.sub(r"___([^_]+)___", r"\1", text)
        text = re.sub(r"__([^_]+)__", r"\1", text)
        text = re.sub(r"_([^_]+)_", r"\1", text)
        # HTML 标签
        text = re.sub(r"</?[^>]+>", "", text)
        # 引用
        text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)
        # 列表
        text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[\s]*\d+\.\s+", "", text, flags=re.MULTILINE)
        # 水平线
        text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
        return text.strip()

    def _strip_html(self, text: str) -> str:
        """去除 HTML 标签"""
        text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"</?[^>]+>", "", text)
        text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&quot;", " ", text)
        return text.strip()

    def _extract_metadata(self, text: str) -> dict:
        """提取文件开头的元数据"""
        metadata = {}
        lines = text.strip().split("\n")[:30]

        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 作者
            m = re.match(r"[作者著]\s*[：:]\s*(.+)", line)
            if m:
                metadata["author"] = m.group(1).strip()
                continue
            # 书名
            m = re.match(r"[书名作品]\s*[：:]\s*(.+)", line)
            if m:
                metadata["title"] = m.group(1).strip()
                continue
            # 类型
            m = re.match(r"[类型类别题材]\s*[：:]\s*(.+)", line)
            if m:
                metadata["genre"] = m.group(1).strip()
                continue
            # 简介
            m = re.match(r"[简介摘要介绍]\s*[：:]\s*(.+)", line)
            if m:
                metadata["summary"] = m.group(1).strip()

        return metadata
