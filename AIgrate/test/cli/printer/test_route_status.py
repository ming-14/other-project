import pytest
from core.models import AIPool, ApiKeyConfig, ModelOverride, ErrorConfig
from core.pool.router import PoolRouter
from cli.printer.route_status import _status_dot, route_status


def _make_pool_and_router():
    pool = AIPool(
        name="test-pool",
        keys=[
            ApiKeyConfig(
                base_url="https://api1.example.com/v1",
                api_key="sk-key1",
                label="Key1",
                errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=1),
                models={"model-a": ModelOverride(model_id="model-a")},
            ),
        ],
    )
    router = PoolRouter(pool)
    return pool, router


class TestStatusDot:
    def test_available(self):
        assert _status_dot(True, 0) == "+"

    def test_permanently_disabled(self):
        assert _status_dot(False, -1) == "x"

    def test_temporarily_disabled(self):
        assert _status_dot(False, 5.0) == "o"


class TestRouteStatus:
    def test_shows_pool_name(self, capsys):
        pool, router = _make_pool_and_router()
        route_status(pool, router)
        captured = capsys.readouterr()
        assert "test-pool" in captured.out

    def test_shows_model_available(self, capsys):
        pool, router = _make_pool_and_router()
        route_status(pool, router)
        captured = capsys.readouterr()
        assert "model-a" in captured.out
        assert "可用" in captured.out

    def test_shows_key_label(self, capsys):
        pool, router = _make_pool_and_router()
        route_status(pool, router)
        captured = capsys.readouterr()
        assert "Key1" in captured.out

    def test_shows_disabled_after_errors(self, capsys):
        pool, router = _make_pool_and_router()
        ki, mid, kc, mo = router.select_entry()
        for _ in range(3):
            router.report_error(ki, mid, kc)
        route_status(pool, router)
        captured = capsys.readouterr()
        assert "禁用" in captured.out

    def test_shows_cooldown_info(self, capsys):
        pool, router = _make_pool_and_router()
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        route_status(pool, router)
        captured = capsys.readouterr()
        assert "冷却" in captured.out or "等待" in captured.out

    def test_multiple_keys(self, capsys):
        pool = AIPool(
            name="multi-pool",
            keys=[
                ApiKeyConfig(
                    base_url="https://api1.example.com/v1",
                    api_key="sk-key1",
                    label="Key1",
                    errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=1),
                    models={"m1": ModelOverride(model_id="m1")},
                ),
                ApiKeyConfig(
                    base_url="https://api2.example.com/v1",
                    api_key="sk-key2",
                    label="Key2",
                    errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=1),
                    models={"m2": ModelOverride(model_id="m2")},
                ),
            ],
        )
        router = PoolRouter(pool)
        route_status(pool, router)
        captured = capsys.readouterr()
        assert "Key1" in captured.out
        assert "Key2" in captured.out