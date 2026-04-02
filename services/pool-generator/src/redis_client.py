"""Synchronous Redis client for the Celery-based pool generator."""

import json
import logging

import redis

from src.config import config

logger = logging.getLogger(__name__)

_pool: redis.ConnectionPool | None = None


def _get_pool() -> redis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(config.REDIS_URL, decode_responses=True)
    return _pool


def get_client() -> redis.Redis:
    return redis.Redis(connection_pool=_get_pool())


def get_pool_size() -> int:
    try:
        return get_client().llen(config.REDIS_KEY)
    except redis.RedisError as exc:
        logger.error("Redis LLEN failed: %s", exc)
        return 0


def push_challenge(challenge_dict: dict) -> bool:
    try:
        get_client().rpush(config.REDIS_KEY, json.dumps(challenge_dict))
        return True
    except redis.RedisError as exc:
        logger.error("Redis RPUSH failed: %s", exc)
        return False


def push_challenges_batch(challenges: list[dict]) -> int:
    """Push multiple challenges via pipeline. Returns count pushed."""
    try:
        pipe = get_client().pipeline()
        for ch in challenges:
            pipe.rpush(config.REDIS_KEY, json.dumps(ch))
        pipe.execute()
        return len(challenges)
    except redis.RedisError as exc:
        logger.error("Redis batch RPUSH failed: %s", exc)
        return 0


def ping() -> bool:
    try:
        return get_client().ping()
    except redis.RedisError:
        return False
