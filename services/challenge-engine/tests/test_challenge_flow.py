# Validates the request flow through system layers, ensuring architectural
# patterns are correctly implemented:
#
#  - Cache-Aside (Redis as primary source)
#  - Fallback (PostgreSQL as secondary source)
#  - Load Shedding (503 when both sources unavailable)
#  - Source priority (Redis ALWAYS before PostgreSQL)
#  - Resilience across multiple consecutive requests

import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

import src.main as main_module
from src.main import app


client = TestClient(app)


def _make_redis_mock(challenge_value):
    mock = MagicMock()
    mock.get_challenge = AsyncMock(return_value=challenge_value)
    mock.ping = AsyncMock(return_value=True)
    mock.get_pool_size = AsyncMock(return_value=1)
    return mock


# Fluxo 1 — GET /challenge com Redis disponível
# Padrão validado: Cache-Aside


class TestFluxoRedisDisponivel:
    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_retorna_desafio_do_pool(self, mock_pg):
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
        mock_pg.return_value = "desafio do postgres"
        redis_mock = _make_redis_mock("desafio do redis")

        with patch.object(main_module, "redis_client", redis_mock):
            resp = client.get("/challenge")

        assert resp.status_code == 200
        assert resp.json()["source"] == "pool"
        mock_pg.assert_not_called()


# Fluxo 2 — GET /challenge com Redis vazio → fallback para PostgreSQL
# Padrão validado: Fallback


class TestFluxoFallbackPostgres:
    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_fallback_para_postgres(self, mock_pg):
        mock_pg.return_value = json.dumps(
            {
                "id": "static-001",
                "title": "Fibonacci Sequence",
                "type": "algorithm",
            }
        )
        redis_mock = _make_redis_mock(None)

        with patch.object(main_module, "redis_client", redis_mock):
            resp = client.get("/challenge")

        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "static_fallback"
        assert data["challenge"] is not None

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_postgres_e_chamado_quando_redis_vazio(self, mock_pg):
        mock_pg.return_value = "desafio fallback"
        redis_mock = _make_redis_mock(None)

        with patch.object(main_module, "redis_client", redis_mock):
            client.get("/challenge")

        redis_mock.get_challenge.assert_called_once()
        mock_pg.assert_called_once()

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_fallback_quando_redis_ausente(self, mock_pg):
        mock_pg.return_value = "desafio pg sem redis"

        with patch.object(main_module, "redis_client", None):
            resp = client.get("/challenge")

        assert resp.status_code == 200
        assert resp.json()["source"] == "static_fallback"


# Fluxo 3 — GET /challenge sem nenhuma fonte disponível
# Padrão validado: Load Shedding (503)


class TestFluxoLoadShedding:
    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_retorna_503_quando_sem_desafios(self, mock_pg):
        mock_pg.return_value = None
        redis_mock = _make_redis_mock(None)

        with patch.object(main_module, "redis_client", redis_mock):
            resp = client.get("/challenge")

        assert resp.status_code == 503
        assert resp.json()["detail"] == "No challenge available."

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_503_sem_redis_e_sem_postgres(self, mock_pg):
        mock_pg.return_value = None

        with patch.object(main_module, "redis_client", None):
            resp = client.get("/challenge")

        assert resp.status_code == 503

    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_503_ainda_tenta_ambas_fontes(self, mock_pg):
        mock_pg.return_value = None
        redis_mock = _make_redis_mock(None)

        with patch.object(main_module, "redis_client", redis_mock):
            client.get("/challenge")

        redis_mock.get_challenge.assert_called_once()
        mock_pg.assert_called_once()


# Fluxo 4 — Prioridade de fontes


class TestPrioridadeDeFontes:
    @patch("src.main.get_challenge_from_postgres", new_callable=AsyncMock)
    def test_redis_vence_sobre_postgres(self, mock_pg):
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
        redis_mock = MagicMock()
        redis_mock.get_challenge = AsyncMock(
            side_effect=["challenge_1", "challenge_2", None, None]
        )
        mock_pg.side_effect = ["fallback_1", None]

        with patch.object(main_module, "redis_client", redis_mock):
            respostas = [client.get("/challenge") for _ in range(4)]

        assert respostas[0].json()["source"] == "pool"
        assert respostas[1].json()["source"] == "pool"
        assert respostas[2].json()["source"] == "static_fallback"
        assert respostas[3].status_code == 503


# Fluxo 5 — Health check


class TestHealthCheck:
    def test_health_retorna_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded")

    def test_health_com_redis_conectado(self):
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
        with patch.object(main_module, "redis_client", None):
            resp = client.get("/health")

        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"

    def test_health_nunca_retorna_5xx(self):
        resp = client.get("/health")
        assert resp.status_code < 500
