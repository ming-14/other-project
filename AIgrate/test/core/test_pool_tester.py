import pytest
from unittest.mock import patch, MagicMock
from core.models import AIPool, ApiKeyConfig, ModelOverride, ErrorConfig, LimitRule
from core.pool.tester import (
    TestResult, TestProgress, _resolve_timeout, _resolve_concurrency,
    _wait_rate_limit, run_pool_test,
)
from core.pool.limiter import RateLimiter


def _make_pool(num_keys=1, models_per_key=1, **kwargs):
    keys = []
    for ki in range(num_keys):
        model_dict = {}
        for mi in range(models_per_key):
            mid = f"model-{ki}-{mi}"
            model_dict[mid] = ModelOverride(model_id=mid)
        keys.append(ApiKeyConfig(
            base_url=f"https://api{ki}.example.com/v1",
            api_key=f"sk-key{ki}",
            label=f"Key{ki}",
            errors=ErrorConfig(
                max_concurrency=kwargs.get("max_concurrency", 1),
                timeout=kwargs.get("timeout", 30),
                max_errors=3,
                failure_pause=1,
            ),
            max_requests=kwargs.get("max_requests"),
            models=model_dict,
        ))
    return AIPool(name="test-pool", keys=keys)


class TestTestResult:
    def test_default_values(self):
        r = TestResult(key_idx=0, key_label="K", model_id="m", ok=True)
        assert r.elapsed == 0.0
        assert r.message == ""

    def test_custom_values(self):
        r = TestResult(key_idx=1, key_label="K2", model_id="m2", ok=False, elapsed=1.5, message="err")
        assert r.key_idx == 1
        assert r.ok is False
        assert r.elapsed == 1.5


class TestTestProgress:
    def test_add_pass(self):
        p = TestProgress(total=1)
        r = TestResult(key_idx=0, key_label="K", model_id="m", ok=True)
        p.add(r)
        assert p.done == 1
        assert p.passed == 1
        assert p.failed == 0

    def test_add_fail(self):
        p = TestProgress(total=1)
        r = TestResult(key_idx=0, key_label="K", model_id="m", ok=False)
        p.add(r)
        assert p.done == 1
        assert p.passed == 0
        assert p.failed == 1

    def test_add_multiple(self):
        p = TestProgress(total=3)
        p.add(TestResult(key_idx=0, key_label="K", model_id="m1", ok=True))
        p.add(TestResult(key_idx=0, key_label="K", model_id="m2", ok=False))
        p.add(TestResult(key_idx=0, key_label="K", model_id="m3", ok=True))
        assert p.done == 3
        assert p.passed == 2
        assert p.failed == 1


class TestResolveTimeout:
    def test_model_timeout_takes_priority(self):
        kc = ApiKeyConfig(base_url="", api_key="", errors=ErrorConfig(timeout=30))
        mo = ModelOverride(model_id="m", timeout=60)
        assert _resolve_timeout(kc, mo) == 60

    def test_key_timeout_fallback(self):
        kc = ApiKeyConfig(base_url="", api_key="", errors=ErrorConfig(timeout=45))
        mo = ModelOverride(model_id="m")
        assert _resolve_timeout(kc, mo) == 45

    def test_default_timeout(self):
        kc = ApiKeyConfig(base_url="", api_key="", errors=ErrorConfig(timeout=None))
        mo = ModelOverride(model_id="m")
        assert _resolve_timeout(kc, mo) == 120


class TestResolveConcurrency:
    def test_both_set_takes_min(self):
        kc = ApiKeyConfig(base_url="", api_key="", errors=ErrorConfig(max_concurrency=3))
        mo = ModelOverride(model_id="m", max_concurrency=2)
        assert _resolve_concurrency(kc, mo) == 2

    def test_only_key_set(self):
        kc = ApiKeyConfig(base_url="", api_key="", errors=ErrorConfig(max_concurrency=4))
        mo = ModelOverride(model_id="m")
        assert _resolve_concurrency(kc, mo) == 4

    def test_only_model_set(self):
        kc = ApiKeyConfig(base_url="", api_key="", errors=ErrorConfig(max_concurrency=None))
        mo = ModelOverride(model_id="m", max_concurrency=5)
        assert _resolve_concurrency(kc, mo) == 5

    def test_neither_set_defaults_to_1(self):
        kc = ApiKeyConfig(base_url="", api_key="")
        mo = ModelOverride(model_id="m")
        assert _resolve_concurrency(kc, mo) == 1


class TestWaitRateLimit:
    def test_no_rules_returns_true(self):
        limiter = RateLimiter()
        assert _wait_rate_limit(limiter, "scope", [], None, None) is True

    def test_allowed_returns_true(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="time_per_req", time=5)]
        assert _wait_rate_limit(limiter, "scope", rules, None, None) is True

    def test_stop_check_interrupts(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="time_per_req", time=60)]
        limiter.record("scope")
        assert _wait_rate_limit(limiter, "scope", rules, lambda: True, None) is False


class TestRunPoolTest:
    @patch("core.pool.tester.stream_chat")
    def test_empty_pool(self, mock_stream):
        pool = AIPool(name="empty", keys=[])
        progress = run_pool_test(pool)
        assert progress.total == 0
        assert progress.done == 0

    @patch("core.pool.tester.stream_chat")
    def test_successful_test(self, mock_stream):
        mock_stream.return_value = iter(["Hello"])
        pool = _make_pool(num_keys=1, models_per_key=1)
        progress = run_pool_test(pool)
        assert progress.total == 1
        assert progress.done == 1
        assert progress.passed == 1

    @patch("core.pool.tester.stream_chat")
    def test_failed_test(self, mock_stream):
        mock_stream.side_effect = Exception("connection error")
        pool = _make_pool(num_keys=1, models_per_key=1)
        progress = run_pool_test(pool)
        assert progress.total == 1
        assert progress.done == 1
        assert progress.failed == 1

    @patch("core.pool.tester.stream_chat")
    def test_stop_check_prevents_test(self, mock_stream):
        mock_stream.return_value = iter(["Hi"])
        pool = _make_pool(num_keys=1, models_per_key=1)
        progress = run_pool_test(pool, stop_check=lambda: True)
        assert progress.done == 0

    @patch("core.pool.tester.stream_chat")
    def test_on_progress_callback(self, mock_stream):
        mock_stream.return_value = iter(["Hi"])
        pool = _make_pool(num_keys=1, models_per_key=1)
        results = []
        run_pool_test(pool, on_progress=lambda p, r: results.append(r))
        assert len(results) == 1

    @patch("core.pool.tester.stream_chat")
    def test_multiple_keys(self, mock_stream):
        mock_stream.return_value = iter(["ok"])
        pool = _make_pool(num_keys=2, models_per_key=2)
        progress = run_pool_test(pool)
        assert progress.total == 4
        assert progress.done == 4