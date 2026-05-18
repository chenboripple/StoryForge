"""web_console 网关冒烟测试。

确保拆分后的 FastAPI 应用：
- 能正常加载（无 import 错误、无循环依赖）；
- 路由数量与拆分前一致；
- 健康检查、列表类只读端点返回预期状态码与字段。

不覆盖：实际执行 pipeline 子进程、调用真实 LLM、文件上传等需要外部依赖的路径。
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def _client():
    from web_console.app import app

    return TestClient(app)


def test_app_loads_with_expected_routes():
    from web_console.app import app

    paths = sorted({getattr(r, "path", "") for r in app.routes if hasattr(r, "path")})
    expected = {
        "/api/v1/config",
        "/api/v1/health",
        "/api/v1/ai/generate",
        "/api/v1/templates",
        "/api/v1/tasks",
        "/api/v1/tasks/{task_id}",
        "/api/v1/tasks/{task_id}/stop",
        "/api/v1/novels",
        "/api/v1/novels/{novel_id}",
        "/api/v1/novels/{novel_id}/proposals",
        "/api/v1/novels/{novel_id}/context-decisions",
        "/api/v1/novels/{novel_id}/chapters",
        "/api/v1/novels/{novel_id}/chapters/{chapter_num}",
        "/api/v1/novels/{novel_id}/characters",
        "/api/v1/import/formats",
        "/api/v1/import/upload",
        "/api/v1/import/save",
        "/api/v1/ip/{novel_id}/story_bible",
        "/api/v1/ip/{novel_id}/character/{character_id}",
        "/api/v1/video/{novel_id}/script/generate",
        "/api/v1/video/{novel_id}/consistency/check",
        "/api/v1/video/{novel_id}/consistency",
    }
    missing = expected - set(paths)
    assert not missing, f"missing routes after refactor: {missing}"


def test_api_health_ok():
    client = _client()
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("status") == "ok"
    assert "running_tasks" in body


def test_health_endpoint_removed():
    client = _client()
    resp = client.get("/health")
    assert resp.status_code == 404


def test_legacy_api_prefix_returns_410():
    client = _client()

    resp = client.get("/api")
    assert resp.status_code == 410
    assert resp.json().get("error") == "gone"

    for method, path in [
        (client.get, "/api/novels"),
        (client.get, "/api/tasks"),
        (client.post, "/api/tasks/start"),
        (client.get, "/api/import/formats"),
    ]:
        r = method(path)
        assert r.status_code == 410
        assert r.json().get("error") == "gone"


def test_api_config_returns_console_caps():
    client = _client()
    resp = client.get("/api/v1/config")
    assert resp.status_code == 200
    body = resp.json()
    assert "max_running_tasks" in body
    assert "running_tasks" in body
    assert "queued_tasks" in body


def test_api_tasks_returns_list_shape():
    client = _client()
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("tasks"), list)


def test_api_templates_returns_list_shape():
    client = _client()
    resp = client.get("/api/v1/templates")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body.get("templates"), list)


def test_api_novels_rejects_missing_dir():
    client = _client()
    resp = client.get("/api/v1/novels", params={"project_dir": "/does/not/exist/abc123"})
    assert resp.status_code == 400


def test_api_import_formats_lists_supported_types():
    client = _client()
    resp = client.get("/api/v1/import/formats")
    assert resp.status_code == 200
    formats = resp.json().get("formats", [])
    types = {f.get("type") for f in formats}
    assert {"text", "epub", "pdf", "image"} <= types


def test_root_returns_index_or_404_when_no_build():
    """有 build → 200 + HTML；无 build → 404 + 友好提示。"""
    from pathlib import Path

    client = _client()
    resp = client.get("/")
    client_build = Path(__file__).resolve().parent.parent / "client" / "build" / "index.html"
    if client_build.exists():
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
    else:
        assert resp.status_code == 404
        body = resp.json()
        assert "expected_path" in body


def test_progressive_endpoints_return_404_without_checkpoint():
    client = _client()
    for path in [
        "/api/v1/novels/nonexistent/proposals",
        "/api/v1/novels/nonexistent/context-decisions",
    ]:
        resp = client.get(path)
        assert resp.status_code == 404
