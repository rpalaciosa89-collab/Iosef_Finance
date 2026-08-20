import os

from fastapi.testclient import TestClient


def test_cors_allow_configured_origin(client):
    """Un origen configurado en CORS_ORIGINS debe recibir Access-Control-Allow-Origin."""
    resp = client.get(
        "/api/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_reject_unknown_origin(client):
    """Un origen no configurado NO debe recibir Access-Control-Allow-Origin."""
    resp = client.get(
        "/api/health",
        headers={"Origin": "http://evil.example.com"},
    )
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


def test_cors_single_source_of_truth():
    """El CORS se lee de CORS_ORIGINS (env). No debe existir un segundo entrypoint."""
    from app.config import settings

    assert "BACKEND_CORS_ORIGINS" not in os.environ or settings.BACKEND_CORS_ORIGINS
    main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "main.py")
    assert not os.path.exists(main_py), "app/main.py debe eliminarse (entrypoint duplicado)"


def test_entrypoint_canonico_es_server():
    import server

    assert hasattr(server, "app")