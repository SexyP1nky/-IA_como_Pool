import asyncio
import asyncpg

async def run():
    try:
        conn = await asyncpg.connect('postgresql://ai_pool_user:ai_pool_pass@127.0.0.1:5432/ai_pool', ssl=False)
        print("CONECTADO COM SUCESSO!")
        await conn.close()
    except Exception as e:
        print(f"ERRO: {e}")

asyncio.run(run())