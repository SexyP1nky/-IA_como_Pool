import asyncio
import os

import asyncpg


DEFAULT_DATABASE_URL = "postgresql://127.0.0.1:5432/ai_pool"


async def run() -> None:
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    try:
        conn = await asyncpg.connect(database_url, timeout=2.0)
        print("CONECTADO COM SUCESSO!")
        await conn.close()
    except Exception as e:
        print(f"ERRO: {e}")


if __name__ == "__main__":
    asyncio.run(run())