"""
Testes para o serviço de desafios.

Cobre:
- Geração e salvamento de desafios
- Geração e salvamento em lote
- Tratamento de erros
- Integração com Redis
"""

import pytest
from unittest.mock import AsyncMock

from src.services.challenge_service import (
    ChallengeService,
    ChallengeServiceError,
)
from src.generators.challenge_generator import (
    Challenge,
    ChallengeLevel,
    ChallengeType,
)
from src.integrations.redis import MockRedisClient, RedisConnectionError


class TestChallengeService:
    """Testes do serviço de desafios."""

    @pytest.fixture
    def mock_redis_client(self):
        """Fixture para criar um mock do cliente Redis."""
        return MockRedisClient()

    @pytest.fixture
    def service_with_redis(self, mock_redis_client):
        """Fixture para criar um serviço com Redis mockado."""
        return ChallengeService(redis_client=mock_redis_client)

    @pytest.fixture
    def service_without_redis(self):
        """Fixture para criar um serviço sem Redis."""
        return ChallengeService(redis_client=None)

    def test_init_with_redis(self, service_with_redis, mock_redis_client):
        """Testa inicialização com cliente Redis."""
        assert service_with_redis.redis_client is mock_redis_client
        assert service_with_redis.generator is not None

    def test_init_without_redis(self, service_without_redis):
        """Testa inicialização sem cliente Redis."""
        assert service_without_redis.redis_client is None
        assert service_without_redis.generator is not None

    @pytest.mark.asyncio
    async def test_generate_and_save_success(
        self, service_with_redis, mock_redis_client
    ):
        """Testa geração e salvamento bem-sucedido."""
        challenge = await service_with_redis.generate_and_save()
        assert isinstance(challenge, Challenge)
        assert challenge.id
        assert await mock_redis_client.get_pool_size() == 1

    @pytest.mark.asyncio
    async def test_generate_and_save_with_type(
        self, service_with_redis, mock_redis_client
    ):
        """Testa geração e salvamento com tipo especificado."""
        challenge = await service_with_redis.generate_and_save(
            challenge_type=ChallengeType.ALGORITHM
        )
        assert challenge.type == ChallengeType.ALGORITHM
        assert await mock_redis_client.get_pool_size() == 1

    @pytest.mark.asyncio
    async def test_generate_and_save_with_level(
        self, service_with_redis, mock_redis_client
    ):
        """Testa geração e salvamento com nível especificado."""
        challenge = await service_with_redis.generate_and_save(
            challenge_type=ChallengeType.ALGORITHM, level=ChallengeLevel.EASY
        )
        assert challenge.level == ChallengeLevel.EASY
        assert await mock_redis_client.get_pool_size() == 1

    @pytest.mark.asyncio
    async def test_generate_and_save_without_redis(self, service_without_redis):
        """Testa geração sem Redis disponível."""
        challenge = await service_without_redis.generate_and_save()
        assert isinstance(challenge, Challenge)
        assert challenge.id

    @pytest.mark.asyncio
    async def test_generate_and_save_redis_failure_non_blocking(
        self, service_with_redis
    ):
        """Testa que falha no Redis não bloqueia geração."""
        failing_redis = AsyncMock()
        failing_redis.push_challenge.side_effect = RedisConnectionError(
            "Connection failed"
        )

        service_with_redis.redis_client = failing_redis

        challenge = await service_with_redis.generate_and_save()

        assert isinstance(challenge, Challenge)
        assert challenge.id

    @pytest.mark.asyncio
    async def test_generate_and_save_batch_with_type(
        self, service_with_redis, mock_redis_client
    ):
        """Testa geração e salvamento em lote com tipo."""
        challenges = await service_with_redis.generate_and_save_batch(
            count=3, challenge_type=ChallengeType.MATH
        )

        assert len(challenges) == 3
        assert all(c.type == ChallengeType.MATH for c in challenges)
        assert await mock_redis_client.get_pool_size() == 3

    @pytest.mark.asyncio
    async def test_generate_and_save_batch_large(
        self, service_with_redis, mock_redis_client
    ):
        """Testa geração em lote grande."""
        challenges = await service_with_redis.generate_and_save_batch(count=50)

        assert len(challenges) == 50
        assert await mock_redis_client.get_pool_size() == 50

    @pytest.mark.asyncio
    async def test_generate_and_save_batch_without_redis(self, service_without_redis):
        """Testa geração em lote sem Redis."""
        challenges = await service_without_redis.generate_and_save_batch(count=5)

        assert len(challenges) == 5
        assert all(isinstance(c, Challenge) for c in challenges)

    @pytest.mark.asyncio
    async def test_generate_and_save_batch_redis_failure_non_blocking(
        self, service_with_redis
    ):
        """Testa que falha no Redis não bloqueia geração em lote."""
        failing_redis = AsyncMock()
        failing_redis.push_challenges_batch.side_effect = RedisConnectionError(
            "Connection failed"
        )

        service_with_redis.redis_client = failing_redis

        challenges = await service_with_redis.generate_and_save_batch(count=5)

        assert len(challenges) == 5
        assert all(isinstance(c, Challenge) for c in challenges)

    def test_get_available_types(self, service_with_redis):
        """Testa recuperação de tipos disponíveis."""
        types = service_with_redis.get_available_types()

        assert isinstance(types, list)
        assert len(types) > 0
        assert "algorithm" in types

    def test_get_available_levels(self, service_with_redis):
        """Testa recuperação de níveis disponíveis."""
        levels = service_with_redis.get_available_levels()

        assert isinstance(levels, list)
        assert len(levels) > 0
        assert "easy" in levels


class TestChallengeServiceErrors:
    """Testes de tratamento de erros do serviço."""

    @pytest.fixture
    def service(self):
        """Fixture para criar um serviço."""
        return ChallengeService(redis_client=None)

    @pytest.mark.asyncio
    async def test_service_error_on_invalid_type(self, service):
        """Testa erro ao usar tipo inválido."""
        with pytest.raises(ChallengeServiceError):
            await service.generate_and_save(challenge_type="invalid")

    @pytest.mark.asyncio
    async def test_batch_error_on_invalid_count(self, service):
        """Testa erro ao usar contagem inválida."""
        with pytest.raises(ChallengeServiceError):
            await service.generate_and_save_batch(count=0)
