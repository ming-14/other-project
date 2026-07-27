import pytest
from core.models import AIPool, ApiKeyConfig, ModelOverride, ErrorConfig, LimitRule
from cli.printer.pool_display import print_pools, print_pool_detail


def _make_pool():
    return AIPool(
        name="test-pool",
        keys=[
            ApiKeyConfig(
                base_url="https://api1.example.com/v1",
                api_key="sk-key1abcdef",
                label="Key1",
                errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=40),
                models={"model-a": ModelOverride(model_id="model-a")},
            ),
        ],
    )


class TestPrintPools:
    def test_with_names(self, capsys):
        print_pools(["pool1", "pool2"])
        captured = capsys.readouterr()
        assert "pool1" in captured.out
        assert "pool2" in captured.out

    def test_empty_list(self, capsys):
        print_pools([])
        captured = capsys.readouterr()
        assert "暂无" in captured.out

    def test_single_pool(self, capsys):
        print_pools(["my-pool"])
        captured = capsys.readouterr()
        assert "my-pool" in captured.out


class TestPrintPoolDetail:
    def test_shows_pool_name(self, capsys):
        pool = _make_pool()
        print_pool_detail(pool)
        captured = capsys.readouterr()
        assert "test-pool" in captured.out

    def test_shows_key_label(self, capsys):
        pool = _make_pool()
        print_pool_detail(pool)
        captured = capsys.readouterr()
        assert "Key1" in captured.out

    def test_shows_url(self, capsys):
        pool = _make_pool()
        print_pool_detail(pool)
        captured = capsys.readouterr()
        assert "https://api1.example.com/v1" in captured.out

    def test_shows_model(self, capsys):
        pool = _make_pool()
        print_pool_detail(pool)
        captured = capsys.readouterr()
        assert "model-a" in captured.out

    def test_shows_rate_limits(self, capsys):
        pool = AIPool(
            name="rl-pool",
            keys=[
                ApiKeyConfig(
                    base_url="https://api1.example.com/v1",
                    api_key="sk-key1",
                    label="Key1",
                    errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=40),
                    rate_limits=[LimitRule(type="count_per_time", time=60, count=10)],
                    models={"m1": ModelOverride(model_id="m1")},
                ),
            ],
        )
        print_pool_detail(pool)
        captured = capsys.readouterr()
        assert "限流" in captured.out

    def test_shows_model_overrides(self, capsys):
        pool = AIPool(
            name="override-pool",
            keys=[
                ApiKeyConfig(
                    base_url="https://api1.example.com/v1",
                    api_key="sk-key1",
                    label="Key1",
                    errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=40),
                    models={
                        "m1": ModelOverride(model_id="m1", max_concurrency=5, timeout=120),
                    },
                ),
            ],
        )
        print_pool_detail(pool)
        captured = capsys.readouterr()
        assert "并发=5" in captured.out
        assert "超时=120" in captured.out

    def test_empty_pool(self, capsys):
        pool = AIPool(name="empty", keys=[])
        print_pool_detail(pool)
        captured = capsys.readouterr()
        assert "empty" in captured.out