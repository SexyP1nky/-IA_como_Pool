"""Async Redis client for the challenge pool.

Uses redis-py (redis.asyncio).
The pool-generator writes challenges as JSON strings via RPUSH;
this client reads them via LPOP.
"""

import json
import logging
import os
from typing import Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

DEFAULT_REDIS_KEY = "challenge_pool"
DEFAULT_REDIS_HOST = "localhost"
DEFAULT_REDIS_PORT = 6379
DEFAULT_REDIS_DB = 0


class RedisConnectionError(Exception):
    pass


class RedisClient(ABC):
    @abstractmethod
    async def push_challenge(self, challenge: dict) -> bool:
        pass

    @abstractmethod
    async def push_challenges_batch(self, challenges: list[dict]) -> bool:
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
        pass


class RedisClientImpl(RedisClient):
    """Production Redis client using redis.asyncio."""

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
        return cls(key=key, url=url)

    @classmethod
    def from_env(cls) -> "RedisClientImpl":
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
        try:
            import redis.asyncio as aioredis

            if self._url:
                self.redis = aioredis.Redis.from_url(self._url, decode_responses=True)
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
            self.logger.info("Connected to Redis at %s", label)
        except Exception as e:
            self.redis = None
            raise RedisConnectionError(f"Failed to connect to Redis: {e}") from e

    async def ping(self) -> bool:
        if not self.redis:
            return False
        try:
            return await self.redis.ping()
        except Exception:
            return False

    async def push_challenge(self, challenge: dict) -> bool:
        if not self.redis:
            raise RedisConnectionError("Redis not connected")
        try:
            await self.redis.rpush(self.key, json.dumps(challenge))
            return True
        except Exception as e:
            raise RedisConnectionError(f"Failed to push challenge: {e}") from e

    async def push_challenges_batch(self, challenges: list[dict]) -> bool:
        if not self.redis:
            raise RedisConnectionError("Redis not connected")
        try:
            pipe = self.redis.pipeline()
            for challenge in challenges:
                pipe.rpush(self.key, json.dumps(challenge))
            await pipe.execute()
            return True
        except Exception as e:
            raise RedisConnectionError(f"Failed to push batch: {e}") from e

    async def get_challenge(self) -> Optional[str]:
        if not self.redis:
            raise RedisConnectionError("Redis not connected")
        try:
            return await self.redis.lpop(self.key)
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
    """In-memory mock for tests."""

    def __init__(self):
        self.storage: list[str] = []

    async def push_challenge(self, challenge: dict) -> bool:
        self.storage.append(json.dumps(challenge))
        return True

    async def push_challenges_batch(self, challenges: list[dict]) -> bool:
        for ch in challenges:
            self.storage.append(json.dumps(ch))
        return True

    async def get_challenge(self) -> Optional[str]:
        return self.storage.pop(0) if self.storage else None

    async def get_pool_size(self) -> int:
        return len(self.storage)

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        self.storage.clear()
