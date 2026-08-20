import pytest
from tests.conftest import register_user, login_user, get_auth_headers


class TestPaperAccount:
    def test_create_account(self, client):
        register_user(client)
        headers = get_auth_headers(client)
        response = client.post(
            "/api/paper-trading/account",
            json={"name": "Test Account", "initial_balance": 100000},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["name"] == "Test Account"
        assert data["initial_balance"] == 100000
        assert data["cash_balance"] == 100000
        assert data["is_active"] is True

    def test_create_duplicate_account_fails(self, client):
        register_user(client)
        headers = get_auth_headers(client)
        client.post(
            "/api/paper-trading/account",
            json={"name": "Test Account", "initial_balance": 100000},
            headers=headers,
        )
        response = client.post(
            "/api/paper-trading/account",
            json={"name": "Second Account", "initial_balance": 50000},
            headers=headers,
        )
        assert response.status_code == 400, response.text
        assert "already exists" in response.json()["detail"]

    def test_create_account_unauthorized(self, client):
        response = client.post(
            "/api/paper-trading/account",
            json={"name": "Test Account", "initial_balance": 100000},
        )
        assert response.status_code == 401, response.text


class TestPaperPortfolio:
    def test_empty_portfolio(self, client):
        register_user(client)
        headers = get_auth_headers(client)
        response = client.get("/api/paper-trading/portfolio", headers=headers)
        assert response.status_code == 404, response.text

    def test_portfolio_after_account_creation(self, client):
        register_user(client)
        headers = get_auth_headers(client)
        client.post(
            "/api/paper-trading/account",
            json={"name": "Test", "initial_balance": 100000},
            headers=headers,
        )
        response = client.get("/api/paper-trading/portfolio", headers=headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["account"]["name"] == "Test"
        assert data["account"]["cash_balance"] == 100000
        assert data["open_positions"] == []
        assert data["total_equity"] == 100000

    def test_portfolio_unauthorized(self, client):
        response = client.get("/api/paper-trading/portfolio")
        assert response.status_code == 401, response.text


class TestPaperExecuteTrade:
    @pytest.fixture(autouse=True)
    def setup_account(self, client):
        register_user(client)
        self.headers = get_auth_headers(client)
        client.post(
            "/api/paper-trading/account",
            json={"name": "Test", "initial_balance": 100000},
            headers=self.headers,
        )

    def test_execute_buy_trade(self, client):
        response = client.post(
            "/api/paper-trading/execute",
            json={
                "ticker": "AAPL",
                "direction": "LONG",
                "quantity": 10,
                "entry_price": 150.0,
            },
            headers=self.headers,
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["ticker"] == "AAPL"
        assert data["direction"] == "LONG"
        assert data["quantity"] == 10
        assert data["entry_price"] == 150.0

    def test_execute_trade_unauthorized(self, client):
        client.cookies.clear()
        response = client.post(
            "/api/paper-trading/execute",
            json={
                "ticker": "AAPL",
                "direction": "LONG",
                "quantity": 10,
                "entry_price": 150.0,
            },
        )
        assert response.status_code == 401, response.text

    def test_execute_trade_no_account(self, client):
        register_user(client, email="noaccount@test.com")
        headers = get_auth_headers(client, email="noaccount@test.com")
        response = client.post(
            "/api/paper-trading/execute",
            json={
                "ticker": "AAPL",
                "direction": "LONG",
                "quantity": 10,
                "entry_price": 150.0,
            },
            headers=headers,
        )
        assert response.status_code == 400, response.text


class TestPaperRefresh:
    @pytest.fixture(autouse=True)
    def setup_account_and_trade(self, client):
        register_user(client)
        self.headers = get_auth_headers(client)
        client.post(
            "/api/paper-trading/account",
            json={"name": "Test", "initial_balance": 100000},
            headers=self.headers,
        )
        client.post(
            "/api/paper-trading/execute",
            json={
                "ticker": "AAPL",
                "direction": "LONG",
                "quantity": 10,
                "entry_price": 150.0,
            },
            headers=self.headers,
        )

    def test_refresh_positions(self, client):
        response = client.post("/api/paper-trading/refresh", headers=self.headers)
        assert response.status_code == 200, response.text
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert data[0]["ticker"] == "AAPL"

    def test_refresh_unauthorized(self, client):
        client.cookies.clear()
        response = client.post("/api/paper-trading/refresh")
        assert response.status_code == 401, response.text
