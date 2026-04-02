"""Unit tests for the LLM client and circuit breaker."""

from unittest.mock import patch

from src.llm_client import (
    CircuitBreaker,
    generate_challenge,
    _generate_mock,
    _parse_llm_response,
    LLMError,
)


class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        assert cb.is_open is False
        assert cb.allow_request() is True

    def test_opens_after_threshold_failures(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        cb.record_failure()
        assert cb.is_open is False
        cb.record_failure()
        assert cb.is_open is True
        assert cb.allow_request() is False

    def test_success_resets_failures(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.is_open is False

    def test_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0)
        cb.record_failure()
        assert cb.is_open is True
        assert cb.allow_request() is True  # timeout=0 means immediate recovery


class TestMockGenerator:
    def test_returns_valid_challenge(self):
        result = _generate_mock("algorithm", "easy")
        assert "title" in result
        assert "description" in result
        assert "example_input" in result
        assert "example_output" in result

    def test_fallback_when_no_exact_match(self):
        result = _generate_mock("algorithm", "impossible_level")
        assert "title" in result


class TestParseLLMResponse:
    def test_parses_clean_json(self):
        raw = '{"title":"T","description":"D","example_input":"I","example_output":"O"}'
        data = _parse_llm_response(raw)
        assert data["title"] == "T"

    def test_strips_markdown_fences(self):
        raw = '```json\n{"title":"T","description":"D","example_input":"I","example_output":"O"}\n```'
        data = _parse_llm_response(raw)
        assert data["title"] == "T"

    def test_raises_on_missing_field(self):
        import pytest

        raw = '{"title":"T","description":"D"}'
        with pytest.raises(LLMError, match="Missing required field"):
            _parse_llm_response(raw)


class TestGenerateChallenge:
    @patch("src.llm_client._select_provider")
    def test_uses_mock_when_llm_disabled(self, mock_select):
        mock_select.return_value = (_generate_mock, "mock")
        result = generate_challenge("algorithm", "easy")
        assert result["id"]
        assert result["type"] == "algorithm"
        assert result["level"] == "easy"
        assert result["metadata"]["source"] == "mock"

    @patch("src.llm_client._select_provider")
    def test_falls_back_on_llm_failure(self, mock_select):
        def failing_provider(ct, lv):
            raise Exception("API down")

        mock_select.return_value = (failing_provider, "gemini")
        result = generate_challenge("math", "hard")
        assert result["metadata"]["source"] == "mock_fallback"
