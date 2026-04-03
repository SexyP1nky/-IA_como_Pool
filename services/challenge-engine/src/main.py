"""Challenge Engine API — pure consumer of the Redis challenge pool.

Endpoints:
    GET /health     — Redis connection status and pool size
    GET /challenge  — pop a challenge from pool, fallback to Postgres, or 503
"""

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.integrations.redis import RedisClientImpl
from src.integrations.postgres import get_challenge_from_postgres

LOG_FMT = "[%(asctime)s] %(levelname)s | %(message)s"
LOG_DATEFMT = "%H:%M:%S"

logging.basicConfig(level=logging.INFO, format=LOG_FMT, datefmt=LOG_DATEFMT)

for _noisy in (
    "uvicorn.access",
    "uvicorn.error",
    "httpx",
    "httpcore",
    "src.integrations.redis",
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger("challenge-engine")

redis_client: RedisClientImpl | None = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    global redis_client
    try:
        redis_client = RedisClientImpl.from_env()
        await redis_client.connect()
        pool_size = await redis_client.get_pool_size()
        logger.info("[STARTUP] Redis connected | pool_size=%d", pool_size)
    except Exception as e:
        logger.warning(
            "[STARTUP] Redis unavailable (%s) — starting in degraded mode", e
        )
        redis_client = None

    yield

    if redis_client:
        await redis_client.close()
        logger.info("[SHUTDOWN] Redis connection closed")


app = FastAPI(
    title="Challenge Engine API",
    description="Serviço de distribuição de desafios — consome do pool Redis preenchido pelo pool-generator",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    """Health check with real dependency status."""
    redis_ok = False
    pool_size = 0

    if redis_client:
        try:
            redis_ok = await redis_client.ping()
            if redis_ok:
                pool_size = await redis_client.get_pool_size()
        except Exception:
            redis_ok = False

    status = "healthy" if redis_ok else "degraded"

    return JSONResponse(
        content={
            "status": status,
            "redis": {
                "connected": redis_ok,
                "pool_size": pool_size,
            },
        }
    )


@app.get("/challenge")
async def get_challenge():
    """Pop a challenge from the pool.

    1. Try Redis (LPOP from pool filled by pool-generator)
    2. Fallback: static challenge from PostgreSQL
    3. If both empty: 503 Service Unavailable (load shedding)
    """
    challenge = None
    if redis_client:
        try:
            challenge = await redis_client.get_challenge()
        except Exception as e:
            logger.warning("[ERROR] Redis read failed: %s", e)

    if challenge:
        try:
            c = json.loads(challenge)
            source = c.get("metadata", {}).get("source", "?")
            pool_size = await redis_client.get_pool_size() if redis_client else "?"
            logger.info(
                "[SERVED] source=%-5s | type=%-20s | level=%-6s | %s  (pool remaining: %s)",
                source,
                c.get("type", "?"),
                c.get("level", "?"),
                c.get("title", "?"),
                pool_size,
            )
        except Exception:
            logger.info("[SERVED] source=pool")
        return JSONResponse(content={"challenge": challenge, "source": "pool"})

    challenge = await get_challenge_from_postgres()
    if challenge:
        logger.info("[SERVED] source=postgres_fallback — Redis pool is empty")
        return JSONResponse(
            content={"challenge": challenge, "source": "static_fallback"}
        )

    logger.warning("[REJECTED] 503 — no challenges available (load shedding)")
    raise HTTPException(status_code=503, detail="No challenge available.")
