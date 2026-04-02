# Valida o fluxo completo de requisição através das camadas do sistema,
# garantindo que os padrões arquiteturais estão corretamente implementados:
#
#  - Cache-Aside (Redis como fonte primária)
#  - Fallback (PostgreSQL como fonte secundária)
#  - Load Shedding (503 quando ambas as fontes indisponíveis)
#  - Geração → Pool → Consumo (ciclo completo via MockRedisClient)
#  - Prioridade de fontes (Redis SEMPRE antes do PostgreSQL)
#  - Resiliência a múltiplas requisições consecutivas

# Uso:
#   # A partir do diretório services/challenge-engine
#   python -m pytest test_challenge_flow.py -v


import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

import src.main as main_module
from src.main import app
from src.integrations.redis import MockRedisClient
from src.generators.challenge_generator import ChallengeType, ChallengeLevel
from src.services.challenge_service import ChallengeService


client = TestClient(app)


def _make_redis_mock(challenge_value):
    """
    Cria um mock do RedisClientImpl compatível com o main.py do Mateus.
    O main.py acessa redis_client.get_challenge() diretamente (não via função standalone).
    """
    mock = MagicMock()
    mock.get_challenge = AsyncMock(return_value=challenge_value)
    mock.ping = AsyncMock(return_value=True)
    mock.get_pool_size = AsyncMock(return_value=1)
    return mock


# Fluxo 1 — GET /challenge com Redis disponível
# Padrão validado: Cache-Aside


class TestFluxoRedisDisponivel:
    """Redis tem desafios prontos → deve retorná-los sem chamar o PostgreSQL."""

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_retorna_desafio_do_pool(self, mock_pg):
        """
        Cenário: Redis com desafio disponível.
        Resultado esperado: HTTP 200, source='pool'.
        """
        mock_pg.return_value = None
        redis_mock = _make_redis_mock(
            json.dumps(
                {
                    "id": "abc-123",
                    "title": "Two Sum",
                    "type": "algorithm",
                    "level": "easy",
                }
            )
        )

        with patch.object(main_module, "redis_client", redis_mock):
            resp = client.get("/challenge")

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "pool"
        assert data["challenge"] is not None

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_postgres_nao_e_chamado_quando_redis_responde(self, mock_pg):

        # Padrão Cache-Aside: se Redis responde, o PostgreSQL NUNCA deve ser consultado.

        mock_pg.return_value = "desafio do postgres"
        redis_mock = _make_redis_mock("desafio do redis")

        with patch.object(main_module, "redis_client", redis_mock):
            resp = client.get("/challenge")

        assert resp.status_code == 200
        assert resp.json()["source"] == "pool"
        mock_pg.assert_not_called()  # ← garantia do padrão


# Fluxo 2 — GET /challenge com Redis vazio → fallback para PostgreSQL
# Padrão validado: Fallback


class TestFluxoFallbackPostgres:
    """Redis vazio → deve tentar PostgreSQL como fallback."""

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_fallback_para_postgres(self, mock_pg):
        """
        Cenário: Redis vazio, PostgreSQL com dados.
        Resultado esperado: HTTP 200, source='static_fallback'.
        """
        mock_pg.return_value = json.dumps(
            {
                "id": "static-001",
                "title": "Fibonacci Sequence",
                "type": "algorithm",
            }
        )
        redis_mock = _make_redis_mock(None)  # Redis vazio

        with patch.object(main_module, "redis_client", redis_mock):
            resp = client.get("/challenge")

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "static_fallback"
        assert data["challenge"] is not None

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_postgres_e_chamado_quando_redis_vazio(self, mock_pg):
        """
        Padrão Fallback: Redis vazio → PostgreSQL deve ser consultado.
        """
        mock_pg.return_value = "desafio fallback"
        redis_mock = _make_redis_mock(None)

        with patch.object(main_module, "redis_client", redis_mock):
            client.get("/challenge")

        redis_mock.get_challenge.assert_called_once()
        mock_pg.assert_called_once()

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_fallback_quando_redis_ausente(self, mock_pg):
        """
        Cenário: redis_client é None (sem conexão) → vai direto para PostgreSQL.
        """
        mock_pg.return_value = "desafio pg sem redis"

        with patch.object(main_module, "redis_client", None):
            resp = client.get("/challenge")

        assert resp.status_code == 200
        assert resp.json()["source"] == "static_fallback"


# Fluxo 3 — GET /challenge sem nenhuma fonte disponível
# Padrão validado: Load Shedding (503)


class TestFluxoLoadShedding:
    """Redis e PostgreSQL vazios → deve retornar 503."""

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_retorna_503_quando_sem_desafios(self, mock_pg):
        """
        Padrão Load Shedding: sem fontes disponíveis, o sistema rejeita
        a requisição com 503 Service Unavailable.
        """
        mock_pg.return_value = None
        redis_mock = _make_redis_mock(None)

        with patch.object(main_module, "redis_client", redis_mock):
            resp = client.get("/challenge")

        assert resp.status_code == 503
        assert resp.json()["detail"] == "No challenge available."

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_503_sem_redis_e_sem_postgres(self, mock_pg):
        """Redis None + PostgreSQL vazio → 503."""
        mock_pg.return_value = None

        with patch.object(main_module, "redis_client", None):
            resp = client.get("/challenge")

        assert resp.status_code == 503

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_503_ainda_tenta_ambas_fontes(self, mock_pg):
        """
        Mesmo no 503, Redis e PostgreSQL devem ter sido tentados.
        """
        mock_pg.return_value = None
        redis_mock = _make_redis_mock(None)

        with patch.object(main_module, "redis_client", redis_mock):
            client.get("/challenge")

        redis_mock.get_challenge.assert_called_once()
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
        """
        from src.integrations.redis import RedisConnectionError

        redis_falho = AsyncMock()
        redis_falho.push_challenge.side_effect = RedisConnectionError("timeout")

        service = ChallengeService(redis_client=redis_falho)
        challenge = await service.generate_and_save()

        assert challenge is not None
        assert challenge.id is not None


# Fluxo 5 — Prioridade de fontes


class TestPrioridadeDeFontes:
    """Valida a hierarquia: Redis > PostgreSQL > 503."""

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_redis_vence_sobre_postgres(self, mock_pg):
        """Quando ambos estão disponíveis, Redis DEVE vencer."""
        mock_pg.return_value = "desafio_postgres"
        redis_mock = _make_redis_mock("desafio_redis")

        with patch.object(main_module, "redis_client", redis_mock):
            resp = client.get("/challenge")

        assert resp.status_code == 200
        assert resp.json()["source"] == "pool"
        assert resp.json()["challenge"] == "desafio_redis"
        mock_pg.assert_not_called()

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_sequencia_redis_esgotado_depois_postgres_esgotado(self, mock_pg):
        """
        Simula a sequência real de operação do sistema:
          - Requisições 1-2: Redis com desafios
          - Requisição 3: Redis vazio, PostgreSQL com fallback
          - Requisição 4: ambos vazios → 503
        """
        redis_mock = MagicMock()
        redis_mock.get_challenge = AsyncMock(
            side_effect=["challenge_1", "challenge_2", None, None]
        )
        mock_pg.side_effect = ["fallback_1", None]

        with patch.object(main_module, "redis_client", redis_mock):
            respostas = [client.get("/challenge") for _ in range(4)]

        assert respostas[0].json()["source"] == "pool"  # Redis
        assert respostas[1].json()["source"] == "pool"  # Redis
        assert respostas[2].json()["source"] == "static_fallback"  # Fallback PG
        assert respostas[3].status_code == 503  # Load Shedding


# Fluxo 6 — Health check


class TestHealthCheck:
    """O endpoint /health deve estar sempre disponível."""

    def test_health_retorna_200(self):
        """
        /health deve retornar HTTP 200 independente do estado do Redis.
        O corpo pode ser 'healthy' ou 'degraded' dependendo da conexão.
        """
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded")

    def test_health_com_redis_conectado(self):
        """Com Redis mockado e respondendo, health deve retornar 'healthy'."""
        redis_mock = MagicMock()
        redis_mock.ping = AsyncMock(return_value=True)
        redis_mock.get_pool_size = AsyncMock(return_value=5)

        with patch.object(main_module, "redis_client", redis_mock):
            resp = client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["redis"]["connected"] is True
        assert data["redis"]["pool_size"] == 5

    def test_health_sem_redis_retorna_degraded(self):
        """
        Sem Redis, health retorna 'degraded' mas ainda HTTP 200.
        O sistema continua operacional (fallback para PostgreSQL).
        """
        with patch.object(main_module, "redis_client", None):
            resp = client.get("/health")

        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"

    def test_health_nunca_retorna_5xx(self):
        """Health check nunca deve retornar erro de servidor."""
        resp = client.get("/health")
        assert resp.status_code < 500
