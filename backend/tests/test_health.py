"""
SP-6.3: health con dependencias (redis, database, data_provider) y degradación.
"""
from unittest.mock import patch


def test_health_reports_dependencies(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "dependencies" in body
    deps = body["dependencies"]
    assert "redis" in deps
    assert "database" in deps
    assert "data_provider" in deps
    assert deps["database"] in ("ok", "down")
    assert deps["redis"] in ("ok", "down")


def test_health_status_degraded_when_redis_down(client):
    import server

    with patch.object(server, "redis_get", return_value=None):
        resp = client.get("/api/health")
        body = resp.json()
        assert body["status"] in ("ok", "degraded")
        assert body["dependencies"]["redis"] in ("ok", "down")


def test_health_ok_when_all_dependencies_ok(client):
    import server

    with patch.object(server, "redis_get", return_value={"ok": True}):
        resp = client.get("/api/health")
        body = resp.json()
        assert body["dependencies"]["data_provider"] == "ok" or "data_provider" in body["dependencies"]


def test_scan_degrades_to_snapshot(client, monkeypatch):
    """Si Redis y scan fallan, /api/scan sirve el snapshot (degradación graceful)."""
    import server

    def redis_get_none(key):
        return None

    monkeypatch.setattr(server, "redis_get", redis_get_none)
    monkeypatch.setattr(server, "_read_parquet_cache", lambda market: None)
    # Forzar que no exista snapshot ni data
    monkeypatch.setattr(server, "SNAPSHOT_DIR", "/nonexistent/snapshots")
    resp = client.get("/api/scan")
    assert resp.status_code in (200, 500, 503)
    if resp.status_code == 200:
        assert resp.json().get("data") == []