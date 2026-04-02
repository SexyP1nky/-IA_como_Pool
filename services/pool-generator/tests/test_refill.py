"""Unit tests for the refill_pool and generate_single_challenge tasks."""

from unittest.mock import patch

from src.main import refill_pool, generate_single_challenge


class TestRefillPool:
    @patch("src.main.generate_single_challenge")
    @patch("src.redis_client.get_pool_size", return_value=50)
    def test_skips_when_pool_is_healthy(self, mock_size, mock_gen):
        result = refill_pool()
        assert result["status"] == "ok"
        assert result["generated"] == 0
        mock_gen.delay.assert_not_called()

    @patch("src.main.generate_single_challenge")
    @patch("src.redis_client.get_pool_size", return_value=3)
    def test_dispatches_tasks_when_pool_below_min(self, mock_size, mock_gen):
        result = refill_pool()
        assert result["status"] == "refilling"
        expected_dispatched = 50 - 3  # POOL_TARGET_SIZE - current
        assert result["dispatched"] == expected_dispatched
        assert mock_gen.delay.call_count == expected_dispatched

    @patch("src.main.generate_single_challenge")
    @patch("src.redis_client.get_pool_size", return_value=0)
    def test_dispatches_full_target_when_pool_empty(self, mock_size, mock_gen):
        result = refill_pool()
        assert result["status"] == "refilling"
        assert result["dispatched"] == 50
        assert mock_gen.delay.call_count == 50

    @patch("src.main.generate_single_challenge")
    @patch("src.redis_client.get_pool_size", return_value=10)
    def test_exactly_at_min_threshold_skips(self, mock_size, mock_gen):
        """Pool at exactly POOL_MIN_SIZE should NOT trigger refill."""
        result = refill_pool()
        assert result["status"] == "ok"
        mock_gen.delay.assert_not_called()


class TestGenerateSingleChallenge:
    @patch("src.redis_client.push_challenge", return_value=True)
    @patch(
        "src.llm_client.generate_challenge",
        return_value={
            "id": "test-123",
            "type": "algorithm",
            "level": "easy",
            "title": "Test",
            "description": "Desc",
            "example_input": "in",
            "example_output": "out",
            "created_at": "2026-01-01T00:00:00",
            "metadata": {"source": "mock", "generator_version": "2.0"},
        },
    )
    def test_generates_and_pushes(self, mock_llm, mock_push):
        result = generate_single_challenge()
        assert result["id"] == "test-123"
        mock_llm.assert_called_once()
        mock_push.assert_called_once()

    @patch("src.redis_client.push_challenge", return_value=False)
    @patch(
        "src.llm_client.generate_challenge",
        return_value={
            "id": "test-456",
            "type": "math",
            "level": "hard",
            "title": "T",
            "description": "D",
            "example_input": "i",
            "example_output": "o",
            "created_at": "2026-01-01T00:00:00",
            "metadata": {"source": "mock", "generator_version": "2.0"},
        },
    )
    def test_raises_when_redis_push_fails(self, mock_llm, mock_push):
        import pytest

        with pytest.raises(RuntimeError, match="Failed to push"):
            generate_single_challenge()
