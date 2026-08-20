import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base, get_db

# Registro explicito de TODOS los modelos para que la metadata este completa
# (evita NoReferencedTableError cuando otros test files importan schemas antes).
from app.models.user import User  # noqa: F401,E402
from app.models.paper_trading import (  # noqa: F401,E402
    PaperAccount, PaperPosition, PaperTrade,
)

TEST_DATABASE_URL = "sqlite:///./test_iosef.db"

test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function", autouse=True)
def disable_rate_limiting():
    from app.config import settings
    original_window = settings.AUTH_RATE_LIMIT_WINDOW
    original_requests = settings.AUTH_RATE_LIMIT_REQUESTS
    settings.AUTH_RATE_LIMIT_WINDOW = 1
    settings.AUTH_RATE_LIMIT_REQUESTS = 999999
    yield
    settings.AUTH_RATE_LIMIT_WINDOW = original_window
    settings.AUTH_RATE_LIMIT_REQUESTS = original_requests


@pytest.fixture(scope="function")
def db_session():
    # Limpiar estado residual de corridas previas (evita flakiness del registro)
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def client(db_session):
    os.environ.setdefault("JWT_SECRET_KEY", "integration-test-secret-key")
    os.environ.setdefault("REDIS_HOST", "localhost")
    os.environ.setdefault("REDIS_PORT", "6379")

    import server
    import app.db.database as db_mod

    server.engine = test_engine
    db_mod.engine = test_engine

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    server.app.dependency_overrides[get_db] = override_get_db

    with TestClient(server.app) as tc:
        yield tc

    server.app.dependency_overrides.clear()

def register_user(client, email="test@integration.com", password="TestPass123!"):
    return client.post("/api/auth/register", json={"email": email, "password": password})

def login_user(client, email="test@integration.com", password="TestPass123!"):
    return client.post(
        "/api/auth/token",
        data={"username": email, "password": password},
    )

def get_auth_headers(client, email="test@integration.com", password="TestPass123!"):
    response = login_user(client, email, password)
    token = response.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}
