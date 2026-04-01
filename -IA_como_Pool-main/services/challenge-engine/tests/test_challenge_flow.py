"""
Testes de Fluxo


Valida o fluxo completo de requisição através das camadas do sistema,
garantindo que os padrões arquiteturais estão corretamente implementados:

  - Cache-Aside (Redis como fonte primária)
  - Fallback (PostgreSQL como fonte secundária)
  - Load Shedding (503 quando ambas as fontes indisponíveis)
  - Geração → Pool → Consumo (ciclo completo via MockRedisClient)
  - Prioridade de fontes (Redis SEMPRE antes do PostgreSQL)
  - Resiliência a múltiplas requisições consecutivas

Uso:
    # A partir do diretório services/challenge-engine
    pytest tests/test_challenge_flow.py -v
"""

import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from src.main import app
from src.integrations.redis import MockRedisClient
from src.generators.challenge_generator import ChallengeType, ChallengeLevel
from src.services.challenge_service import ChallengeService


client = TestClient(app)


# Fluxo 1 — GET /challenge com Redis disponível
# Padrão validado: Cache-Aside

class TestFluxoRedisDisponivel:
    """Redis tem desafios prontos → deve retorná-los sem chamar o PostgreSQL."""

    @patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_retorna_desafio_do_pool(self, mock_pg, mock_redis):
        """
        Cenário: Redis com desafio disponível.
        Resultado esperado: HTTP 200, source='pool'.
        """
        mock_redis.return_value = json.dumps({
            "id": "abc-123",
            "title": "Two Sum",
            "type": "algorithm",
            "level": "easy",
        })
        mock_pg.return_value = None

        resp = client.get("/challenge")

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "pool"
        assert data["challenge"] is not None

    @patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_postgres_nao_e_chamado_quando_redis_responde(self, mock_pg, mock_redis):
        """
        Padrão Cache-Aside: se Redis responde, o PostgreSQL NUNCA deve ser consultado.
        """
        mock_redis.return_value = "desafio do redis"
        mock_pg.return_value = "desafio do postgres"  # não deve ser usado

        resp = client.get("/challenge")

        assert resp.status_code == 200
        assert resp.json()["source"] == "pool"
        mock_redis.assert_called_once()
        mock_pg.assert_not_called()  # ← garantia do padrão


# Fluxo 2 — GET /challenge com Redis vazio → fallback para PostgreSQL
# Padrão validado: Fallback

class TestFluxoFallbackPostgres:
    """Redis vazio → deve tentar PostgreSQL como fallback."""

    @patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_fallback_para_postgres(self, mock_pg, mock_redis):
        """
        Cenário: Redis vazio, PostgreSQL com dados.
        Resultado esperado: HTTP 200, source='static_fallback'.
        """
        mock_redis.return_value = None
        mock_pg.return_value = json.dumps({
            "id": "static-001",
            "title": "Fibonacci Sequence",
            "type": "algorithm",
        })

        resp = client.get("/challenge")

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "static_fallback"
        assert data["challenge"] is not None

    @patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_ambas_fontes_sao_consultadas_no_fallback(self, mock_pg, mock_redis):
        """
        Padrão Fallback: quando Redis está vazio, AMBAS as funções devem ser chamadas.
        """
        mock_redis.return_value = None
        mock_pg.return_value = "desafio fallback"

        client.get("/challenge")

        mock_redis.assert_called_once()
        mock_pg.assert_called_once()


# Fluxo 3 — GET /challenge sem nenhuma fonte disponível
# Padrão validado: Load Shedding (503)

class TestFluxoLoadShedding:
    """Redis e PostgreSQL vazios → deve retornar 503."""

    @patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_retorna_503_quando_sem_desafios(self, mock_pg, mock_redis):
        """
        Padrão Load Shedding: sem fontes disponíveis, o sistema rejeita
        a requisição com 503 Service Unavailable.
        """
        mock_redis.return_value = None
        mock_pg.return_value = None

        resp = client.get("/challenge")

        assert resp.status_code == 503
        assert resp.json()["detail"] == "No challenge available."

    @patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_503_ainda_consulta_ambas_fontes(self, mock_pg, mock_redis):
        """
        Mesmo no cenário de 503, as duas fontes DEVEM ter sido tentadas.
        Garante que o fallback foi de fato executado antes do Load Shedding.
        """
        mock_redis.return_value = None
        mock_pg.return_value = None

        client.get("/challenge")

        mock_redis.assert_called_once()
        mock_pg.assert_called_once()


# Fluxo 4 — Ciclo completo: geração → pool → consumo
# Padrão validado: Cache-Aside + FIFO Queue

class TestFluxoGeracaoEConsumo:
    """Valida o ciclo completo: ChallengeService gera e salva; Redis entrega."""

    @pytest.mark.asyncio
    async def test_ciclo_completo_geracao_consumo(self):
        """
        Fluxo completo:
          1. ChallengeService.generate_and_save() → gera desafio e salva no Redis
          2. MockRedisClient armazena o desafio (FIFO)
          3. get_challenge() retorna o desafio correto
          4. Pool fica vazio após o consumo
        """
        redis_mock = MockRedisClient()
        service = ChallengeService(redis_client=redis_mock)

        # 1. Gera e salva
        challenge = await service.generate_and_save(
            challenge_type=ChallengeType.ALGORITHM,
            level=ChallengeLevel.EASY,
        )

        # 2. Verifica que foi para o pool
        assert await redis_mock.get_pool_size() == 1

        # 3. Consome do pool e valida dados
        raw = await redis_mock.get_challenge()
        assert raw is not None
        data = json.loads(raw)
        assert data["id"] == challenge.id
        assert data["type"] == "algorithm"
        assert data["level"] == "easy"

        # 4. Pool deve estar vazio após consumo
        assert await redis_mock.get_pool_size() == 0

    @pytest.mark.asyncio
    async def test_batch_mantem_ordem_fifo(self):
        """
        Padrão FIFO: desafios devem ser entregues na mesma ordem que foram inseridos.
        """
        redis_mock = MockRedisClient()
        service = ChallengeService(redis_client=redis_mock)

        challenges = await service.generate_and_save_batch(count=3)
        ids_inseridos = [c.id for c in challenges]

        ids_consumidos = []
        for _ in range(3):
            raw = await redis_mock.get_challenge()
            data = json.loads(raw)
            ids_consumidos.append(data["id"])

        assert ids_inseridos == ids_consumidos  # garante FIFO

    @pytest.mark.asyncio
    async def test_redis_indisponivel_nao_bloqueia_geracao(self):
        """
        Resiliência: se o Redis falha ao salvar, a geração do desafio
        ainda deve ser concluída com sucesso (non-blocking).
        Padrão: não há acoplamento forte entre geração e persistência.
        """
        from unittest.mock import AsyncMock
        from src.integrations.redis import RedisConnectionError

        redis_falho = AsyncMock()
        redis_falho.push_challenge.side_effect = RedisConnectionError("timeout")

        service = ChallengeService(redis_client=redis_falho)
        challenge = await service.generate_and_save()

        # Geração deve ter ocorrido mesmo com Redis falhando
        assert challenge is not None
        assert challenge.id is not None


# Fluxo 5 — Prioridade de fontes

class TestPrioridadeDeFontes:
    """Valida a hierarquia: Redis > PostgreSQL > 503."""

    @patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_redis_vence_sobre_postgres(self, mock_pg, mock_redis):
        """Quando ambos estão disponíveis, Redis DEVE vencer."""
        mock_redis.return_value = "desafio_redis"
        mock_pg.return_value = "desafio_postgres"

        resp = client.get("/challenge")

        assert resp.status_code == 200
        assert resp.json()["source"] == "pool"
        assert resp.json()["challenge"] == "desafio_redis"
        mock_pg.assert_not_called()

    @patch("src.main.get_challenge_from_redis", new_callable=AsyncMock)
    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_sequencia_redis_esgotado_depois_postgres_esgotado(self, mock_pg, mock_redis):
        """
        Simula a sequência real de operação do sistema:
          - Requisições 1-2: Redis com desafios
          - Requisições 3: Redis vazio, PostgreSQL com fallback
          - Requisição 4: ambos vazios → 503
        """
        mock_redis.side_effect = ["challenge_1", "challenge_2", None, None]
        mock_pg.side_effect = [None, None, "fallback_1", None]

        respostas = [client.get("/challenge") for _ in range(4)]

        assert respostas[0].json()["source"] == "pool"           # Redis
        assert respostas[1].json()["source"] == "pool"           # Redis
        assert respostas[2].json()["source"] == "static_fallback"  # Fallback PG
        assert respostas[3].status_code == 503                   # Load Shedding


# Fluxo 6 — Health check

class TestHealthCheck:
    """O endpoint /health deve estar sempre disponível."""

    def test_health_retorna_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}

    def test_health_independe_do_redis(self):
        """Health check não deve depender do estado do Redis ou PostgreSQL."""
        resp = client.get("/health")
        assert resp.status_code == 200
