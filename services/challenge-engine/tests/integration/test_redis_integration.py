"""
Testes de integração com Redis real.

Requer Redis rodando (docker-compose up -d redis).
Rodar com:  pytest tests/integration/ -v -m integration
Pular com:  pytest -m "not integration"
"""
import json
import os
import pytest
import pytest_asyncio

from src.integrations.redis import RedisClientImpl, RedisConnectionError
from src.generators.challenge_generator import (
    Challenge,
    ChallengeType,
    ChallengeLevel,
)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TEST_KEY = "test_integration_pool"


def _make_challenge(id: str = "int-1") -> Challenge:
    return Challenge(
        id=id,
        type=ChallengeType.ALGORITHM,
        level=ChallengeLevel.EASY,
        title="Integration Test Challenge",
        description="Testing real Redis connection",
        example_input="[1,2]",
        example_output="3",
        created_at="2026-01-01T00:00:00",
    )


def _can_reach_redis() -> bool:
    """Tenta ping no Redis para decidir se os testes devem rodar."""
    import asyncio

    async def _ping():
        client = RedisClientImpl.from_url(REDIS_URL, key=TEST_KEY)
        try:
            await client.connect()
            await client.close()
            return True
        except Exception:
            return False

    return asyncio.run(_ping())


skip_no_redis = pytest.mark.skipif(
    not _can_reach_redis(),
    reason=f"Redis não acessível em {REDIS_URL} (rode: docker-compose up -d redis)",
)


@pytest_asyncio.fixture
async def redis_client():
    """Cria client conectado ao Redis real e limpa a key de teste."""
    client = RedisClientImpl.from_url(REDIS_URL, key=TEST_KEY)
    await client.connect()
    if client.redis:
        await client.redis.delete(TEST_KEY)
    yield client
    if client.redis:
        await client.redis.delete(TEST_KEY)
    await client.close()


@pytest.mark.integration
@skip_no_redis
@pytest.mark.asyncio
async def test_ping(redis_client):
    assert await redis_client.ping() is True


@pytest.mark.integration
@skip_no_redis
@pytest.mark.asyncio
async def test_push_and_pop(redis_client):
    ch = _make_challenge("push-pop-1")
    await redis_client.push_challenge(ch)

    size = await redis_client.get_pool_size()
    assert size == 1

    raw = await redis_client.get_challenge()
    assert raw is not None
    data = json.loads(raw)
    assert data["id"] == "push-pop-1"
    assert data["type"] == "algorithm"

    size = await redis_client.get_pool_size()
    assert size == 0


@pytest.mark.integration
@skip_no_redis
@pytest.mark.asyncio
async def test_batch_push(redis_client):
    challenges = [_make_challenge(f"batch-{i}") for i in range(10)]
    await redis_client.push_challenges_batch(challenges)

    size = await redis_client.get_pool_size()
    assert size == 10


@pytest.mark.integration
@skip_no_redis
@pytest.mark.asyncio
async def test_fifo_order(redis_client):
    for i in range(5):
        await redis_client.push_challenge(_make_challenge(f"fifo-{i}"))

    for i in range(5):
        raw = await redis_client.get_challenge()
        data = json.loads(raw)
        assert data["id"] == f"fifo-{i}"


@pytest.mark.integration
@skip_no_redis
@pytest.mark.asyncio
async def test_pop_empty_returns_none(redis_client):
    result = await redis_client.get_challenge()
    assert result is None


@pytest.mark.integration
@skip_no_redis
@pytest.mark.asyncio
async def test_pool_size_empty(redis_client):
    size = await redis_client.get_pool_size()
    assert size == 0


@pytest.mark.integration
@skip_no_redis
@pytest.mark.asyncio
async def test_connection_failure():
    """Testa que conexão com host inválido levanta RedisConnectionError."""
    client = RedisClientImpl(host="host-invalido-xyz", port=9999, key=TEST_KEY)
    with pytest.raises(RedisConnectionError):
        await client.connect()
