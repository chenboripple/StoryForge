"""
StoryForge - PDF 解析器
"""
import re
from typing import Optional

from .base_parser import BaseParser, ImportResult, ChapterImport


class PDFParser(BaseParser):
    """
    解析 PDF 文件
    依赖：pdfplumber（轻量且效果好）
    备选：PyMuPDF (fitz)
    """

    supported_extensions = {"pdf"}

    def parse(self, filepath: str, **options) -> ImportResult:
        """解析 PDF 文件"""
        errors = []
        warnings = []

        # 尝试导入 pdfplumber
        try:
            import pdfplumber
        except ImportError:
            return ImportResult(
                success=False,
                errors=["未安装 pdfplumber，请运行: pip install pdfplumber"]
            )

        try:
            pages_text = []
            with pdfplumber.open(filepath) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text and text.strip():
                        pages_text.append(text.strip())

            if not pages_text:
                return ImportResult(
                    success=False,
                    errors=["PDF 未能提取到文本，可能是扫描件或图片 PDF"]
                )

            content = "\n\n".join(pages_text)

            # 提取元数据
            metadata = self._extract_pdf_metadata(filepath)
            title = metadata.get("title", self._detect_title(content))

            # 检查是否每页内容很少（可能是扫描件）
            avg_chars_per_page = sum(len(p) for p in pages_text) / len(pages_text)
            if avg_chars_per_page < 50:
                warnings.append(
                    f"平均每页仅 {avg_chars_per_page:.0f} 字符，可能是扫描件 PDF，"
                    "建议使用 OCR 功能"
                )

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
                    metadata={"source_pages": i}
                ))

            return ImportResult(
                success=True,
                novel_title=title,
                author=metadata.get("author", ""),
                genre="",
                total_chapters=len(chapters),
                total_word_count=total_words,
                chapters=chapters,
                raw_text=content,
                metadata=metadata,
                errors=errors,
                warnings=warnings
            )

        except Exception as e:
            return ImportResult(
                success=False,
                errors=[f"PDF 解析失败: {str(e)}"]
            )

    def _extract_pdf_metadata(self, filepath: str) -> dict:
        """提取 PDF 元数据"""
        metadata = {}
        try:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                meta = pdf.metadata or {}
                if meta.get("Title"):
                    metadata["title"] = meta["Title"]
                if meta.get("Author"):
                    metadata["author"] = meta["Author"]
                if meta.get("Subject"):
                    metadata["subject"] = meta["Subject"]
                metadata["total_pages"] = len(pdf.pages)
        except Exception:
            pass
        return metadata
