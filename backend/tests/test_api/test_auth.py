import pytest
from tests.conftest import register_user, login_user, get_auth_headers


class TestAuthRegister:
    def test_register_success(self, client):
        response = register_user(client)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["email"] == "test@integration.com"
        assert data["is_active"] is True
        assert "id" in data

    def test_register_duplicate_email(self, client):
        register_user(client)
        response = register_user(client)
        assert response.status_code == 400, response.text
        assert "already registered" in response.json()["detail"]


class TestAuthLogin:
    def test_login_success(self, client):
        register_user(client)
        response = login_user(client)
        assert response.status_code == 200, response.text
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_password(self, client):
        register_user(client)
        response = client.post(
            "/api/auth/token",
            data={"username": "test@integration.com", "password": "WrongPassword"},
        )
        assert response.status_code == 401, response.text

    def test_login_nonexistent_user(self, client):
        response = login_user(client, email="noexiste@test.com")
        assert response.status_code == 401, response.text


class TestAuthProtectedEndpoint:
    def test_no_token_returns_401(self, client):
        response = client.get("/api/paper-trading/portfolio")
        assert response.status_code == 401, response.text

    def test_valid_token_accesses_protected_endpoint(self, client):
        register_user(client)
        headers = get_auth_headers(client)
        response = client.get("/api/paper-trading/portfolio", headers=headers)
        assert response.status_code in (200, 404), response.text

    def test_invalid_token_returns_401(self, client):
        headers = {"Authorization": "Bearer fake-token"}
        response = client.get("/api/paper-trading/portfolio", headers=headers)
        assert response.status_code == 401, response.text
