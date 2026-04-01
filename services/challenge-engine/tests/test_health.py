import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from src.integrations.redis import MockRedisClient
from src.generators.challenge_generator import (
    Challenge, ChallengeType, ChallengeLevel,
)
from src.main import app
import src.main as main_module


@pytest.fixture(autouse=True)
def _reset_globals():
    """Garante estado limpo entre testes."""
    original_client = main_module.redis_client
    original_service = main_module.challenge_service
    yield
    main_module.redis_client = original_client
    main_module.challenge_service = original_service


client = TestClient(app)


def _make_challenge(id: str = "test-1") -> Challenge:
    return Challenge(
        id=id, type=ChallengeType.ALGORITHM, level=ChallengeLevel.EASY,
        title="T", description="D", example_input="i", example_output="o",
        created_at="2025-01-01",
    )


# ── Health Check ─────────────────────────────────────────


def test_health_with_redis_connected():
    mock_redis = MockRedisClient()
    main_module.redis_client = mock_redis
    response = client.get("/health")
    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "healthy"
    assert data["redis"]["connected"] is True
    assert data["redis"]["pool_size"] == 0


def test_health_with_redis_and_pool():
    mock_redis = MockRedisClient()
    asyncio.run(mock_redis.push_challenge(_make_challenge()))
    main_module.redis_client = mock_redis
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "healthy"
    assert data["redis"]["pool_size"] == 1


def test_health_without_redis():
    main_module.redis_client = None
    response = client.get("/health")
    data = response.json()
    assert response.status_code == 200
    assert data["status"] == "degraded"
    assert data["redis"]["connected"] is False


# ── GET /challenge ───────────────────────────────────────


@patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
def test_challenge_from_redis(mock_postgres):
    mock_redis = MockRedisClient()
    asyncio.run(mock_redis.push_challenge(_make_challenge()))
    main_module.redis_client = mock_redis
    mock_postgres.return_value = None

    response = client.get("/challenge")
    assert response.status_code == 200
    assert response.json()["source"] == "pool"


@patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
def test_challenge_from_postgres(mock_postgres):
    main_module.redis_client = None
    mock_postgres.return_value = "desafio pg"
    response = client.get("/challenge")
    assert response.status_code == 200
    assert response.json() == {"challenge": "desafio pg", "source": "static_fallback"}


@patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
def test_challenge_unavailable(mock_postgres):
    main_module.redis_client = None
    mock_postgres.return_value = None
    response = client.get("/challenge")
    assert response.status_code == 503
