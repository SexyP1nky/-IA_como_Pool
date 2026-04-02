import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from src.main import app
from src.generators.challenge_generator import Challenge, ChallengeType, ChallengeLevel
from src.services.challenge_service import ChallengeServiceError

client = TestClient(app)

def _make_mock_challenge(id="test-gen-1"):
    return Challenge(
        id=id,
        type=ChallengeType.ALGORITHM,
        level=ChallengeLevel.EASY,
        title="Mock Title",
        description="Mock Desc",
        example_input="in",
        example_output="out",
        created_at="2026-01-01T00:00:00"
    )

class TestGenerateEndpoints:
    
    @patch("src.main.get_challenge_service")
    def test_generate_challenge_success(self, mock_get_service):
        mock_service = AsyncMock()
        mock_service.generate_and_save.return_value = _make_mock_challenge()
        mock_get_service.return_value = mock_service

        response = client.post("/challenge/generate?challenge_type=algorithm&level=easy")
        
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "generated"
        assert data["id"] == "test-gen-1"
        assert "challenge" in data
        
        mock_service.generate_and_save.assert_called_once_with(
            challenge_type=ChallengeType.ALGORITHM,
            level=ChallengeLevel.EASY
        )

    def test_generate_challenge_invalid_type(self):
        response = client.post("/challenge/generate?challenge_type=invalid_type")
        assert response.status_code == 400
        assert "Invalid challenge_type" in response.json()["detail"]

    def test_generate_challenge_invalid_level(self):
        response = client.post("/challenge/generate?level=super_hard")
        assert response.status_code == 400
        assert "Invalid level" in response.json()["detail"]

    @patch("src.main.get_challenge_service")
    def test_generate_challenge_service_error_returns_500(self, mock_get_service):
        mock_service = AsyncMock()
        mock_service.generate_and_save.side_effect = ChallengeServiceError("Service failure")
        mock_get_service.return_value = mock_service

        response = client.post("/challenge/generate")
        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to generate challenge"

    @patch("src.main.get_challenge_service")
    def test_generate_batch_success(self, mock_get_service):
        mock_service = AsyncMock()
        mock_service.generate_and_save_batch.return_value = [
            _make_mock_challenge("batch-1"),
            _make_mock_challenge("batch-2")
        ]
        mock_get_service.return_value = mock_service

        response = client.post("/challenge/generate-batch?count=2")
        
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "generated"
        assert data["count"] == 2
        assert len(data["challenges"]) == 2
        
        mock_service.generate_and_save_batch.assert_called_once_with(
            count=2,
            challenge_type=None
        )

    def test_generate_batch_invalid_count_out_of_bounds(self):
        # The route expects ge=1, le=100
        response = client.post("/challenge/generate-batch?count=0")
        assert response.status_code == 422 # FastAPI validation error
        
        response = client.post("/challenge/generate-batch?count=101")
        assert response.status_code == 422 # FastAPI validation error

class TestMetadataEndpoints:
    
    @patch("src.main.get_challenge_service")
    def test_get_challenge_types(self, mock_get_service):
        from unittest.mock import MagicMock
        mock_service = MagicMock()
        mock_service.get_available_types.return_value = ["algorithm", "math"]
        mock_get_service.return_value = mock_service

        response = client.get("/challenge/types")
        assert response.status_code == 200
        assert response.json() == {"types": ["algorithm", "math"]}

    @patch("src.main.get_challenge_service")
    def test_get_challenge_levels(self, mock_get_service):
        from unittest.mock import MagicMock
        mock_service = MagicMock()
        mock_service.get_available_levels.return_value = ["easy", "hard"]
        mock_get_service.return_value = mock_service

        response = client.get("/challenge/levels")
        assert response.status_code == 200
        assert response.json() == {"levels": ["easy", "hard"]}
