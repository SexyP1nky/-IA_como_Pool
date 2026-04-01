import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, PropertyMock
from src.integrations.redis import MockRedisClient
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


@patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
def test_challenge_from_redis(mock_postgres):
    mock_redis_client = MockRedisClient()

    async def _seed():
        from src.generators.challenge_generator import (
            Challenge, ChallengeType, ChallengeLevel,
        )
        ch = Challenge(
            id="r1", type=ChallengeType.ALGORITHM, level=ChallengeLevel.EASY,
            title="T", description="D", example_input="i", example_output="o",
            created_at="2025-01-01",
        )
        await mock_redis_client.push_challenge(ch)

    import asyncio
    asyncio.get_event_loop().run_until_complete(_seed())

    main_module.redis_client = mock_redis_client
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
