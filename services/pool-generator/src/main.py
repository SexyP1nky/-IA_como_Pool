"""Pool Generator — Celery worker that keeps the Redis challenge pool filled.

Architecture:
    Celery Beat  ──(every N seconds)──>  refill_pool (periodic task)
        │
        ├── checks Redis pool size via LLEN
        ├── if size < POOL_MIN_SIZE: dispatches generate_single_challenge tasks
        └── each task calls LLM (circuit-breaker protected) and RPUSHes to Redis

Patterns implemented:
    - Async processing via RabbitMQ (Celery broker)
    - Circuit Breaker on LLM calls
    - Retry with exponential backoff + DLQ (Celery task_reject_on_worker_lost)
    - Bulkhead: this worker is isolated from the challenge-engine API
"""

import logging

from celery import Celery
from celery.schedules import timedelta
from celery.signals import after_setup_logger

from src.config import config

LOG_FMT = "[%(asctime)s] %(levelname)s | %(message)s"
LOG_DATEFMT = "%H:%M:%S"

logging.basicConfig(level=logging.INFO, format=LOG_FMT, datefmt=LOG_DATEFMT)

for _noisy in (
    "celery.worker.strategy",
    "celery.app.trace",
    "celery.worker.consumer",
    "celery.worker.consumer.connection",
    "celery.bootsteps",
    "celery.utils.functional",
    "celery.beat",
    "httpx",
    "httpcore",
    "kombu",
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger("pool-generator")


@after_setup_logger.connect
def _quiet_celery(sender=None, **kwargs):
    """Keep Celery from overriding our format."""
    celery_logger = kwargs.get("logger", sender)
    if celery_logger:
        for h in celery_logger.handlers:
            h.setFormatter(logging.Formatter(LOG_FMT, datefmt=LOG_DATEFMT))


# ---------------------------------------------------------------------------
# Celery application
# ---------------------------------------------------------------------------

app = Celery("pool_generator", broker=config.CELERY_BROKER_URL)

app.conf.update(
    result_backend=config.REDIS_URL,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="pool_tasks",
    task_default_exchange="pool_tasks",
    task_default_routing_key="pool_tasks",
    worker_hijack_root_logger=False,
)

app.conf.beat_schedule = {
    "refill-pool-periodically": {
        "task": "src.main.refill_pool",
        "schedule": timedelta(seconds=config.REFILL_INTERVAL_S),
    },
}


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


@app.task(name="src.main.refill_pool")
def refill_pool():
    """Check the Redis pool and dispatch generation tasks if pool is low."""
    from src import redis_client as rc

    current_size = rc.get_pool_size()

    if current_size >= config.POOL_MIN_SIZE:
        logger.info(
            "[POOL CHECK] size=%d/%d — healthy, no refill needed",
            current_size,
            config.POOL_TARGET_SIZE,
        )
        return {"status": "ok", "pool_size": current_size, "generated": 0}

    deficit = config.POOL_TARGET_SIZE - current_size
    logger.info(
        "[POOL CHECK] size=%d/%d — BELOW minimum (%d) — dispatching %d LLM generation tasks",
        current_size,
        config.POOL_TARGET_SIZE,
        config.POOL_MIN_SIZE,
        deficit,
    )

    for _ in range(deficit):
        generate_single_challenge.delay()

    return {"status": "refilling", "pool_size": current_size, "dispatched": deficit}


@app.task(
    name="src.main.generate_single_challenge",
    bind=True,
    max_retries=config.TASK_MAX_RETRIES,
    default_retry_delay=config.TASK_RETRY_DELAY_S,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
)
def generate_single_challenge(self):
    """Generate one challenge via LLM and push it to Redis.

    On failure, Celery retries with exponential backoff.  After max_retries
    the task is rejected and routed to the dead-letter queue.
    """
    from src import llm_client, redis_client as rc

    challenge = llm_client.generate_challenge()
    pushed = rc.push_challenge(challenge)

    if not pushed:
        raise RuntimeError("Failed to push challenge to Redis")

    source = challenge.get("metadata", {}).get("source", "unknown")
    logger.info(
        "[GENERATED] source=%-5s | type=%-20s | level=%-6s | %s\n"
        "            desc: %s\n"
        "            input:  %s\n"
        "            output: %s",
        source,
        challenge.get("type", "?"),
        challenge.get("level", "?"),
        challenge.get("title", "?"),
        challenge.get("description", "?")[:140],
        str(challenge.get("example_input", "?"))[:100],
        str(challenge.get("example_output", "?"))[:100],
    )
    return {"id": challenge["id"], "source": source}
