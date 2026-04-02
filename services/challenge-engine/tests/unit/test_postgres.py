"""Testes unitários de integração postgres."""

import os
from unittest.mock import patch, AsyncMock
import pytest

from src.integrations.postgres import _postgres_dsn, get_challenge_from_postgres


def test_postgres_dsn_normalizes_asyncpg_url():
    with patch.dict(os.environ, {"DATABASE_URL": "postgresql+asyncpg://user:pass@host/db"}):
        assert _postgres_dsn() == "postgresql://user:pass@host/db"


def test_postgres_dsn_none_without_env():
    with patch.dict(os.environ, {}, clear=True):
        assert _postgres_dsn() is None


@pytest.mark.asyncio
async def test_get_challenge_success():
    with patch("src.integrations.postgres._postgres_dsn", return_value="fake_dsn"), \
         patch("src.integrations.postgres.asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {"challenge": '{"id": "c1"}'}
        mock_connect.return_value = mock_conn
        
        result = await get_challenge_from_postgres()
        
        assert result == '{"id": "c1"}'
        mock_connect.assert_called_once()
        mock_conn.fetchrow.assert_called_once()
        mock_conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_challenge_empty_table():
    with patch("src.integrations.postgres._postgres_dsn", return_value="fake_dsn"), \
         patch("src.integrations.postgres.asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None  # None rows returned
        mock_connect.return_value = mock_conn
        
        result = await get_challenge_from_postgres()
        
        assert result is None
        mock_conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_get_challenge_connection_fails():
    with patch("src.integrations.postgres._postgres_dsn", return_value="fake_dsn"), \
         patch("src.integrations.postgres.asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        
        # Simulate connection timeout or refusal
        mock_connect.side_effect = Exception("Connection refused")
        
        result = await get_challenge_from_postgres()
        
        assert result is None


@pytest.mark.asyncio
async def test_get_challenge_query_fails():
    with patch("src.integrations.postgres._postgres_dsn", return_value="fake_dsn"), \
         patch("src.integrations.postgres.asyncpg.connect", new_callable=AsyncMock) as mock_connect:
        
        mock_conn = AsyncMock()
        # Simulate query timeout or syntax error
        mock_conn.fetchrow.side_effect = Exception("Query timeout")
        mock_connect.return_value = mock_conn
        
        result = await get_challenge_from_postgres()
        
        assert result is None
        mock_conn.close.assert_called_once()  # Ensure cleanup happens even on error


@pytest.mark.asyncio
async def test_get_challenge_no_dsn_returns_none():
    with patch("src.integrations.postgres._postgres_dsn", return_value=None):
        result = await get_challenge_from_postgres()
        assert result is None
