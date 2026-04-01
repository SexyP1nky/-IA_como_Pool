"""
Integração com Redis para o pool de desafios.

Módulo responsável por:
- Gerenciar conexão com Redis
- Salvar desafios gerados no pool
- Recuperar desafios do pool
- Tratamento de erros de conexão
"""
import json
import logging
from typing import Optional
from abc import ABC, abstractmethod

from src.generators.challenge_generator import Challenge

logger = logging.getLogger(__name__)

# Configuração padrão
DEFAULT_REDIS_KEY = "challenge_pool"
DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 0


class RedisConnectionError(Exception):
    """Erro de conexão com Redis."""
    pass


class RedisClient(ABC):
    """Interface abstrata para cliente Redis."""

    @abstractmethod
    async def push_challenge(self, challenge: Challenge) -> bool:
        """
        Adiciona um desafio ao pool no Redis.

        Args:
            challenge: Desafio a adicionar

        Returns:
            bool: True se bem-sucedido

        Raises:
            RedisConnectionError: Erro de conexão
        """
        pass

    @abstractmethod
    async def push_challenges_batch(self, challenges: list[Challenge]) -> bool:
        """
        Adiciona múltiplos desafios ao pool no Redis.

        Args:
            challenges: Lista de desafios

        Returns:
            bool: True se bem-sucedido

        Raises:
            RedisConnectionError: Erro de conexão
        """
        pass

    @abstractmethod
    async def get_challenge(self) -> Optional[str]:
        """
        Recupera um desafio do pool no Redis.

        Returns:
            Optional[str]: Desafio em JSON ou None

        Raises:
            RedisConnectionError: Erro de conexão
        """
        pass

    @abstractmethod
    async def get_pool_size(self) -> int:
        """
        Retorna o tamanho do pool de desafios.

        Returns:
            int: Número de desafios no pool

        Raises:
            RedisConnectionError: Erro de conexão
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Fecha a conexão com Redis."""
        pass


class RedisClientImpl(RedisClient):
    """Implementação real do cliente Redis usando aioredis."""

    def __init__(
        self,
        host: str = DEFAULT_REDIS_HOST,
        port: int = DEFAULT_REDIS_PORT,
        db: int = DEFAULT_REDIS_DB,
        key: str = DEFAULT_REDIS_KEY,
    ):
        """
        Inicializa o cliente Redis.

        Args:
            host: Host do Redis
            port: Porta do Redis
            db: Database do Redis
            key: Chave de lista para armazenar desafios
        """
        self.host = host
        self.port = port
        self.db = db
        self.key = key
        self.redis = None
        self.logger = logging.getLogger(__name__)

    async def connect(self) -> None:
        """Conecta ao Redis."""
        try:
            import aioredis

            self.redis = await aioredis.create_redis_pool(
                f"redis://{self.host}:{self.port}/{self.db}"
            )
            self.logger.info(
                f"Connected to Redis at {self.host}:{self.port}/{self.db}"
            )
        except Exception as e:
            error_msg = f"Failed to connect to Redis: {str(e)}"
            self.logger.error(error_msg)
            raise RedisConnectionError(error_msg) from e

    async def push_challenge(self, challenge: Challenge) -> bool:
        """Adiciona um desafio ao pool."""
        if not self.redis:
            raise RedisConnectionError("Redis not connected")

        try:
            challenge_json = json.dumps(challenge.to_dict())
            await self.redis.rpush(self.key, challenge_json)
            self.logger.debug(f"Challenge {challenge.id} pushed to Redis")
            return True
        except Exception as e:
            error_msg = f"Failed to push challenge to Redis: {str(e)}"
            self.logger.error(error_msg)
            raise RedisConnectionError(error_msg) from e

    async def push_challenges_batch(self, challenges: list[Challenge]) -> bool:
        """Adiciona múltiplos desafios ao pool."""
        if not self.redis:
            raise RedisConnectionError("Redis not connected")

        try:
            for challenge in challenges:
                challenge_json = json.dumps(challenge.to_dict())
                await self.redis.rpush(self.key, challenge_json)

            self.logger.info(f"Batch of {len(challenges)} challenges pushed to Redis")
            return True
        except Exception as e:
            error_msg = f"Failed to push challenges batch to Redis: {str(e)}"
            self.logger.error(error_msg)
            raise RedisConnectionError(error_msg) from e

    async def get_challenge(self) -> Optional[str]:
        """Recupera um desafio do pool."""
        if not self.redis:
            raise RedisConnectionError("Redis not connected")

        try:
            challenge = await self.redis.lpop(self.key)
            if challenge:
                self.logger.debug("Challenge retrieved from Redis")
                return challenge.decode() if isinstance(challenge, bytes) else challenge
            return None
        except Exception as e:
            error_msg = f"Failed to get challenge from Redis: {str(e)}"
            self.logger.error(error_msg)
            raise RedisConnectionError(error_msg) from e

    async def get_pool_size(self) -> int:
        """Retorna o tamanho do pool."""
        if not self.redis:
            raise RedisConnectionError("Redis not connected")

        try:
            size = await self.redis.llen(self.key)
            self.logger.debug(f"Pool size: {size}")
            return size
        except Exception as e:
            error_msg = f"Failed to get pool size from Redis: {str(e)}"
            self.logger.error(error_msg)
            raise RedisConnectionError(error_msg) from e

    async def close(self) -> None:
        """Fecha a conexão com Redis."""
        if self.redis:
            self.redis.close()
            await self.redis.wait_closed()
            self.logger.info("Redis connection closed")


class MockRedisClient(RedisClient):
    """Mock do cliente Redis para testes."""

    def __init__(self):
        """Inicializa o mock com uma lista em memória."""
        self.storage: list[str] = []
        self.logger = logging.getLogger(__name__)

    async def push_challenge(self, challenge: Challenge) -> bool:
        """Adiciona um desafio ao mock."""
        self.storage.append(json.dumps(challenge.to_dict()))
        return True

    async def push_challenges_batch(self, challenges: list[Challenge]) -> bool:
        """Adiciona múltiplos desafios ao mock."""
        for challenge in challenges:
            self.storage.append(json.dumps(challenge.to_dict()))
        return True

    async def get_challenge(self) -> Optional[str]:
        """Recupera um desafio do mock."""
        return self.storage.pop(0) if self.storage else None

    async def get_pool_size(self) -> int:
        """Retorna o tamanho do mock storage."""
        return len(self.storage)

    async def close(self) -> None:
        """Limpa o mock."""
        self.storage.clear()


# Função legacy para retrocompatibilidade com código existente
async def get_challenge_from_redis(
    host: str = DEFAULT_REDIS_HOST,
    port: int = DEFAULT_REDIS_PORT,
    key: str = DEFAULT_REDIS_KEY,
) -> Optional[str]:
    """
    Busca um desafio pronto no Redis (função legacy).

    Args:
        host: Host do Redis
        port: Porta do Redis
        key: Chave de lista

    Returns:
        Optional[str]: Desafio em JSON ou None
    """
    try:
        client = RedisClientImpl(host=host, port=port, key=key)
        await client.connect()
        challenge = await client.get_challenge()
        await client.close()
        return challenge
    except RedisConnectionError as e:
        logger.warning(f"Failed to get challenge from Redis: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_challenge_from_redis: {str(e)}")
        return None
