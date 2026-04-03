"""
Testes de integração com PostgreSQL real.

Requer Postgres com schema (docker-compose up -d postgres) e DATABASE_URL.
Rodar com:  pytest tests/integration/test_postgres_integration.py -v -m integration
"""

import json
import os

import pytest
import asyncpg

from src.integrations.postgres import get_challenge_from_postgres

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://ai_pool_user:ai_pool_pass@localhost:5432/ai_pool"
)
PROBE_TIMEOUT_S = 2.0


def _can_reach_postgres() -> bool:
    import asyncio

    async def _ping():
        dsn = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL).replace(
            "postgresql+asyncpg://", "postgresql://", 1
        )
        try:
            conn = await asyncpg.connect(dsn, timeout=PROBE_TIMEOUT_S)
            await conn.close()
            return True
        except Exception:
            return False

    return asyncio.run(_ping())


skip_no_postgres = pytest.mark.skipif(
    not _can_reach_postgres(),
    reason=(
        "PostgreSQL não acessível (rode: docker-compose up -d postgres; "
        "DATABASE_URL padrão localhost)"
    ),
)


@pytest.mark.integration
@skip_no_postgres
@pytest.mark.asyncio
async def test_get_challenge_from_postgres_returns_json_string():
    raw = await get_challenge_from_postgres()
    assert raw is not None
    data = json.loads(raw)
    assert "id" in data
    assert data.get("type") in ("algorithm", "string_manipulation", "math")
    assert "title" in data
