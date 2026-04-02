"""
Integração com Redis para o pool de desafios.

Usa redis-py (redis.asyncio) como cliente async.
"""

import json
import logging
import os
from typing import Optional
from abc import ABC, abstractmethod

from src.generators.challenge_generator import Challenge

logger = logging.getLogger(__name__)

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
        pass

    @abstractmethod
    async def push_challenges_batch(self, challenges: list[Challenge]) -> bool:
        pass

    @abstractmethod
    async def get_challenge(self) -> Optional[str]:
        pass

    @abstractmethod
    async def get_pool_size(self) -> int:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    @abstractmethod
    async def ping(self) -> bool:
        """Verifica se a conexão com Redis está ativa."""
        pass


class RedisClientImpl(RedisClient):
    """Implementação real do cliente Redis usando redis.asyncio (redis-py)."""

    def __init__(
        self,
        host: str = DEFAULT_REDIS_HOST,
        port: int = DEFAULT_REDIS_PORT,
        db: int = DEFAULT_REDIS_DB,
        key: str = DEFAULT_REDIS_KEY,
        *,
        url: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.db = db
        self.key = key
        self._url = url
        self.redis = None
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_url(cls, url: str, key: str = DEFAULT_REDIS_KEY) -> "RedisClientImpl":
        """Cria instância preservando a URL original (auth, rediss://, query params)."""
        return cls(key=key, url=url)

    @classmethod
    def from_env(cls) -> "RedisClientImpl":
        """Cria instância a partir das variáveis de ambiente.

        Prioriza REDIS_URL; se ausente, usa REDIS_HOST/PORT/DB.
        """
        key = os.getenv("REDIS_KEY", DEFAULT_REDIS_KEY)
        url = os.getenv("REDIS_URL")
        if url:
            return cls.from_url(url, key=key)
        return cls(
            host=os.getenv("REDIS_HOST", DEFAULT_REDIS_HOST),
            port=int(os.getenv("REDIS_PORT", str(DEFAULT_REDIS_PORT))),
            db=int(os.getenv("REDIS_DB", str(DEFAULT_REDIS_DB))),
            key=key,
        )

    async def connect(self) -> None:
        """Conecta ao Redis."""
        try:
            import redis.asyncio as aioredis

            if self._url:
                self.redis = aioredis.Redis.from_url(
                    self._url,
                    decode_responses=True,
                )
                label = self._url.split("@")[-1] if "@" in self._url else self._url
            else:
                self.redis = aioredis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    decode_responses=True,
                )
                label = f"{self.host}:{self.port}/{self.db}"

            await self.redis.ping()
            self.logger.info(f"Connected to Redis at {label}")
        except Exception as e:
            self.redis = None
            error_msg = f"Failed to connect to Redis: {e}"
            self.logger.error(error_msg)
            raise RedisConnectionError(error_msg) from e

    async def ping(self) -> bool:
        if not self.redis:
            return False
        try:
            return await self.redis.ping()
        except Exception:
            return False

    async def push_challenge(self, challenge: Challenge) -> bool:
        if not self.redis:
            raise RedisConnectionError("Redis not connected")
        try:
            await self.redis.rpush(self.key, json.dumps(challenge.to_dict()))
            self.logger.debug(f"Challenge {challenge.id} pushed to Redis")
            return True
        except Exception as e:
            raise RedisConnectionError(f"Failed to push challenge: {e}") from e

    async def push_challenges_batch(self, challenges: list[Challenge]) -> bool:
        if not self.redis:
            raise RedisConnectionError("Redis not connected")
        try:
            pipe = self.redis.pipeline()
            for challenge in challenges:
                pipe.rpush(self.key, json.dumps(challenge.to_dict()))
            await pipe.execute()
            self.logger.info(f"Batch of {len(challenges)} challenges pushed to Redis")
            return True
        except Exception as e:
            raise RedisConnectionError(f"Failed to push batch: {e}") from e

    async def get_challenge(self) -> Optional[str]:
        if not self.redis:
            raise RedisConnectionError("Redis not connected")
        try:
            challenge = await self.redis.lpop(self.key)
            if challenge:
                self.logger.debug("Challenge retrieved from Redis")
            return challenge
        except Exception as e:
            raise RedisConnectionError(f"Failed to get challenge: {e}") from e

    async def get_pool_size(self) -> int:
        if not self.redis:
            raise RedisConnectionError("Redis not connected")
        try:
            return await self.redis.llen(self.key)
        except Exception as e:
            raise RedisConnectionError(f"Failed to get pool size: {e}") from e

    async def close(self) -> None:
        if self.redis:
            await self.redis.aclose()
            self.logger.info("Redis connection closed")


class MockRedisClient(RedisClient):
    """Mock do cliente Redis para testes."""

    def __init__(self):
        self.storage: list[str] = []

    async def push_challenge(self, challenge: Challenge) -> bool:
        self.storage.append(json.dumps(challenge.to_dict()))
        return True

    async def push_challenges_batch(self, challenges: list[Challenge]) -> bool:
        for challenge in challenges:
            self.storage.append(json.dumps(challenge.to_dict()))
        return True

    async def get_challenge(self) -> Optional[str]:
        return self.storage.pop(0) if self.storage else None

    async def get_pool_size(self) -> int:
        return len(self.storage)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self.storage.clear()


async def get_challenge_from_redis(
    host: str = DEFAULT_REDIS_HOST,
    port: int = DEFAULT_REDIS_PORT,
    key: str = DEFAULT_REDIS_KEY,
) -> Optional[str]:
    """Busca um desafio pronto no Redis (função legacy)."""
    try:
        client = RedisClientImpl(host=host, port=port, key=key)
        await client.connect()
        challenge = await client.get_challenge()
        await client.close()
        return challenge
    except RedisConnectionError as e:
        logger.warning(f"Failed to get challenge from Redis: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error in get_challenge_from_redis: {e}")
        return None
