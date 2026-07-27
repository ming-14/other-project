import time
import pytest
from core.models import AIPool, ApiKeyConfig, ModelOverride, ErrorConfig, LimitRule
from core.pool.router import PoolRouter


def _make_pool(num_keys=1, models_per_key=1, max_errors=3, max_concurrency=1,
               failure_pause=1, max_requests=None, rate_limits=None,
               model_overrides=None):
    keys = []
    for ki in range(num_keys):
        model_dict = {}
        for mi in range(models_per_key):
            mid = f"model-{ki}-{mi}"
            if model_overrides and (ki, mi) in model_overrides:
                model_dict[mid] = model_overrides[(ki, mi)]
            else:
                model_dict[mid] = ModelOverride(model_id=mid)
        keys.append(ApiKeyConfig(
            base_url=f"https://api{ki}.example.com/v1",
            api_key=f"sk-key{ki}",
            label=f"Key{ki}",
            errors=ErrorConfig(
                max_concurrency=max_concurrency,
                timeout=30,
                max_errors=max_errors,
                failure_pause=failure_pause,
            ),
            max_requests=max_requests,
            rate_limits=rate_limits,
            models=model_dict,
        ))
    return AIPool(name="test-pool", keys=keys)


class TestPoolRouterBasic:
    def test_select_entry_returns_available(self):
        pool = _make_pool(num_keys=1, models_per_key=1)
        router = PoolRouter(pool)
        result = router.select_entry()
        assert result is not None
        ki, mid, kc, mo = result
        assert ki == 0
        assert mid == "model-0-0"

    def test_select_entry_increments_concurrency(self):
        pool = _make_pool(num_keys=1, models_per_key=1, max_concurrency=5)
        router = PoolRouter(pool)
        router.select_entry()
        assert router._key_conc[0] == 1
        assert router._mdl_conc[(0, "model-0-0")] == 1

    def test_select_entry_increments_requests(self):
        pool = _make_pool(num_keys=1, models_per_key=1)
        router = PoolRouter(pool)
        router.select_entry()
        assert router._key_reqs[0] == 1
        assert router._mdl_reqs[(0, "model-0-0")] == 1

    def test_select_entry_multiple_candidates(self):
        pool = _make_pool(num_keys=2, models_per_key=2, max_concurrency=10)
        router = PoolRouter(pool)
        results = set()
        for _ in range(100):
            ki, mid, kc, mo = router.select_entry()
            results.add(mid)
            router.report_success(ki, mid)
        assert len(results) == 4


class TestPoolRouterConcurrency:
    def test_concurrency_limit_blocks(self):
        pool = _make_pool(num_keys=1, models_per_key=1, max_concurrency=1)
        router = PoolRouter(pool)
        result = router.select_entry()
        assert result is not None
        available, wait = router._entry_available(0, "model-0-0", pool.keys[0], pool.keys[0].models["model-0-0"])
        assert available is False
        assert wait == -1

    def test_concurrency_release_on_success(self):
        pool = _make_pool(num_keys=1, models_per_key=1, max_concurrency=1)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_success(ki, mid)
        assert router._key_conc[0] == 0
        assert router._mdl_conc[(0, "model-0-0")] == 0

    def test_concurrency_release_on_error(self):
        pool = _make_pool(num_keys=1, models_per_key=1, max_concurrency=1)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        assert router._key_conc[0] == 0
        assert router._mdl_conc[(0, "model-0-0")] == 0


class TestPoolRouterErrorTracking:
    def test_error_count_increments(self):
        pool = _make_pool(num_keys=1, models_per_key=1, max_errors=5)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        assert router._key_errors[0] == 1
        assert router._mdl_errors[(0, "model-0-0")] == 1

    def test_success_resets_errors(self):
        pool = _make_pool(num_keys=1, models_per_key=1, max_errors=5)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        assert router._key_errors[0] == 1
        router.report_success(ki, mid)
        assert router._key_errors[0] == 0
        assert router._mdl_errors[(0, "model-0-0")] == 0

    def test_max_errors_disables_permanently(self):
        pool = _make_pool(num_keys=1, models_per_key=1, max_errors=2)
        router = PoolRouter(pool)
        for _ in range(2):
            ki, mid, kc, mo = router.select_entry()
            router.report_error(ki, mid, kc)
        assert router._key_errors[0] >= 2
        assert router.is_permanently_disabled(0, "model-0-0", pool.keys[0]) is True

    def test_model_level_max_errors(self):
        model_overrides = {
            (0, 0): ModelOverride(model_id="model-0-0", max_errors=1),
        }
        pool = _make_pool(num_keys=1, models_per_key=1, max_errors=10,
                          model_overrides=model_overrides)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        assert router.is_permanently_disabled(0, "model-0-0", pool.keys[0]) is True


class TestPoolRouterCooldown:
    def test_error_triggers_cooldown(self):
        """failure_pause 在 apikey 级别现在冷却整个 key"""
        pool = _make_pool(num_keys=1, models_per_key=1, failure_pause=10)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        # 新行为：整个 key 冷却，而不是单个模型
        assert 0 in router._key_cooldown
        assert router._key_cooldown[0] > time.time()
        # 模型级别冷却不应被设置
        assert (0, "model-0-0") not in router._mdl_cooldown

    def test_cooldown_expires(self):
        pool = _make_pool(num_keys=1, models_per_key=1, failure_pause=0)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        time.sleep(0.05)
        available, wait = router._entry_available(0, "model-0-0", pool.keys[0],
                                                   pool.keys[0].models["model-0-0"])
        assert available is True

    def test_model_override_failure_pause(self):
        model_overrides = {
            (0, 0): ModelOverride(model_id="model-0-0", failure_pause=5),
        }
        pool = _make_pool(num_keys=1, models_per_key=1, failure_pause=1,
                          model_overrides=model_overrides)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        remaining = router._mdl_cooldown[(0, "model-0-0")] - time.time()
        assert remaining > 3


class TestPoolRouterMaxRequests:
    def test_max_requests_disables_key(self):
        pool = _make_pool(num_keys=1, models_per_key=1, max_requests=1)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_success(ki, mid)
        assert router.is_permanently_disabled(0, "model-0-0", pool.keys[0]) is True

    def test_model_max_requests(self):
        model_overrides = {
            (0, 0): ModelOverride(model_id="model-0-0", max_requests=1),
        }
        pool = _make_pool(num_keys=1, models_per_key=1, max_requests=None,
                          model_overrides=model_overrides)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_success(ki, mid)
        assert router.is_permanently_disabled(0, "model-0-0", pool.keys[0]) is True


class TestPoolRouterRateLimits:
    def test_rate_limit_blocks_entry(self):
        pool = _make_pool(num_keys=1, models_per_key=1,
                          rate_limits=[LimitRule(type="time_per_req", time=10)])
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_success(ki, mid)
        available, wait = router._entry_available(0, "model-0-0", pool.keys[0],
                                                   pool.keys[0].models["model-0-0"])
        assert available is False
        assert wait > 0


class TestPoolRouterAllDisabled:
    def test_all_disabled_returns_none(self):
        pool = _make_pool(num_keys=1, models_per_key=1, max_errors=1)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        result = router.select_entry()
        assert result is None


class TestPoolRouterResetSession:
    def test_reset_clears_state(self):
        pool = _make_pool(num_keys=1, models_per_key=1, max_errors=5)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        assert router._key_errors[0] > 0
        router.reset_session()
        assert router._key_errors[0] == 0
        assert router._mdl_errors[(0, "model-0-0")] == 0
        assert router._key_conc[0] == 0
        assert router._mdl_conc[(0, "model-0-0")] == 0


class TestPoolRouterGetStatusText:
    def test_status_text_contains_model(self):
        pool = _make_pool(num_keys=1, models_per_key=1)
        router = PoolRouter(pool)
        text = router.get_status_text()
        assert "model-0-0" in text
        assert "可用" in text

    def test_status_text_shows_disabled(self):
        pool = _make_pool(num_keys=1, models_per_key=1, max_errors=1)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        text = router.get_status_text()
        assert "禁用" in text


class TestPoolRouterLogging:
    def test_on_log_called_on_error(self):
        logs = []
        pool = _make_pool(num_keys=1, models_per_key=1, max_errors=5)
        router = PoolRouter(pool, on_log=logs.append)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        assert len(logs) > 0
        assert "失败" in logs[0]

    def test_on_log_none_no_error(self):
        pool = _make_pool(num_keys=1, models_per_key=1)
        router = PoolRouter(pool, on_log=None)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)


# ── 组过滤测试 ──


def _make_grouped_pool():
    """创建含分组的池

    key0: groups=["free"]   -> model-0: groups=["cn"], model-1: groups=["eu"]
    key1: groups=["premium"] -> model-2: groups=["cn"]
    key2: groups=["other"]  -> model-3: groups=["other"]
    """
    keys = [
        ApiKeyConfig(
            base_url="https://free.example.com/v1",
            api_key="sk-free",
            label="Free",
            groups=["free"],
            errors=ErrorConfig(max_concurrency=5, timeout=30, max_errors=10, failure_pause=1),
            models={
                "model-cn": ModelOverride(model_id="model-cn", groups=["cn"]),
                "model-eu": ModelOverride(model_id="model-eu", groups=["eu"]),
            },
        ),
        ApiKeyConfig(
            base_url="https://prem.example.com/v1",
            api_key="sk-prem",
            label="Premium",
            groups=["premium"],
            errors=ErrorConfig(max_concurrency=5, timeout=30, max_errors=10, failure_pause=1),
            models={
                "model-prem-cn": ModelOverride(model_id="model-prem-cn", groups=["cn"]),
            },
        ),
        ApiKeyConfig(
            base_url="https://other.example.com/v1",
            api_key="sk-other",
            label="Other",
            groups=["other"],
            errors=ErrorConfig(max_concurrency=5, timeout=30, max_errors=10, failure_pause=1),
            models={
                "model-other": ModelOverride(model_id="model-other"),
            },
        ),
    ]
    return AIPool(name="grouped-pool", keys=keys)


class TestPoolRouterGroups:
    def test_get_all_groups(self):
        pool = _make_grouped_pool()
        router = PoolRouter(pool)
        all_groups = router.get_all_groups()
        assert all_groups == {"free", "premium", "cn", "eu", "other"}

    def test_active_groups_default_is_none(self):
        pool = _make_grouped_pool()
        router = PoolRouter(pool)
        assert router.get_active_groups() is None

    def test_no_filter_all_available(self):
        pool = _make_grouped_pool()
        router = PoolRouter(pool)
        # active_groups=None -> 无过滤，全部可用
        selected = set()
        for _ in range(200):
            result = router.select_entry()
            if result:
                ki, mid, kc, mo = result
                selected.add((ki, mid))
                router.report_success(ki, mid)
        assert len(selected) == 4  # 4个 (key, model) 对

    def test_disable_free_group(self):
        pool = _make_grouped_pool()
        router = PoolRouter(pool)
        # 禁用 "free" 组，排除 key0
        router.set_active_groups({"premium", "cn", "eu", "other"})
        selected = set()
        for _ in range(200):
            result = router.select_entry()
            if result:
                ki, mid, kc, mo = result
                selected.add((ki, mid))
                router.report_success(ki, mid)
        # key0 的组 "free" 不在活跃列表，被排除
        assert (0, "model-cn") not in selected
        assert (0, "model-eu") not in selected
        assert (1, "model-prem-cn") in selected
        assert (2, "model-other") in selected

    def test_disable_cn_group(self):
        pool = _make_grouped_pool()
        router = PoolRouter(pool)
        # 禁用 "cn" 组
        router.set_active_groups({"free", "premium", "eu", "other"})
        selected = set()
        for _ in range(200):
            result = router.select_entry()
            if result:
                ki, mid, kc, mo = result
                selected.add((ki, mid))
                router.report_success(ki, mid)
        # model-cn 和 model-prem-cn 的组 "cn" 不在活跃列表
        assert (0, "model-cn") not in selected
        assert (0, "model-eu") in selected  # key=free, model=eu 都在活跃列表
        assert (1, "model-prem-cn") not in selected
        assert (2, "model-other") in selected

    def test_only_cn_active(self):
        pool = _make_grouped_pool()
        router = PoolRouter(pool)
        router.set_active_groups({"cn"})
        selected = set()
        for _ in range(200):
            result = router.select_entry()
            if result:
                ki, mid, kc, mo = result
                selected.add((ki, mid))
                router.report_success(ki, mid)
        # 仅 key组 AND model组 都在 {"cn"} 的才可用
        # key0[free] 不在 {"cn"} -> 排除
        # key1[premium] 不在 {"cn"} -> 排除
        # key2[other] 不在 {"cn"} -> 排除
        assert len(selected) == 0

    def test_reset_to_all_active(self):
        pool = _make_grouped_pool()
        router = PoolRouter(pool)
        router.set_active_groups({"other"})  # 仅 other 活跃
        result = router.select_entry()
        assert result is not None
        ki, mid, _, _ = result
        assert (ki, mid) == (2, "model-other")
        router.report_success(ki, mid)

        router.set_active_groups(None)  # 重置
        selected = set()
        for _ in range(200):
            result = router.select_entry()
            if result:
                ki, mid, kc, mo = result
                selected.add((ki, mid))
                router.report_success(ki, mid)
        assert len(selected) == 4

    def test_status_text_shows_group_filter(self):
        pool = _make_grouped_pool()
        router = PoolRouter(pool)
        router.set_active_groups({"other"})
        text = router.get_status_text()
        assert "组过滤禁用" in text

    def test_all_filtered_returns_none(self):
        pool = _make_grouped_pool()
        router = PoolRouter(pool)
        router.set_active_groups(set())  # 空集，全部禁用
        result = router.select_entry()
        assert result is None


# ── 冷却与错误上限扩展测试 ──


def _make_pool_extended(num_keys=1, models_per_key=1, max_errors=3, max_concurrency=1,
                        failure_pause=1, max_errors_model=None, failure_pause_model=None,
                        model_overrides=None):
    """创建支持新参数的池"""
    keys = []
    for ki in range(num_keys):
        model_dict = {}
        for mi in range(models_per_key):
            mid = f"model-{ki}-{mi}"
            if model_overrides and (ki, mi) in model_overrides:
                model_dict[mid] = model_overrides[(ki, mi)]
            else:
                model_dict[mid] = ModelOverride(model_id=mid)
        keys.append(ApiKeyConfig(
            base_url=f"https://api{ki}.example.com/v1",
            api_key=f"sk-key{ki}",
            label=f"Key{ki}",
            errors=ErrorConfig(
                max_concurrency=max_concurrency,
                timeout=30,
                max_errors=max_errors,
                failure_pause=failure_pause,
                max_errors_model=max_errors_model,
                failure_pause_model=failure_pause_model,
            ),
            models=model_dict,
        ))
    return AIPool(name="test-pool", keys=keys)


class TestPoolRouterCooldownExtended:
    def test_key_failure_pause_cools_entire_key(self):
        """apikey 的 failure_pause 冷却整个 key，所有模型受影响"""
        pool = _make_pool_extended(num_keys=1, models_per_key=3, failure_pause=10,
                                   max_concurrency=5)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        # 整个 key 冷却
        assert 0 in router._key_cooldown
        # 所有模型都显示为暂时不可用（key 冷却）
        for m in pool.keys[0].models:
            available, wait = router._entry_available(0, m, pool.keys[0],
                                                      pool.keys[0].models[m])
            assert available is False
            assert wait > 0  # key 冷却中，暂时不可用

    def test_model_explicit_failure_pause_cools_model_only(self):
        """model 显式 failure_pause 仅冷却该模型"""
        overrides = {
            (0, 0): ModelOverride(model_id="model-0-0", failure_pause=5),
        }
        pool = _make_pool_extended(num_keys=1, models_per_key=2, failure_pause=10,
                                   max_concurrency=5, model_overrides=overrides)
        router = PoolRouter(pool)
        # 选中 model-0-0 并报告错误
        for _ in range(50):
            ki, mid, kc, mo = router.select_entry()
            if mid == "model-0-0":
                router.report_error(ki, mid, kc)
                break
            router.report_success(ki, mid)
        # model-0-0 应被模型级别冷却
        assert (0, "model-0-0") in router._mdl_cooldown
        # key 不应被冷却（因为 model 有显式 failure_pause）
        assert 0 not in router._key_cooldown
        # model-0-1 仍可用
        found_other = False
        for _ in range(50):
            result = router.select_entry()
            if result and result[1] == "model-0-1":
                found_other = True
                router.report_success(result[0], result[1])
                break
        assert found_other

    def test_failure_pause_model_cools_model_only(self):
        """apikey 的 failure_pause_model 仅冷却该模型"""
        pool = _make_pool_extended(num_keys=1, models_per_key=2, failure_pause_model=5,
                                   max_concurrency=5)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        # 模型级别冷却被设置
        assert (ki, mid) in router._mdl_cooldown
        # key 级别冷却不应被设置
        assert ki not in router._key_cooldown

    def test_default_cooldown_cools_key(self):
        """无 failure_pause 配置时默认冷却整个 key"""
        pool = _make_pool_extended(num_keys=1, models_per_key=1, failure_pause=None)
        # 手动清除 failure_pause
        pool.keys[0].errors.failure_pause = None
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        assert 0 in router._key_cooldown


class TestPoolRouterMaxErrorsModel:
    def test_max_errors_model_disables_only_that_model(self):
        """max_errors_model 仅禁用该模型，不影响其他模型"""
        pool = _make_pool_extended(num_keys=1, models_per_key=2, max_errors=10,
                                   max_errors_model=2, max_concurrency=5,
                                   failure_pause=0)
        router = PoolRouter(pool)
        # 对 model-0-0 报告 2 次错误
        error_count = 0
        for _ in range(100):
            result = router.select_entry()
            if not result:
                break
            ki, mid, kc, mo = result
            if mid == "model-0-0":
                router.report_error(ki, mid, kc)
                error_count += 1
                if error_count >= 2:
                    break
            else:
                router.report_success(ki, mid)
        # model-0-0 应被永久禁用
        available, wait = router._entry_available(0, "model-0-0", pool.keys[0],
                                                  pool.keys[0].models["model-0-0"])
        assert available is False
        assert wait == -1
        # model-0-1 应仍可用
        available2, wait2 = router._entry_available(0, "model-0-1", pool.keys[0],
                                                     pool.keys[0].models["model-0-1"])
        assert available2 is True

    def test_max_errors_model_does_not_disable_key(self):
        """max_errors_model 不影响整个 key"""
        pool = _make_pool_extended(num_keys=1, models_per_key=2, max_errors=10,
                                   max_errors_model=1, max_concurrency=5,
                                   failure_pause=0)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        if mid == "model-0-0":
            router.report_error(ki, mid, kc)
        else:
            router.report_success(ki, mid)
            # 再试一次找到 model-0-0
            for _ in range(50):
                result = router.select_entry()
                if result and result[1] == "model-0-0":
                    router.report_error(result[0], result[1], result[2])
                    break
                elif result:
                    router.report_success(result[0], result[1])
        # key 级别错误计数应该不达到 max_errors=10
        assert router._key_errors[0] < 10
        # model-0-1 仍可用
        available, wait = router._entry_available(0, "model-0-1", pool.keys[0],
                                                  pool.keys[0].models["model-0-1"])
        assert available is True

    def test_status_text_shows_model_error_limit(self):
        """状态文本显示模型错误上限"""
        pool = _make_pool_extended(num_keys=1, models_per_key=1, max_errors=10,
                                   max_errors_model=1, max_concurrency=5,
                                   failure_pause=0)
        router = PoolRouter(pool)
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        text = router.get_status_text()
        assert "模型错误上限" in text
