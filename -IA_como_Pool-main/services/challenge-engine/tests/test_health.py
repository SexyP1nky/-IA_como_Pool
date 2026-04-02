import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from src.main import app

client = TestClient(app)

@patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
@patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
def test_challenge_from_redis(mock_postgres, mock_redis):
	mock_redis.return_value = "desafio redis"
	mock_postgres.return_value = None
	response = client.get("/challenge")
	assert response.status_code == 200
	assert response.json() == {"challenge": "desafio redis", "source": "pool"}

@patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
@patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
def test_challenge_from_postgres(mock_postgres, mock_redis):
	mock_redis.return_value = None
	mock_postgres.return_value = "desafio pg"
	response = client.get("/challenge")
	assert response.status_code == 200
	assert response.json() == {"challenge": "desafio pg", "source": "static_fallback"}

@patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
@patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
def test_challenge_unavailable(mock_postgres, mock_redis):
	mock_redis.return_value = None
	mock_postgres.return_value = None
	response = client.get("/challenge")
	assert response.status_code == 503

import pytest

@pytest.mark.skip(reason="Integração real será implementada futuramente")
def test_integration_challenge_from_redis_and_postgres():
    """
    Exemplo de teste de integração para o endpoint /challenge.
    Quando as integrações estiverem prontas, remova o skip e implemente mocks reais de Redis/Postgres.
    """
    assert True
