"""文件导入端点（格式列表 / 上传 / 解析 / 保存）。

【兼容层】旧版 API，保持向后兼容。新代码应使用 /api/v1/import/。
"""

from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from core.config import get_config
from core.models import Chapter, ChapterStatus, NovelMeta, PipelineStage
from core.storage import StorageManager

from web_console.dependencies import get_storage_manager_dep
from web_console.security import (
    get_upload_type,
    sanitize_filename,
    validate_file_extension,
    validate_file_size,
    safe_novel_id,
)

router = APIRouter()


class SaveImportedRequest(BaseModel):
    novel_id: Optional[str] = None
    title: str = "未命名"
    author: str = ""
    genre: str = "未分类"
    concept: str = ""
    chapters: List[Dict[str, Any]] = Field(default_factory=list)


@router.get("/api/import/formats")
async def list_import_formats() -> dict:
    """列出支持的导入格式。"""
    from core.config import ALLOWED_UPLOAD_TYPES
    return {
        "formats": [
            {
                "type": "text",
                "name": "纯文本",
                "extensions": ALLOWED_UPLOAD_TYPES["text"],
                "description": "直接读取纯文本内容，支持自动章节识别",
            },
            {
                "type": "epub",
                "name": "EPUB 电子书",
                "extensions": ALLOWED_UPLOAD_TYPES["epub"],
                "description": "解析 EPUB 章节结构和元数据",
            },
            {
                "type": "pdf",
                "name": "PDF 文档",
                "extensions": ALLOWED_UPLOAD_TYPES["pdf"],
                "description": "提取 PDF 文字内容，扫描件建议使用图片导入",
            },
            {
                "type": "image",
                "name": "图片（OCR）",
                "extensions": ALLOWED_UPLOAD_TYPES["image"],
                "description": "通过 OCR 识别图片中的文字",
            },
        ]
    }


@router.post("/api/import/upload")
async def upload_file(
    file: UploadFile = File(...),
    chapter_pattern: Optional[str] = Form(None),
    ocr_language: Optional[str] = Form(None),
    merge_chapters: Optional[bool] = Form(None),
) -> dict:
    """上传并解析文件（兼容旧版 API，添加了安全检查）。"""
    filename = file.filename or ""
    if not filename:
        raise HTTPException(status_code=400, detail="未选择文件")

    # 1. 验证文件大小
    content_length = file.headers.get("content-length")
    if content_length:
        try:
            size = int(content_length)
            if not validate_file_size(size):
                cfg = get_config()
                max_size = cfg.security.max_upload_size
                raise HTTPException(
                    status_code=413,
                    detail=f"文件过大，最大允许 {max_size // (1024*1024)}MB"
                )
        except ValueError:
            pass

    # 2. 验证文件扩展名
    is_allowed, ext = validate_file_extension(filename)
    if not is_allowed:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}"
        )

    # 3. 读取文件内容（安全方式）
    content_bytes = await file.read()

    # 二次检查文件大小
    if not validate_file_size(len(content_bytes)):
        cfg = get_config()
        max_size = cfg.security.max_upload_size
        raise HTTPException(
            status_code=413,
            detail=f"文件过大，最大允许 {max_size // (1024*1024)}MB"
        )

    # 4. 保存到安全的临时位置
    safe_filename = sanitize_filename(filename)
    temp_dir = os.path.join(tempfile.gettempdir(), "storyforge_uploads")
    os.makedirs(temp_dir, mode=0o700, exist_ok=True)

    # 生成唯一文件名避免冲突
    import uuid
    unique_id = uuid.uuid4().hex[:12]
    safe_filepath = os.path.join(temp_dir, f"{unique_id}_{safe_filename}")

    try:
        with open(safe_filepath, "wb") as fout:
            fout.write(content_bytes)

        # 5. 解析文件
        options: Dict[str, Any] = {}
        if chapter_pattern:
            options["chapter_pattern"] = chapter_pattern
        if ocr_language:
            options["ocr_language"] = ocr_language
        if merge_chapters is not None:
            options["merge_chapters"] = merge_chapters

        from stages.importer.novel_importer import NovelImporter

        importer = NovelImporter()
        result = importer.parse(safe_filepath, **options)

        if not result.success:
            raise HTTPException(
                status_code=422,
                detail={
                    "success": False,
                    "errors": result.errors,
                    "warnings": result.warnings,
                },
            )

        return {
            "success": True,
            "preview": {
                "title": result.novel_title,
                "author": result.author,
                "genre": result.genre,
                "total_chapters": result.total_chapters,
                "total_word_count": result.total_word_count,
                "chapters": [
                    {
                        "chapter_num": ch.chapter_num,
                        "title": ch.title,
                        "word_count": ch.word_count,
                        "preview": ch.content[:200] if ch.content else "",
                    }
                    for ch in result.chapters[:10]
                ],
            },
            "warnings": result.warnings,
            "full_result": {
                "chapters": [
                    {
                        "chapter_num": ch.chapter_num,
                        "title": ch.title,
                        "content": ch.content,
                        "word_count": ch.word_count,
                    }
                    for ch in result.chapters
                ],
                "metadata": result.metadata,
            },
        }
    finally:
        # 6. 清理临时文件
        try:
            os.unlink(safe_filepath)
        except Exception:
            pass


@router.post("/api/import/save")
async def save_imported(
    req: SaveImportedRequest,
    sm: StorageManager = Depends(get_storage_manager_dep),
) -> dict:
    """保存导入的内容为新小说（兼容旧版 API，添加了安全检查）。"""
    if not req.chapters:
        raise HTTPException(status_code=400, detail="缺少章节数据")

    novel_id = (req.novel_id or "").strip()
    if not novel_id:
        from datetime import datetime
        safe_title = "".join(c for c in req.title if c.isalnum() or c == "_")
        novel_id = f"{safe_title or 'imported'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # 使用安全的 novel_id
    novel_id = safe_novel_id(novel_id)

    # 检查小说是否已存在
    if sm.novel_exists(novel_id):
        raise HTTPException(status_code=409, detail=f"小说已存在: {novel_id}")

    meta = NovelMeta(
        novel_id=novel_id,
        novel_title=req.title,
        genre=req.genre,
        concept=req.concept,
        target_word_count=max(
            sum(len(ch.get("content", "")) for ch in req.chapters) // max(len(req.chapters), 1),
            3000,
        ),
        current_stage=PipelineStage.CREATION,
    )
    sm.save_novel_meta(novel_id, meta)

    chapters: Dict[int, Chapter] = {}
    for ch in req.chapters:
        num = int(ch.get("chapter_num", 1))
        chapters[num] = Chapter(
            novel_id=novel_id,
            chapter_num=num,
            title=str(ch.get("title", "")),
            content=str(ch.get("content", "")),
            status=ChapterStatus.DRAFT,
        )
    sm.save_chapters(novel_id, chapters)

    meta.total_chapters = len(chapters)
    meta.draft_chapters = len(chapters)
    sm.save_novel_meta(novel_id, meta)

    return {
        "success": True,
        "novel_id": novel_id,
        "title": req.title,
        "chapter_count": len(chapters),
    }
