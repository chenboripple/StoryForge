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

# 解决独立脚本运行时的 import 问题
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_THIS_DIR)
if _ROOT_DIR not in sys.path:
    sys.path.insert(0, _ROOT_DIR)

from flask import Flask, jsonify, send_from_directory, request  # noqa: E402
from flask_cors import CORS  # noqa: E402
from werkzeug.utils import secure_filename  # noqa: E402

from backend import storage  # noqa: E402
from core.config import get_config  # noqa: E402


def create_app() -> Flask:
    cfg = get_config()

    # 静态文件目录指向 client/build（生产模式时使用）
    client_build = os.path.join(_ROOT_DIR, "client", "build")
    app = Flask(
        __name__,
        static_folder=client_build if os.path.isdir(client_build) else None,
        static_url_path="",
    )

    # 跨域配置（来自配置文件）
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
        return jsonify(storage.list_novels())

    @app.get("/api/novels/<novel_id>")
    def get_novel(novel_id: str):
        state = storage.load_novel(novel_id)
        if state is None:
            return jsonify({"error": "novel not found", "novel_id": novel_id}), 404
        return jsonify(state.to_dict())

    @app.get("/api/novels/<novel_id>/chapters")
    def list_chapters(novel_id: str):
        state = storage.load_novel(novel_id)
        if state is None:
            return jsonify({"error": "novel not found", "novel_id": novel_id}), 404

        chapters = []
        # 按章节号排序输出
        for num in sorted(state.chapters.keys()):
            content = state.chapters[num] or ""
            status = state.chapter_status.get(num)
            reviews = state.reviews.get(num, [])
            latest_review = reviews[-1] if reviews else None
            chapters.append({
                "chapter_num": num,
                "status": status.value if status else "pending",
                "word_count": len(content),
                "preview": content[:120],
                "review_rounds": len(reviews),
                "latest_score": latest_review.score if latest_review else None,
                "latest_passed": latest_review.passed if latest_review else None,
            })
        return jsonify({
            "novel_id": novel_id,
            "current_chapter": state.current_chapter,
            "chapters": chapters,
        })

    @app.get("/api/novels/<novel_id>/chapters/<int:chapter_num>")
    def get_chapter(novel_id: str, chapter_num: int):
        state = storage.load_novel(novel_id)
        if state is None:
            return jsonify({"error": "novel not found", "novel_id": novel_id}), 404
        if chapter_num not in state.chapters:
            return jsonify({
                "error": "chapter not found",
                "novel_id": novel_id,
                "chapter_num": chapter_num,
            }), 404

        status = state.chapter_status.get(chapter_num)
        reviews = state.reviews.get(chapter_num, [])
        proofreads = state.proofread_records.get(chapter_num, [])

        return jsonify({
            "novel_id": novel_id,
            "chapter_num": chapter_num,
            "status": status.value if status else "pending",
            "content": state.chapters[chapter_num],
            "word_count": len(state.chapters[chapter_num]),
            "reviews": [
                {
                    "round": r.round,
                    "reviewer": r.reviewer,
                    "score": r.score,
                    "comments": r.comments,
                    "passed": r.passed,
                    "timestamp": r.timestamp,
                }
                for r in reviews
            ],
            "proofread_records": [
                {
                    "round": p.round,
                    "proofreader": p.proofreader,
                    "comments": p.comments,
                    "passed": p.passed,
                    "timestamp": p.timestamp,
                }
                for p in proofreads
            ],
        })

    # ==================== 静态资源（生产模式） ====================

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
        """获取支持的导入格式"""
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
        """上传文件并解析"""
        if "file" not in request.files:
            return jsonify({"error": "缺少文件"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "未选择文件"}), 400

        # 保存上传文件
        import tempfile
        upload_dir = os.path.join(tempfile.gettempdir(), "storyforge_uploads")
        os.makedirs(upload_dir, exist_ok=True)

        filename = secure_filename(file.filename)
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        # 获取解析选项
        options = {}
        if request.form.get("chapter_pattern"):
            options["chapter_pattern"] = request.form.get("chapter_pattern")
        if request.form.get("ocr_language"):
            options["ocr_language"] = request.form.get("ocr_language")
        if request.form.get("merge_chapters"):
            options["merge_chapters"] = request.form.get("merge_chapters") == "true"

        # 解析文件
        from stages.importer.novel_importer import NovelImporter
        importer = NovelImporter()
        result = importer.parse(filepath, **options)

        # 清理临时文件
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

        # 返回解析结果（预览用）
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
                    for ch in result.chapters[:10]  # 最多返回10章预览
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
        """保存导入的小说到存储层"""
        data = request.get_json()
        if not data or "chapters" not in data:
            return jsonify({"error": "缺少章节数据"}), 400

        novel_id = data.get("novel_id")
        title = data.get("title", "未命名")
        author = data.get("author", "")
        genre = data.get("genre", "未分类")
        concept = data.get("concept", "")
        chapters_data = data.get("chapters", [])

        # 构建 NovelState
        from core.state import NovelState

        chapters = {}
        chapter_status = {}
        for ch in chapters_data:
            num = ch.get("chapter_num", 1)
            chapters[num] = ch.get("content", "")
            chapter_status[num] = "draft"

        if not novel_id:
            safe_title = "".join(c for c in title if c.isalnum() or c == "_")
            from datetime import datetime
            novel_id = f"{safe_title or 'imported'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        state = NovelState(
            novel_id=novel_id,
            novel_title=title,
            genre=genre,
            current_chapter=1,
            concept=concept,
            outline="",
            chapters=chapters,
            chapter_status=chapter_status,
            target_word_count=max(sum(len(c) for c in chapters.values()) // max(len(chapters), 1), 3000),
        )

        try:
            storage.save_novel(state)
            return jsonify({
                "success": True,
                "novel_id": novel_id,
                "title": title,
                "chapter_count": len(chapters),
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e),
            }), 500

    # ==================== 静态资源（生产模式） ====================

    @app.errorhandler(404)
    def fallback(_e):
        # SPA fallback：未匹配的路径都交给 index.html（如果存在）
        if app.static_folder and os.path.exists(os.path.join(app.static_folder, "index.html")):
            return send_from_directory(app.static_folder, "index.html")
        return jsonify({"error": "not found"}), 404

    return app


app = create_app()


if __name__ == "__main__":
    cfg = get_config()
    # 默认使用配置文件中的 host/port，可通过环境变量覆盖
    port = int(os.environ.get("PORT", cfg.server.port))
    host = os.environ.get("HOST", cfg.server.host)
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug)
