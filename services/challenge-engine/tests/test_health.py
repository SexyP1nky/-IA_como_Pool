from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from src.main import app


client = TestClient(app)


def test_health_endpoint_returns_healthy():
    # Confirma que a API está de pé para os demais testes.
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
@patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
def test_challenge_from_redis(mock_postgres, mock_redis):
    # Fluxo principal: se houver item no Redis, ele deve ser retornado direto.
    mock_redis.return_value = "desafio redis"
    mock_postgres.return_value = None

    response = client.get("/challenge")

    assert response.status_code == 200
    assert response.json() == {"challenge": "desafio redis", "source": "pool"}


@patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
@patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
def test_challenge_from_postgres(mock_postgres, mock_redis):
    # Fallback: sem dado no Redis, a API deve tentar o PostgreSQL.
    mock_redis.return_value = None
    mock_postgres.return_value = "desafio pg"

    response = client.get("/challenge")

    assert response.status_code == 200
    assert response.json() == {"challenge": "desafio pg", "source": "static_fallback"}


@patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
@patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
def test_challenge_unavailable(mock_postgres, mock_redis):
    # Indisponibilidade total: sem Redis e sem PostgreSQL, retorna 503.
    mock_redis.return_value = None
    mock_postgres.return_value = None

    response = client.get("/challenge")

    assert response.status_code == 503
    assert response.json() == {"detail": "No challenge available."}
