"""Tests for the MockRedisClient (FIFO queue behavior)."""

import json
import asyncio
from src.integrations.redis import MockRedisClient


SAMPLE_CHALLENGE = {
    "id": "test-123",
    "type": "algorithm",
    "level": "easy",
    "title": "Test Challenge",
    "description": "A test challenge",
    "example_input": "test",
    "example_output": "test",
    "created_at": "2024-01-01T00:00:00",
}


class TestMockRedisClient:
    def _make(self, **overrides):
        return {**SAMPLE_CHALLENGE, **overrides}

    def test_init(self):
        rc = MockRedisClient()
        assert rc.storage == []

    def test_push_challenge(self):
        async def run():
            rc = MockRedisClient()
            result = await rc.push_challenge(self._make())
            assert result is True
            assert len(rc.storage) == 1

        asyncio.run(run())

    def test_push_multiple(self):
        async def run():
            rc = MockRedisClient()
            for i in range(3):
                await rc.push_challenge(self._make(id=f"test-{i}"))
            assert len(rc.storage) == 3

        asyncio.run(run())

    def test_get_challenge(self):
        async def run():
            rc = MockRedisClient()
            await rc.push_challenge(self._make())
            raw = await rc.get_challenge()
            assert raw is not None
            data = json.loads(raw)
            assert data["id"] == "test-123"
            assert len(rc.storage) == 0

        asyncio.run(run())

    def test_get_challenge_empty(self):
        async def run():
            rc = MockRedisClient()
            result = await rc.get_challenge()
            assert result is None

        asyncio.run(run())

    def test_push_batch(self):
        async def run():
            rc = MockRedisClient()
            batch = [self._make(id=f"test-{i}") for i in range(5)]
            result = await rc.push_challenges_batch(batch)
            assert result is True
            assert len(rc.storage) == 5

        asyncio.run(run())

    def test_get_pool_size(self):
        async def run():
            rc = MockRedisClient()
            await rc.push_challenge(self._make())
            assert await rc.get_pool_size() == 1

        asyncio.run(run())

    def test_close_clears_storage(self):
        async def run():
            rc = MockRedisClient()
            await rc.push_challenge(self._make())
            await rc.close()
            assert len(rc.storage) == 0

        asyncio.run(run())

    def test_fifo_order(self):
        async def run():
            rc = MockRedisClient()
            for i in range(3):
                await rc.push_challenge(self._make(id=f"test-{i}"))

            for i in range(3):
                raw = await rc.get_challenge()
                data = json.loads(raw)
                assert data["id"] == f"test-{i}"

        asyncio.run(run())
