"""
Challenge Engine API

Este serviço expõe endpoints para:
- Gerar desafios: POST /challenge/generate
- Buscar desafios prontos no Redis (pool): GET /challenge

Integrações:
	- src/integrations/redis.py: gerenciar pool de desafios em Redis
	- src/integrations/postgres.py: fallback para desafios estáticos

Módulos principais:
	- src/generators/challenge_generator.py: geração de desafios
	- src/services/challenge_service.py: orquestração de geração + Redis
"""
import logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from src.integrations.redis import get_challenge_from_redis
from src.integrations.postgres import get_challenge_from_postgres
from src.services.challenge_service import ChallengeService, ChallengeServiceError
from src.generators.challenge_generator import ChallengeType, ChallengeLevel

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Challenge Engine API",
    description="Serviço de geração e distribução de desafios de programação",
    version="1.0.0",
)

# Inicializar serviço
challenge_service = ChallengeService(redis_client=None)  # Redis mockado por enquanto


@app.get("/health")
async def health():
	"""Endpoint de health check."""
	return JSONResponse(content={"status": "healthy"})


@app.get("/challenge")
async def get_challenge():
	"""
	Busca um desafio pronto no pool.
	
	1. Tenta buscar no Redis
	2. Fallback: busca no PostgreSQL
	3. Se não houver disponível, retorna erro 503
	"""
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


@app.post("/challenge/generate")
async def generate_challenge(
	challenge_type: str = Query(None, description="Tipo de desafio (algorithm, string_manipulation, math)"),
	level: str = Query(None, description="Nível de dificuldade (easy, medium, hard)"),
):
	"""
	Gera um novo desafio e o salva no Redis.
	
	Query Parameters:
		- challenge_type: Tipo de desafio (opcional)
		- level: Nível de dificuldade (opcional)
	
	Returns:
		{
			"id": "uuid",
			"challenge": {desafio_gerado},
			"source": "generated"
		}
	"""
	try:
		# Converter strings de Query para enums
		challenge_type_enum = None
		if challenge_type:
			try:
				challenge_type_enum = ChallengeType(challenge_type)
			except ValueError:
				raise HTTPException(
					status_code=400,
					detail=f"Invalid challenge_type. Must be one of: {', '.join(ChallengeType.get_available_types())}",
				)

		level_enum = None
		if level:
			try:
				level_enum = ChallengeLevel(level)
			except ValueError:
				raise HTTPException(
					status_code=400,
					detail=f"Invalid level. Must be one of: {', '.join(ChallengeLevel.get_available_levels())}",
				)

		# Gera e salva
		challenge = await challenge_service.generate_and_save(
			challenge_type=challenge_type_enum,
			level=level_enum,
		)

		logger.info(f"Challenge generated: {challenge.id}")

		return JSONResponse(
			content={
				"id": challenge.id,
				"challenge": challenge.to_dict(),
				"source": "generated",
			}
		)

	except ChallengeServiceError as e:
		logger.error(f"Service error: {str(e)}")
		raise HTTPException(status_code=500, detail="Failed to generate challenge")
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"Unexpected error: {str(e)}")
		raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/challenge/generate-batch")
async def generate_batch(
	count: int = Query(10, ge=1, le=100, description="Número de desafios a gerar (1-100)"),
	challenge_type: str = Query(None, description="Tipo de desafio (opcional)"),
):
	"""
	Gera múltiplos desafios em lote e os salva no Redis.
	
	Query Parameters:
		- count: Número de desafios (1-100, default=10)
		- challenge_type: Tipo de desafio (opcional)
	
	Returns:
		{
			"count": 10,
			"challenges": [list_of_challenges],
			"source": "generated"
		}
	"""
	try:
		# Converter tipo se especificado
		challenge_type_enum = None
		if challenge_type:
			try:
				challenge_type_enum = ChallengeType(challenge_type)
			except ValueError:
				raise HTTPException(
					status_code=400,
					detail=f"Invalid challenge_type. Must be one of: {', '.join(ChallengeType.get_available_types())}",
				)

		# Gera lote
		challenges = await challenge_service.generate_and_save_batch(
			count=count,
			challenge_type=challenge_type_enum,
		)

		logger.info(f"Batch of {count} challenges generated")

		return JSONResponse(
			content={
				"count": len(challenges),
				"challenges": [c.to_dict() for c in challenges],
				"source": "generated",
			}
		)

	except ChallengeServiceError as e:
		logger.error(f"Service error: {str(e)}")
		raise HTTPException(status_code=500, detail="Failed to generate batch")
	except HTTPException:
		raise
	except Exception as e:
		logger.error(f"Unexpected error: {str(e)}")
		raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/challenge/types")
async def get_challenge_types():
	"""Retorna os tipos de desafios disponíveis."""
	return JSONResponse(
		content={
			"types": challenge_service.get_available_types(),
		}
	)


@app.get("/challenge/levels")
async def get_challenge_levels():
	"""Retorna os níveis de dificuldade disponíveis."""
	return JSONResponse(
		content={
			"levels": challenge_service.get_available_levels(),
		}
	)
