"""Unit tests for the Redis client module (mocked)."""

import json
from unittest.mock import patch, MagicMock

from src import redis_client as rc


class TestRedisClient:
    @patch("src.redis_client.get_client")
    def test_get_pool_size(self, mock_get_client):
        mock_redis = MagicMock()
        mock_redis.llen.return_value = 42
        mock_get_client.return_value = mock_redis

        assert rc.get_pool_size() == 42
        mock_redis.llen.assert_called_once_with("challenge_pool")

    @patch("src.redis_client.get_client")
    def test_get_pool_size_returns_zero_on_error(self, mock_get_client):
        import redis

        mock_redis = MagicMock()
        mock_redis.llen.side_effect = redis.RedisError("down")
        mock_get_client.return_value = mock_redis

        assert rc.get_pool_size() == 0

    @patch("src.redis_client.get_client")
    def test_push_challenge(self, mock_get_client):
        mock_redis = MagicMock()
        mock_get_client.return_value = mock_redis

        challenge = {"id": "c1", "title": "Test"}
        assert rc.push_challenge(challenge) is True
        mock_redis.rpush.assert_called_once_with(
            "challenge_pool", json.dumps(challenge)
        )

    @patch("src.redis_client.get_client")
    def test_push_challenge_returns_false_on_error(self, mock_get_client):
        import redis

        mock_redis = MagicMock()
        mock_redis.rpush.side_effect = redis.RedisError("down")
        mock_get_client.return_value = mock_redis

        assert rc.push_challenge({"id": "c1"}) is False

    @patch("src.redis_client.get_client")
    def test_push_challenges_batch(self, mock_get_client):
        mock_pipe = MagicMock()
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_pipe
        mock_get_client.return_value = mock_redis

        challenges = [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}]
        assert rc.push_challenges_batch(challenges) == 3
        assert mock_pipe.rpush.call_count == 3
        mock_pipe.execute.assert_called_once()

    @patch("src.redis_client.get_client")
    def test_ping_success(self, mock_get_client):
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_get_client.return_value = mock_redis

        assert rc.ping() is True

    @patch("src.redis_client.get_client")
    def test_ping_failure(self, mock_get_client):
        import redis

        mock_redis = MagicMock()
        mock_redis.ping.side_effect = redis.RedisError("down")
        mock_get_client.return_value = mock_redis

        assert rc.ping() is False
