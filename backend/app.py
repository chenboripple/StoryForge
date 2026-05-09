"""
Legacy backend entrypoint (sunset).

StoryForge has consolidated API gateway responsibilities into FastAPI:
    web_console/app.py

Use:
    uvicorn web_console.app:app --reload --port 8787
"""

from __future__ import annotations

from flask import Flask, jsonify


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def root():
        return jsonify(
            {
                "ok": False,
                "deprecated": True,
                "message": "Flask backend has been sunset. Use FastAPI gateway at web_console.app.",
                "run": "uvicorn web_console.app:app --reload --port 8787",
            }
        ), 410

    @app.route("/api/<path:_path>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def api_sunset(_path: str):
        return jsonify(
            {
                "ok": False,
                "deprecated": True,
                "message": "API has moved to FastAPI gateway (web_console.app).",
            }
        ), 410

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5089, debug=False)
