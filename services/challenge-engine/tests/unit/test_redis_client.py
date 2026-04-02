"""
Testes para o cliente Redis.

Cobre:
- Mock do cliente Redis
- Operações básicas (push, get)
- Tratamento de erros
"""

import pytest
import json
import asyncio
from src.integrations.redis import MockRedisClient
from src.generators.challenge_generator import (
    Challenge,
    ChallengeLevel,
    ChallengeType,
)


class TestMockRedisClient:
    """Testes do mock do cliente Redis."""

    @pytest.fixture
    def redis_client(self):
        """Fixture para criar um cliente Redis mock."""
        return MockRedisClient()

    @pytest.fixture
    def sample_challenge(self):
        """Fixture para criar um desafio de exemplo."""
        return Challenge(
            id="test-123",
            type=ChallengeType.ALGORITHM,
            level=ChallengeLevel.EASY,
            title="Test Challenge",
            description="A test challenge",
            example_input="test",
            example_output="test",
            created_at="2024-01-01T00:00:00",
        )

    def test_init(self, redis_client):
        """Testa inicialização do mock."""
        assert redis_client.storage == []

    def test_push_challenge(self, redis_client, sample_challenge):
        """Testa adição de um desafio."""

        async def run_test():
            result = await redis_client.push_challenge(sample_challenge)
            assert result is True
            assert len(redis_client.storage) == 1

        asyncio.run(run_test())

    def test_push_challenge_multiple(self, redis_client, sample_challenge):
        """Testa adição de múltiplos desafios."""

        async def run_test():
            for i in range(3):
                challenge = sample_challenge
                challenge.id = f"test-{i}"
                await redis_client.push_challenge(challenge)

            assert len(redis_client.storage) == 3

        asyncio.run(run_test())

    def test_get_challenge(self, redis_client, sample_challenge):
        """Testa recuperação de um desafio."""

        async def run_test():
            await redis_client.push_challenge(sample_challenge)
            challenge_json = await redis_client.get_challenge()

            assert challenge_json is not None
            data = json.loads(challenge_json)
            assert data["id"] == "test-123"
            assert len(redis_client.storage) == 0  # Deve remover após get

        asyncio.run(run_test())

    def test_get_challenge_empty(self, redis_client):
        """Testa recuperação quando storage está vazio."""

        async def run_test():
            result = await redis_client.get_challenge()
            assert result is None

        asyncio.run(run_test())

    def test_push_batch(self, redis_client, sample_challenge):
        """Testa adição de lote."""

        async def run_test():
            challenges = [sample_challenge for _ in range(5)]
            result = await redis_client.push_challenges_batch(challenges)

            assert result is True
            assert len(redis_client.storage) == 5

        asyncio.run(run_test())

    def test_get_pool_size(self, redis_client, sample_challenge):
        """Testa obtenção do tamanho do pool."""

        async def run_test():
            await redis_client.push_challenge(sample_challenge)
            size = await redis_client.get_pool_size()

            assert size == 1

        asyncio.run(run_test())

    def test_get_pool_size_multiple(self, redis_client, sample_challenge):
        """Testa tamanho do pool com múltiplos items."""

        async def run_test():
            for i in range(5):
                challenge = sample_challenge
                challenge.id = f"test-{i}"
                await redis_client.push_challenge(challenge)

            size = await redis_client.get_pool_size()
            assert size == 5

        asyncio.run(run_test())

    def test_close(self, redis_client, sample_challenge):
        """Testa fechamento da conexão."""

        async def run_test():
            await redis_client.push_challenge(sample_challenge)
            await redis_client.close()

            assert len(redis_client.storage) == 0

        asyncio.run(run_test())

    def test_fifo_order(self, redis_client):
        """Testa que entrega segue ordem FIFO."""

        async def run_test():
            challenges = []
            for i in range(3):
                challenge = Challenge(
                    id=f"test-{i}",
                    type=ChallengeType.ALGORITHM,
                    level=ChallengeLevel.EASY,
                    title=f"Challenge {i}",
                    description="Test",
                    example_input="test",
                    example_output="test",
                    created_at="2024-01-01",
                )
                challenges.append(challenge)
                await redis_client.push_challenge(challenge)

            for i in range(3):
                result = await redis_client.get_challenge()
                data = json.loads(result)
                assert data["id"] == f"test-{i}"

        asyncio.run(run_test())
