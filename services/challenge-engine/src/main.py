"""
Challenge Engine API

Este serviço expõe o endpoint /challenge, que busca desafios prontos em Redis (pool) e faz fallback para PostgreSQL.

Integrações:
	- src/integrations/redis.py: função get_challenge_from_redis()
	- src/integrations/postgres.py: função get_challenge_from_postgres()

Para integrar:
	- Implemente as funções stub nas integrações conforme contrato e docstring.
	- O endpoint já está pronto para consumir essas funções.
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from src.integrations.redis import get_challenge_from_redis
from src.integrations.postgres import get_challenge_from_postgres

app = FastAPI()

@app.get("/challenge")
async def get_challenge():
	# 1. Tenta buscar no Redis
	challenge = await get_challenge_from_redis()
	if challenge:
		return JSONResponse(content={"challenge": challenge, "source": "pool"})

	# 2. Fallback: busca no PostgreSQL
	challenge = await get_challenge_from_postgres()
	if challenge:
		return JSONResponse(content={"challenge": challenge, "source": "static_fallback"})

	# 3. Se não houver desafio disponível
	raise HTTPException(status_code=503, detail="No challenge available.")
