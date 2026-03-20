"""Testes para o endpoint GET /health."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_returns_200(client: TestClient):
    """GET /health deve retornar status 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_status_ok(client: TestClient):
    """GET /health deve retornar status 'ok'."""
    data = client.get("/health").json()
    assert data["status"] == "ok"


def test_health_returns_version(client: TestClient):
    """GET /health deve retornar version '0.12.0'."""
    data = client.get("/health").json()
    assert data["version"] == "0.12.0"


def test_health_database_connected_when_url_set(client: TestClient):
    """database deve ser 'connected' quando DATABASE_URL esta configurado."""
    with patch("src.api.routes.health.settings") as mock_settings:
        mock_settings.DATABASE_URL = "postgresql://localhost/test"
        mock_settings.EVOLUTION_API_URL = ""
        mock_settings.EVOLUTION_API_KEY = ""
        response = client.get("/health")
        assert response.json()["database"] == "connected"


def test_health_database_disconnected_when_url_empty(client: TestClient):
    """database deve ser 'disconnected' quando DATABASE_URL esta vazio."""
    with patch("src.api.routes.health.settings") as mock_settings:
        mock_settings.DATABASE_URL = ""
        mock_settings.EVOLUTION_API_URL = ""
        mock_settings.EVOLUTION_API_KEY = ""
        response = client.get("/health")
        assert response.json()["database"] == "disconnected"


def test_health_evolution_configured_when_credentials_set(client: TestClient):
    """evolution deve ser 'configured' quando URL e API_KEY estao definidos."""
    with patch("src.api.routes.health.settings") as mock_settings:
        mock_settings.DATABASE_URL = ""
        mock_settings.EVOLUTION_API_URL = "http://localhost:8080"
        mock_settings.EVOLUTION_API_KEY = "my-api-key"
        response = client.get("/health")
        assert response.json()["evolution"] == "configured"


def test_health_evolution_not_configured_when_missing_url(client: TestClient):
    """evolution deve ser 'not_configured' quando EVOLUTION_API_URL esta vazio."""
    with patch("src.api.routes.health.settings") as mock_settings:
        mock_settings.DATABASE_URL = ""
        mock_settings.EVOLUTION_API_URL = ""
        mock_settings.EVOLUTION_API_KEY = "my-api-key"
        response = client.get("/health")
        assert response.json()["evolution"] == "not_configured"


def test_health_evolution_not_configured_when_missing_key(client: TestClient):
    """evolution deve ser 'not_configured' quando EVOLUTION_API_KEY esta vazio."""
    with patch("src.api.routes.health.settings") as mock_settings:
        mock_settings.DATABASE_URL = ""
        mock_settings.EVOLUTION_API_URL = "http://localhost:8080"
        mock_settings.EVOLUTION_API_KEY = ""
        response = client.get("/health")
        assert response.json()["evolution"] == "not_configured"


def test_health_chatwoot_configured_when_credentials_set(client: TestClient):
    """chatwoot deve ser 'configured' quando URL e API_KEY estao definidos."""
    with patch("src.api.routes.health.settings") as mock_settings:
        mock_settings.DATABASE_URL = ""
        mock_settings.EVOLUTION_API_URL = ""
        mock_settings.EVOLUTION_API_KEY = ""
        mock_settings.CHATWOOT_API_URL = "http://chatwoot:3000"
        mock_settings.CHATWOOT_API_KEY = "my-chatwoot-key"
        response = client.get("/health")
        assert response.json()["chatwoot"] == "configured"


def test_health_chatwoot_not_configured_when_missing(client: TestClient):
    """chatwoot deve ser 'not_configured' quando credenciais estao vazias."""
    with patch("src.api.routes.health.settings") as mock_settings:
        mock_settings.DATABASE_URL = ""
        mock_settings.EVOLUTION_API_URL = ""
        mock_settings.EVOLUTION_API_KEY = ""
        mock_settings.CHATWOOT_API_URL = ""
        mock_settings.CHATWOOT_API_KEY = ""
        response = client.get("/health")
        assert response.json()["chatwoot"] == "not_configured"


def test_health_response_has_all_fields(client: TestClient):
    """GET /health deve retornar exatamente os 5 campos esperados."""
    data = client.get("/health").json()
    assert set(data.keys()) == {"status", "version", "database", "evolution", "chatwoot"}
