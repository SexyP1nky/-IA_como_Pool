"""Challenge Engine API — pure consumer of the Redis challenge pool.

Endpoints:
    GET /health     — Redis connection status and pool size
    GET /challenge  — pop a challenge from pool, fallback to Postgres, or 503
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from src.integrations.redis import RedisClientImpl
from src.integrations.postgres import get_challenge_from_postgres

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

redis_client: RedisClientImpl | None = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    global redis_client
    try:
        redis_client = RedisClientImpl.from_env()
        await redis_client.connect()
        logger.info("Redis connected")
    except Exception as e:
        logger.warning("Redis unavailable at startup (%s), starting degraded", e)
        redis_client = None

    yield

    if redis_client:
        await redis_client.close()


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
            logger.warning("Redis read failed: %s", e)

    if challenge:
        return JSONResponse(content={"challenge": challenge, "source": "pool"})

    challenge = await get_challenge_from_postgres()
    if challenge:
        return JSONResponse(
            content={"challenge": challenge, "source": "static_fallback"}
        )

    raise HTTPException(status_code=503, detail="No challenge available.")
