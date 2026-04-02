"""
Integração com PostgreSQL para fallback de desafios.

Função principal:
    get_challenge_from_postgres()

Responsabilidade:
    Buscar um desafio na tabela 'challenges' do banco PostgreSQL.
    Retornar o desafio como string, ou None se não houver.
    Lançar exceção ou logar erro em caso de falha de conexão.

Exemplo de uso futuro:
    challenge = await get_challenge_from_postgres()
    if challenge:
        ...
"""
import logging
import os

import asyncpg

logger = logging.getLogger(__name__)


def _postgres_dsn() -> str | None:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return None
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def get_challenge_from_postgres() -> str | None:
    """
    Busca um desafio no banco PostgreSQL.

    Onde buscar:
        - Tabela: challenges
        - Campo a buscar: challenge (string)
        - Exemplo de query: SELECT challenge FROM challenges LIMIT 1;

    Onde salvar (se for necessário no futuro):
        - Tabela: challenges
        - Campo a salvar: challenge (string)
        - Exemplo de insert: INSERT INTO challenges (challenge) VALUES ('...');

    Retorna:
        str: desafio encontrado
        None: se não houver desafio disponível
    """
    dsn = _postgres_dsn()
    if not dsn:
        return None

    try:
        conn = await asyncpg.connect(dsn)
        try:
            row = await conn.fetchrow(
                "SELECT challenge FROM challenges ORDER BY id ASC LIMIT 1"
            )
            return row["challenge"] if row else None
        finally:
            await conn.close()
    except Exception as e:
        logger.warning(f"PostgreSQL fallback failed: {e}")
        return None
