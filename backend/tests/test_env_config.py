import os

from app.db.database import DATABASE_URL, engine
from app.config import settings


def test_database_url_comes_from_settings():
    """La URL de la DB debe venir de settings (que lee el .env), no de un default local."""
    assert DATABASE_URL == settings.DATABASE_URL
    assert "iosef_finance.db" in DATABASE_URL


def test_database_url_not_empty_default():
    assert "sqlite" in DATABASE_URL or "postgres" in DATABASE_URL


def test_engine_uses_database_url():
    url = str(engine.url)
    assert "iosef_finance" in url or url == DATABASE_URL


def test_health_reports_database_path(client):
    """El endpoint /api/health debe exponer la ruta de la DB activa (SP-3.2)."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "database" in body
    assert "test_iosef.db" in body["database"]


def test_env_file_exists_and_has_database_url():
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    assert os.path.exists(env_path)
    content = open(env_path).read()
    assert "DATABASE_URL=" in content