"""
StoryForge - 小说导入器
统一入口：自动识别文件类型并调用对应解析器
"""
import os
import uuid
from typing import Optional, List
from datetime import datetime

from .base_parser import ImportResult, ChapterImport, FileFormat
from .text_parser import TextParser
from .pdf_parser import PDFParser
from .epub_parser import EPUBParser
from .image_parser import ImageParser


class NovelImporter:
    """
    小说导入器

    职责：
    1. 自动检测文件类型
    2. 调用对应解析器
    3. 将 ImportResult 转换为 NovelState
    4. 保存到存储层
    """

    # 注册所有解析器
    PARSERS = [
        TextParser,
        EPUBParser,
        PDFParser,
        ImageParser,
    ]

    @classmethod
    def detect_format(cls, filepath: str) -> FileFormat:
        """根据文件扩展名检测格式"""
        if os.path.isdir(filepath):
            # 检查目录中的文件
            for fname in os.listdir(filepath):
                for parser_cls in cls.PARSERS:
                    if parser_cls.can_parse(fname):
                        return cls._format_from_parser(parser_cls)
            return FileFormat.UNKNOWN

        ext = filepath.rsplit(".", 1)[-1].lower() if "." in filepath else ""

        format_map = {
            "txt": FileFormat.TXT,
            "md": FileFormat.MD,
            "markdown": FileFormat.MD,
            "html": FileFormat.TXT,
            "htm": FileFormat.TXT,
            "rst": FileFormat.TXT,
            "org": FileFormat.TXT,
            "epub": FileFormat.EPUB,
            "pdf": FileFormat.PDF,
            "jpg": FileFormat.IMAGE,
            "jpeg": FileFormat.IMAGE,
            "png": FileFormat.IMAGE,
            "gif": FileFormat.IMAGE,
            "bmp": FileFormat.IMAGE,
            "tiff": FileFormat.IMAGE,
            "tif": FileFormat.IMAGE,
            "webp": FileFormat.IMAGE,
        }
        return format_map.get(ext, FileFormat.UNKNOWN)

    @classmethod
    def _format_from_parser(cls, parser_cls) -> FileFormat:
        """根据解析器类获取格式"""
        name_map = {
            "TextParser": FileFormat.TXT,
            "EPUBParser": FileFormat.EPUB,
            "PDFParser": FileFormat.PDF,
            "ImageParser": FileFormat.IMAGE,
        }
        return name_map.get(parser_cls.__name__, FileFormat.UNKNOWN)

    @classmethod
    def get_supported_extensions(cls) -> List[str]:
        """获取所有支持的扩展名"""
        exts = set()
        for parser_cls in cls.PARSERS:
            exts.update(parser_cls.supported_extensions)
        return sorted(exts)

    def parse(self, filepath: str, **options) -> ImportResult:
        """
        解析文件

        Args:
            filepath: 文件路径
            **options: 解析选项
                - chapter_pattern: 自定义章节分隔正则
                - ocr_language: OCR 语言（默认 chi_sim+eng）
                - merge_chapters: 是否合并章节（图片导入）

        Returns:
            ImportResult
        """
        # 找到合适的解析器
        parser = None
        for parser_cls in self.PARSERS:
            if parser_cls.can_parse(filepath):
                parser = parser_cls()
                break

        if parser is None:
            return ImportResult(
                success=False,
                errors=[f"不支持的文件格式: {filepath}"]
            )

        return parser.parse(filepath, **options)

    def import_to_state(self, filepath: str, novel_id: Optional[str] = None,
                        **options) -> dict:
        """
        导入文件并转换为 NovelState

        Args:
            filepath: 文件路径
            novel_id: 小说ID（自动生成 UUID 如果未提供）
            **options: 解析选项

        Returns:
            {"success": bool, "state": NovelState, "errors": [...], "warnings": [...]}
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

        from core.state import NovelState, CharacterInfo

        result = self.parse(filepath, **options)

        if not result.success:
            return {
                "success": False,
                "state": None,
                "errors": result.errors,
                "warnings": result.warnings
            }

        # 生成 novel_id
        if not novel_id:
            safe_title = "".join(c for c in result.novel_title if c.isalnum() or c == "_")
            novel_id = f"{safe_title or 'imported'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 构建 NovelState
        chapters = {}
        chapter_status = {}
        for ch in result.chapters:
            chapters[ch.chapter_num] = ch.content
            chapter_status[ch.chapter_num] = "draft"

        state = NovelState(
            novel_id=novel_id,
            novel_title=result.novel_title,
            genre=result.genre or "未分类",
            current_chapter=1,
            concept=result.metadata.get("description", ""),
            outline=result.raw_text[:1000] if result.raw_text else "",
            chapters=chapters,
            chapter_status=chapter_status,
            target_word_count=max(result.total_word_count // max(len(result.chapters), 1), 3000),
            current_stage="creation",
        )

        return {
            "success": True,
            "state": state,
            "result": result,
            "errors": result.errors,
            "warnings": result.warnings
        }

    def import_and_save(self, filepath: str, novel_id: Optional[str] = None,
                        **options) -> dict:
        """
        导入文件并直接保存到存储层

        Returns:
            {"success": bool, "novel_id": str, "state": NovelState, ...}
        """
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

        from backend.storage import save_novel

        result = self.import_to_state(filepath, novel_id, **options)

        if result["success"] and result["state"]:
            try:
                save_novel(result["state"])
                result["saved"] = True
                result["novel_id"] = result["state"].novel_id
            except Exception as e:
                result["saved"] = False
                result["errors"].append(f"保存失败: {str(e)}")

        return result
