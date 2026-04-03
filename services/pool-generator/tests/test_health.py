"""Smoke tests: verify the Celery app loads and tasks are registered."""

from src.main import app


class TestCeleryAppBootstrap:
    def test_app_is_celery_instance(self):
        from celery import Celery

        assert isinstance(app, Celery)

    def test_refill_pool_task_registered(self):
        assert "src.main.refill_pool" in app.tasks

    def test_generate_single_challenge_task_registered(self):
        assert "src.main.generate_single_challenge" in app.tasks

    def test_beat_schedule_contains_refill(self):
        assert "refill-pool-periodically" in app.conf.beat_schedule
