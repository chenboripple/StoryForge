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

from flask import Flask, jsonify, send_from_directory  # noqa: E402
from flask_cors import CORS  # noqa: E402

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
