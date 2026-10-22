from fastapi.testclient import TestClient

from app.api.main import ApiError, app


@app.get("/_test/boom", include_in_schema=False)
def _boom():
    raise RuntimeError("секрет не должен утечь")


@app.get("/_test/api-error", include_in_schema=False)
def _api_error():
    raise ApiError(403, "forbidden", "нет доступа")


client = TestClient(app, raise_server_exceptions=False)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["ok"] is True and r.json()["llm_mode"] == "stub"
    assert r.headers["X-Trace-Id"]


def test_openapi_available():
    r = client.get("/openapi.json")
    assert r.status_code == 200 and "/health" in r.json()["paths"]


def test_errors_have_single_format_and_trace_id():
    for path, status, code in (("/nope", 404, "not_found"), ("/_test/api-error", 403, "forbidden"),
                               ("/_test/boom", 500, "internal_error")):
        r = client.get(path, headers={"X-Trace-Id": "t-123"})
        body = r.json()["error"]
        assert r.status_code == status and body["code"] == code and body["trace_id"] == "t-123"
        assert "секрет" not in body["message"]


def test_cors_for_frontend():
    r = client.options("/health", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"
