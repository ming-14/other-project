import time
import threading
import pytest
from core.pool.limiter import RateLimiter
from core.models import LimitRule


class TestRateLimiterBasic:
    def test_empty_rules_allow(self):
        limiter = RateLimiter()
        ok, wait = limiter.check("scope1", [])
        assert ok is True
        assert wait == 0.0

    def test_no_records_allow(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="time_per_req", time=5)]
        ok, wait = limiter.check("scope1", rules)
        assert ok is True
        assert wait == 0.0

    def test_time_per_req_blocks(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="time_per_req", time=5)]
        limiter.record("scope1")
        ok, wait = limiter.check("scope1", rules)
        assert ok is False
        assert wait > 0

    def test_time_per_req_allows_after_window(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="time_per_req", time=0)]
        limiter.record("scope1")
        time.sleep(0.05)
        ok, wait = limiter.check("scope1", rules)
        assert ok is True

    def test_count_per_time_under_limit(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="count_per_time", time=60, count=5)]
        for _ in range(4):
            limiter.record("scope1")
        ok, wait = limiter.check("scope1", rules)
        assert ok is True

    def test_count_per_time_at_limit(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="count_per_time", time=60, count=5)]
        for _ in range(5):
            limiter.record("scope1")
        ok, wait = limiter.check("scope1", rules)
        assert ok is False
        assert wait > 0

    def test_count_per_time_none_count_skipped(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="count_per_time", time=60, count=None)]
        for _ in range(10):
            limiter.record("scope1")
        ok, wait = limiter.check("scope1", rules)
        assert ok is True

    def test_tokens_per_time_under_limit(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="tokens_per_time", time=60, tokens=1000)]
        limiter.record("scope1", tokens=500)
        ok, wait = limiter.check("scope1", rules)
        assert ok is True

    def test_tokens_per_time_at_limit(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="tokens_per_time", time=60, tokens=1000)]
        limiter.record("scope1", tokens=1000)
        ok, wait = limiter.check("scope1", rules)
        assert ok is False
        assert wait > 0

    def test_tokens_per_time_over_limit(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="tokens_per_time", time=60, tokens=100)]
        limiter.record("scope1", tokens=200)
        ok, wait = limiter.check("scope1", rules)
        assert ok is False

    def test_tokens_per_time_none_tokens_skipped(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="tokens_per_time", time=60, tokens=None)]
        limiter.record("scope1", tokens=99999)
        ok, wait = limiter.check("scope1", rules)
        assert ok is True


class TestRateLimiterMultipleRules:
    def test_multiple_rules_all_pass(self):
        limiter = RateLimiter()
        rules = [
            LimitRule(type="time_per_req", time=0),
            LimitRule(type="count_per_time", time=60, count=10),
        ]
        limiter.record("scope1")
        ok, wait = limiter.check("scope1", rules)
        assert ok is True

    def test_multiple_rules_one_blocks(self):
        limiter = RateLimiter()
        rules = [
            LimitRule(type="time_per_req", time=10),
            LimitRule(type="count_per_time", time=60, count=10),
        ]
        limiter.record("scope1")
        ok, wait = limiter.check("scope1", rules)
        assert ok is False
        assert wait > 0


class TestRateLimiterScopeIsolation:
    def test_different_scopes_independent(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="time_per_req", time=10)]
        limiter.record("scope1")
        ok1, _ = limiter.check("scope1", rules)
        ok2, _ = limiter.check("scope2", rules)
        assert ok1 is False
        assert ok2 is True


class TestRateLimiterPruning:
    def test_old_records_pruned(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="count_per_time", time=1, count=1)]
        limiter.record("scope1")
        time.sleep(1.1)
        ok, wait = limiter.check("scope1", rules)
        assert ok is True


class TestRateLimiterThreadSafety:
    def test_concurrent_access(self):
        limiter = RateLimiter()
        rules = [LimitRule(type="count_per_time", time=60, count=1000)]
        errors = []

        def worker(scope):
            try:
                for _ in range(100):
                    limiter.record(scope, tokens=1)
                    limiter.check(scope, rules)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(f"scope-{i}",)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []