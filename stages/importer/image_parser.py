"""
StoryForge - 图片/OCR 解析器
支持通过 OCR 从图片中提取文字
"""
import re
import os
from typing import List

from .base_parser import BaseParser, ImportResult, ChapterImport


class ImageParser(BaseParser):
    """
    解析图片文件（通过 OCR 提取文字）
    依赖：pytesseract + pillow + tesseract-ocr 引擎
    """

    supported_extensions = {"jpg", "jpeg", "png", "gif", "bmp", "tiff", "tif", "webp"}

    def parse(self, filepath: str, **options) -> ImportResult:
        """解析图片文件"""
        errors = []
        warnings = []

        # 检查依赖
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            return ImportResult(
                success=False,
                errors=[
                    "未安装 OCR 依赖。请运行:\n"
                    "  pip install pytesseract pillow\n"
                    "并安装 Tesseract-OCR 引擎:\n"
                    "  macOS: brew install tesseract\n"
                    "  Ubuntu: sudo apt install tesseract-ocr\n"
                    "  Windows: https://github.com/UB-Mannheim/tesseract/wiki"
                ]
            )

        # 检查 tesseract 引擎
        try:
            pytesseract.get_tesseract_version()
        except Exception as e:
            return ImportResult(
                success=False,
                errors=[f"Tesseract OCR 引擎不可用: {str(e)}"]
            )

        # 支持传入多张图片（目录或多个文件）
        if os.path.isdir(filepath):
            files = sorted([
                os.path.join(filepath, f)
                for f in os.listdir(filepath)
                if any(f.lower().endswith(ext) for ext in self.supported_extensions)
            ])
        else:
            files = [filepath]

        if not files:
            return ImportResult(
                success=False,
                errors=["未找到支持的图片文件"]
            )

        # OCR 配置
        lang = options.get("ocr_language", "chi_sim+eng")
        ocr_config = options.get("ocr_config", "--psm 6")

        chapters = []
        total_words = 0
        all_texts = []

        for i, img_path in enumerate(files, 1):
            try:
                image = Image.open(img_path)
                text = pytesseract.image_to_string(
                    image,
                    lang=lang,
                    config=ocr_config
                )
                text = text.strip()

                if not text:
                    warnings.append(f"图片 {os.path.basename(img_path)} 未能识别到文字")
                    continue

                all_texts.append(text)
                word_count = self._count_words(text)
                total_words += word_count

                chapters.append(ChapterImport(
                    chapter_num=i,
                    title=f"图片 {i}",
                    content=text,
                    word_count=word_count,
                    metadata={
                        "source_image": img_path,
                        "ocr_language": lang,
                    }
                ))

            except Exception as e:
                warnings.append(f"图片 {os.path.basename(img_path)} 处理失败: {str(e)}")

        if not chapters:
            return ImportResult(
                success=False,
                errors=errors,
                warnings=warnings + ["所有图片都未能识别到有效文字"]
            )

        # 合并为单章节或保持多章节
        if options.get("merge_chapters", True) and len(chapters) > 1:
            merged_text = "\n\n".join(all_texts)
            chapter_dicts = self._split_chapters(merged_text, options.get("chapter_pattern"))
            if len(chapter_dicts) > 1:
                chapters = []
                for j, ch in enumerate(chapter_dicts, 1):
                    word_count = self._count_words(ch["content"])
                    chapters.append(ChapterImport(
                        chapter_num=j,
                        title=ch["title"],
                        content=ch["content"],
                        word_count=word_count,
                    ))

        title = self._detect_title(chapters[0].content) if chapters else "未命名"
        if not title or title == "未命名":
            title = os.path.splitext(os.path.basename(files[0]))[0]

        return ImportResult(
            success=True,
            novel_title=title,
            author="",
            genre="",
            total_chapters=len(chapters),
            total_word_count=sum(ch.word_count for ch in chapters),
            chapters=chapters,
            raw_text="\n\n".join(ch.content for ch in chapters),
            metadata={"ocr_language": lang, "image_count": len(files)},
            errors=errors,
            warnings=warnings
        )
