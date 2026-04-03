#!/usr/bin/env python3
"""
Script de validação de leitura/escrita no Redis.

Uso:
    # Com Redis rodando localmente (docker-compose up redis):
    python scripts/validate_redis.py

    # Com URL customizada:
    REDIS_URL=redis://localhost:6379/0 python scripts/validate_redis.py

Testa: ping, push, pop, batch, pool size, FIFO order, cleanup.
"""

import asyncio
import json
import os
import sys
import time


async def main():
    try:
        import redis.asyncio as aioredis
    except ImportError:
        print("ERRO: pacote 'redis' não instalado. Rode: pip install redis[hiredis]")
        sys.exit(1)

    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    test_key = "validation_test_pool"
    print("=== Validação Redis ===")
    print(f"URL: {url}")
    print(f"Key: {test_key}\n")

    r = aioredis.from_url(url, decode_responses=True)
    passed = 0
    failed = 0

    def ok(name):
        nonlocal passed
        passed += 1
        print(f"  [PASS] {name}")

    def fail(name, err):
        nonlocal failed
        failed += 1
        print(f"  [FAIL] {name} — {err}")

    try:
        # 1) Ping
        print("1. Conectividade (PING)")
        try:
            result = await r.ping()
            assert result is True
            ok("Redis respondeu PONG")
        except Exception as e:
            fail("PING", e)
            print(f"\n  Redis não está acessível em {url}.")
            print("  Rode: docker-compose up -d redis")
            sys.exit(1)

        # Limpa key de teste antes de começar
        await r.delete(test_key)

        # 2) Write (RPUSH)
        print("\n2. Escrita (RPUSH)")
        try:
            challenge = {
                "id": "val-1",
                "title": "Validation Challenge",
                "type": "algorithm",
            }
            await r.rpush(test_key, json.dumps(challenge))
            size = await r.llen(test_key)
            assert size == 1
            ok(f"Push OK, pool size = {size}")
        except Exception as e:
            fail("RPUSH", e)

        # 3) Read (LPOP)
        print("\n3. Leitura (LPOP)")
        try:
            raw = await r.lpop(test_key)
            data = json.loads(raw)
            assert data["id"] == "val-1"
            ok(f"Pop OK, id = {data['id']}")
        except Exception as e:
            fail("LPOP", e)

        # 4) Batch write (pipeline)
        print("\n4. Escrita em batch (PIPELINE)")
        try:
            pipe = r.pipeline()
            for i in range(5):
                pipe.rpush(test_key, json.dumps({"id": f"batch-{i}", "seq": i}))
            await pipe.execute()
            size = await r.llen(test_key)
            assert size == 5
            ok(f"Pipeline 5 itens, pool size = {size}")
        except Exception as e:
            fail("PIPELINE", e)

        # 5) FIFO order
        print("\n5. Ordem FIFO")
        try:
            for i in range(5):
                raw = await r.lpop(test_key)
                data = json.loads(raw)
                assert data["seq"] == i, f"Esperado seq={i}, recebeu seq={data['seq']}"
            ok("Ordem FIFO verificada (0→4)")
        except Exception as e:
            fail("FIFO", e)

        # 6) Pool size after drain
        print("\n6. Pool vazio após consumo")
        try:
            size = await r.llen(test_key)
            assert size == 0
            ok(f"Pool size = {size} (vazio)")
        except Exception as e:
            fail("Pool vazio", e)

        # 7) Latência
        print("\n7. Latência de escrita/leitura")
        try:
            t0 = time.perf_counter()
            iterations = 100
            pipe = r.pipeline()
            for i in range(iterations):
                pipe.rpush(test_key, json.dumps({"id": f"perf-{i}"}))
            await pipe.execute()
            for _ in range(iterations):
                await r.lpop(test_key)
            elapsed = (time.perf_counter() - t0) * 1000
            avg = elapsed / (iterations * 2)
            ok(f"{iterations} write+read em {elapsed:.1f}ms (avg {avg:.2f}ms/op)")
        except Exception as e:
            fail("Latência", e)

    finally:
        await r.delete(test_key)
        await r.aclose()

    print(f"\n{'=' * 40}")
    print(f"Resultado: {passed} passed, {failed} failed")
    if failed > 0:
        sys.exit(1)
    print("Redis validado com sucesso!")


if __name__ == "__main__":
    asyncio.run(main())
