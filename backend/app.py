"""
StoryForge - Flask 后端

提供 RESTful API 给前端展示小说清单和创作进展。

启动：
    python backend/app.py

API 端点：
    GET /api/health
    GET /api/novels
    GET /api/novels/<novel_id>
    GET /api/novels/<novel_id>/chapters
    GET /api/novels/<novel_id>/chapters/<chapter_num>
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_THIS_DIR)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from flask import Flask, jsonify, send_from_directory, request  # noqa: E402
from flask_cors import CORS  # noqa: E402
from werkzeug.utils import secure_filename  # noqa: E402

from core.config import get_config  # noqa: E402
from core.storage import StorageManager, StorageConfig  # noqa: E402
from core.models import (  # noqa: E402
    NovelMeta, PipelineStage,
    Chapter, ChapterStatus,
    Review, ReviewRecord, ReviewVerdict,
    Proofread, ProofreadRecord,
)


def _get_sm() -> StorageManager:
    """获取存储管理器实例。"""
    config = get_config()
    storage_config = StorageConfig(data_dir=config.data_dir_abs)
    return StorageManager(storage_config)


def create_app() -> Flask:
    cfg = get_config()

    client_build = os.path.join(_ROOT_DIR, "client", "build")
    app = Flask(
        __name__,
        static_folder=client_build if os.path.isdir(client_build) else None,
        static_url_path="",
    )

    CORS(app, resources={r"/api/*": {"origins": cfg.server.cors_origins}})

    # ==================== API ====================

    @app.get("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "config_path": cfg.config_path,
            "data_dir": cfg.data_dir_abs,
        })

    @app.get("/api/novels")
    def list_novels():
        sm = _get_sm()
        return jsonify(sm.list_novels())

    @app.get("/api/novels/<novel_id>")
    def get_novel(novel_id: str):
        sm = _get_sm()
        meta = sm.load_novel_meta(novel_id)
        if meta is None:
            return jsonify({"error": "novel not found", "novel_id": novel_id}), 404
        # Build response
        result = meta.to_index_entry()
        # Try to load characters
        characters_list = []
        try:
            char_graph = sm.load_characters(novel_id)
            if char_graph:
                if hasattr(char_graph, 'characters') and char_graph.characters:
                    for c in char_graph.characters:
                        char_dict = {}
                        # 优先尝试 to_dict
                        if hasattr(c, 'to_dict'):
                            try:
                                char_dict = c.to_dict()
                            except Exception:
                                pass
                        # 如果没有，则手动提取字段
                        if not char_dict:
                            char_dict = {
                                'id': getattr(c, 'character_id', getattr(c, 'id', '')),
                                'character_id': getattr(c, 'character_id', ''),
                                'name': getattr(c, 'name', ''),
                                'description': getattr(c, 'description', ''),
                                'personality': getattr(c, 'personality', ''),
                                'background': getattr(c, 'background', ''),
                                'age': getattr(c, 'age', None),
                                'gender': getattr(c, 'gender', ''),
                            }
                        characters_list.append(char_dict)
        except Exception as e:
            # 错误时不添加任何字符，但也不崩溃
            pass
        result['characters'] = characters_list
        return jsonify(result)

    @app.get("/api/novels/<novel_id>/chapters")
    def list_chapters(novel_id: str):
        sm = _get_sm()
        meta = sm.load_novel_meta(novel_id)
        if meta is None:
            return jsonify({"error": "novel not found", "novel_id": novel_id}), 404

        chapters = sm.load_chapters(novel_id)
        reviews = sm.load_reviews(novel_id)

        result = []
        for num in sorted(chapters.keys()):
            ch = chapters[num]
            review = reviews.get(num)
            latest = review.get_latest() if review else None
            result.append({
                "chapter_num": num,
                "title": ch.title,
                "status": ch.status.value,
                "word_count": ch.word_count,
                "preview": ch.get_preview(),
                "review_rounds": len(review.records) if review else 0,
                "latest_score": latest.total_score if latest else None,
                "latest_passed": latest.passed if latest else None,
            })

        return jsonify({
            "novel_id": novel_id,
            "current_chapter": meta.current_chapter,
            "total_chapters": meta.total_chapters,
            "chapters": result,
        })

    @app.get("/api/novels/<novel_id>/chapters/<int:chapter_num>")
    def get_chapter(novel_id: str, chapter_num: int):
        sm = _get_sm()
        meta = sm.load_novel_meta(novel_id)
        if meta is None:
            return jsonify({"error": "novel not found", "novel_id": novel_id}), 404

        chapters = sm.load_chapters(novel_id)
        ch = chapters.get(chapter_num)
        if ch is None:
            return jsonify({
                "error": "chapter not found",
                "novel_id": novel_id,
                "chapter_num": chapter_num,
            }), 404

        reviews = sm.load_reviews(novel_id)
        review = reviews.get(chapter_num)
        proofreads = sm.load_proofreads(novel_id)
        proofread = proofreads.get(chapter_num)

        return jsonify({
            "novel_id": novel_id,
            "chapter_num": chapter_num,
            "title": ch.title,
            "status": ch.status.value,
            "content": ch.content,
            "word_count": ch.word_count,
            "reviews": [r.to_dict() for r in (review.records if review else [])],
            "proofread_records": [p.to_dict() for p in (proofread.records if proofread else [])],
        })

    # ==================== 静态资源 ====================

    @app.get("/")
    def serve_index():
        if app.static_folder and os.path.exists(os.path.join(app.static_folder, "index.html")):
            return send_from_directory(app.static_folder, "index.html")
        return jsonify({
            "name": "StoryForge API",
            "config": {
                "data_dir": cfg.data_dir_abs,
                "config_path": cfg.config_path,
            },
            "endpoints": [
                "/api/health",
                "/api/novels",
                "/api/novels/<novel_id>",
                "/api/novels/<novel_id>/chapters",
                "/api/novels/<novel_id>/chapters/<chapter_num>",
            ],
        })

    # ==================== 小说导入 API ====================

    @app.get("/api/import/formats")
    def list_import_formats():
        from stages.importer.novel_importer import NovelImporter
        return jsonify({
            "formats": [
                {
                    "type": "text",
                    "name": "纯文本",
                    "extensions": ["txt", "md", "markdown", "html", "htm", "rst", "org"],
                    "description": "直接读取纯文本内容，支持自动章节识别"
                },
                {
                    "type": "epub",
                    "name": "EPUB 电子书",
                    "extensions": ["epub"],
                    "description": "解析 EPUB 章节结构和元数据"
                },
                {
                    "type": "pdf",
                    "name": "PDF 文档",
                    "extensions": ["pdf"],
                    "description": "提取 PDF 文字内容，扫描件建议使用图片导入"
                },
                {
                    "type": "image",
                    "name": "图片（OCR）",
                    "extensions": ["jpg", "jpeg", "png", "gif", "bmp", "tiff", "tif", "webp"],
                    "description": "通过 OCR 识别图片中的文字"
                },
            ]
        })

    @app.post("/api/import/upload")
    def upload_file():
        if "file" not in request.files:
            return jsonify({"error": "缺少文件"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "未选择文件"}), 400

        import tempfile
        upload_dir = os.path.join(tempfile.gettempdir(), "storyforge_uploads")
        os.makedirs(upload_dir, exist_ok=True)

        filename = secure_filename(file.filename)
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        options = {}
        if request.form.get("chapter_pattern"):
            options["chapter_pattern"] = request.form.get("chapter_pattern")
        if request.form.get("ocr_language"):
            options["ocr_language"] = request.form.get("ocr_language")
        if request.form.get("merge_chapters"):
            options["merge_chapters"] = request.form.get("merge_chapters") == "true"

        from stages.importer.novel_importer import NovelImporter
        importer = NovelImporter()
        result = importer.parse(filepath, **options)

        try:
            os.unlink(filepath)
        except Exception:
            pass

        if not result.success:
            return jsonify({
                "success": False,
                "errors": result.errors,
                "warnings": result.warnings,
            }), 422

        return jsonify({
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
            }
        })

    @app.post("/api/import/save")
    def save_imported():
        data = request.get_json()
        if not data or "chapters" not in data:
            return jsonify({"error": "缺少章节数据"}), 400

        novel_id = data.get("novel_id")
        title = data.get("title", "未命名")
        author = data.get("author", "")
        genre = data.get("genre", "未分类")
        concept = data.get("concept", "")
        chapters_data = data.get("chapters", [])

        if not novel_id:
            safe_title = "".join(c for c in title if c.isalnum() or c == "_")
            from datetime import datetime
            novel_id = f"{safe_title or 'imported'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        sm = _get_sm()

        # Create novel meta
        meta = NovelMeta(
            novel_id=novel_id,
            novel_title=title,
            genre=genre,
            concept=concept,
            target_word_count=max(sum(len(c.get("content", "")) for c in chapters_data) // max(len(chapters_data), 1), 3000),
            current_stage=PipelineStage.CREATION,
        )
        sm.save_novel_meta(novel_id, meta)

        # Create chapters
        chapters = {}
        for ch in chapters_data:
            num = ch.get("chapter_num", 1)
            chapters[num] = Chapter(
                novel_id=novel_id,
                chapter_num=num,
                title=ch.get("title", ""),
                content=ch.get("content", ""),
                status=ChapterStatus.DRAFT,
            )
        sm.save_chapters(novel_id, chapters)

        # Update meta with stats
        meta.total_chapters = len(chapters)
        meta.draft_chapters = len(chapters)
        sm.save_novel_meta(novel_id, meta)

        return jsonify({
            "success": True,
            "novel_id": novel_id,
            "title": title,
            "chapter_count": len(chapters),
        })

    # ==================== 静态资源 ====================

    @app.errorhandler(404)
    def fallback(_e):
        if app.static_folder and os.path.exists(os.path.join(app.static_folder, "index.html")):
            return send_from_directory(app.static_folder, "index.html")
        return jsonify({"error": "not found"}), 404

    return app


app = create_app()


if __name__ == "__main__":
    cfg = get_config()
    port = int(os.environ.get("PORT", cfg.server.port))
    host = os.environ.get("HOST", cfg.server.host)
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
