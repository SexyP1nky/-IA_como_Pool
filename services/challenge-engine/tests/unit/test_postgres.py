"""Testes unitários de integração postgres (sem banco)."""
from src.integrations.postgres import _postgres_dsn


def test_postgres_dsn_normalizes_asyncpg_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    assert _postgres_dsn() == "postgresql://u:p@h:5432/db"


def test_postgres_dsn_none_without_env(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert _postgres_dsn() is None
