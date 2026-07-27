import json
import os
import pytest
from unittest.mock import patch
from core.models import AIPool, ApiKeyConfig, ModelOverride, ErrorConfig, SingleAI
from core.pool.manager import PoolManager, POOLS_FILE


def _make_pool(name="test-pool", num_keys=1):
    keys = []
    for i in range(num_keys):
        keys.append(ApiKeyConfig(
            base_url=f"https://api{i}.example.com/v1",
            api_key=f"sk-key{i}",
            label=f"Key{i}",
            errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=40),
            models={f"model-{i}": ModelOverride(model_id=f"model-{i}")},
        ))
    return AIPool(name=name, keys=keys)


class TestPoolManagerCRUD:
    def test_add_pool(self):
        pm = PoolManager()
        pool = _make_pool("pool1")
        with patch.object(pm, '_save'):
            pm.add_pool(pool)
        assert "pool1" in pm.pools
        assert pm.get_pool("pool1") is pool

    def test_add_pool_creates_router(self):
        pm = PoolManager()
        pool = _make_pool("pool1")
        with patch.object(pm, '_save'):
            pm.add_pool(pool)
        assert pm.get_router("pool1") is not None

    def test_remove_pool(self):
        pm = PoolManager()
        pool = _make_pool("pool1")
        with patch.object(pm, '_save'):
            pm.add_pool(pool)
            pm.remove_pool("pool1")
        assert pm.get_pool("pool1") is None
        assert pm.get_router("pool1") is None

    def test_remove_nonexistent_pool(self):
        pm = PoolManager()
        with patch.object(pm, '_save'):
            pm.remove_pool("nonexistent")

    def test_rename_pool(self):
        pm = PoolManager()
        pool = _make_pool("old-name")
        with patch.object(pm, '_save'):
            pm.add_pool(pool)
            result = pm.rename_pool("old-name", "new-name")
        assert result is True
        assert pm.get_pool("new-name") is not None
        assert pm.get_pool("old-name") is None
        assert pm.get_router("new-name") is not None

    def test_rename_pool_target_exists(self):
        pm = PoolManager()
        with patch.object(pm, '_save'):
            pm.add_pool(_make_pool("pool1"))
            pm.add_pool(_make_pool("pool2"))
            result = pm.rename_pool("pool1", "pool2")
        assert result is False

    def test_rename_pool_source_not_found(self):
        pm = PoolManager()
        with patch.object(pm, '_save'):
            result = pm.rename_pool("nonexistent", "new-name")
        assert result is False

    def test_get_pool_names(self):
        pm = PoolManager()
        with patch.object(pm, '_save'):
            pm.add_pool(_make_pool("pool1"))
            pm.add_pool(_make_pool("pool2"))
        names = pm.get_pool_names()
        assert set(names) == {"pool1", "pool2"}

    def test_get_pool_names_empty(self):
        pm = PoolManager()
        assert pm.get_pool_names() == []

    def test_update_pool(self):
        pm = PoolManager()
        pool = _make_pool("pool1", num_keys=1)
        with patch.object(pm, '_save'):
            pm.add_pool(pool)
        updated_pool = _make_pool("pool1", num_keys=2)
        with patch.object(pm, '_save'):
            pm.update_pool(updated_pool)
        assert len(pm.get_pool("pool1").keys) == 2

    def test_update_pool_preserves_router(self):
        pm = PoolManager()
        pool = _make_pool("pool1")
        with patch.object(pm, '_save'):
            pm.add_pool(pool)
        old_router = pm.get_router("pool1")
        updated_pool = _make_pool("pool1", num_keys=2)
        with patch.object(pm, '_save'):
            pm.update_pool(updated_pool)
        assert pm.get_router("pool1") is old_router


class TestPoolManagerPersistence:
    def test_save_creates_file(self, tmp_path):
        pm = PoolManager()
        pool = _make_pool("pool1")
        with patch("core.pool.manager.POOLS_FILE", str(tmp_path / "pools.json")):
            with patch("core.pool.manager._DATA_DIR", str(tmp_path)):
                pm.add_pool(pool)
                assert (tmp_path / "pools.json").exists()

    def test_save_and_load_roundtrip(self, tmp_path):
        pools_file = str(tmp_path / "pools.json")
        pool = _make_pool("pool1", num_keys=2)
        with patch("core.pool.manager.POOLS_FILE", pools_file):
            with patch("core.pool.manager._DATA_DIR", str(tmp_path)):
                pm1 = PoolManager()
                pm1.add_pool(pool)
        with patch("core.pool.manager.POOLS_FILE", pools_file):
            with patch("core.pool.manager._DATA_DIR", str(tmp_path)):
                pm2 = PoolManager()
                pm2.load()
        assert "pool1" in pm2.pools
        assert len(pm2.pools["pool1"].keys) == 2

    def test_load_missing_file(self, tmp_path):
        pm = PoolManager()
        with patch("core.pool.manager.POOLS_FILE", str(tmp_path / "nonexistent.json")):
            pm.load()
        assert pm.get_pool_names() == []

    def test_load_corrupt_file(self, tmp_path):
        pools_file = tmp_path / "pools.json"
        pools_file.write_text("not valid json{{{")
        pm = PoolManager()
        with patch("core.pool.manager.POOLS_FILE", str(pools_file)):
            pm.load()
        assert pm.get_pool_names() == []


class TestPoolManagerOnChange:
    def test_on_change_called_on_add(self):
        pm = PoolManager()
        calls = []
        pm.on_change(lambda: calls.append(1))
        with patch.object(pm, '_save'):
            pm.add_pool(_make_pool("pool1"))
        assert len(calls) == 1

    def test_on_change_called_on_remove(self):
        pm = PoolManager()
        calls = []
        pm.on_change(lambda: calls.append(1))
        with patch.object(pm, '_save'):
            pm.add_pool(_make_pool("pool1"))
            pm.remove_pool("pool1")
        assert len(calls) == 2

    def test_on_change_exception_swallowed(self):
        pm = PoolManager()
        def bad_cb():
            raise RuntimeError("boom")
        pm.on_change(bad_cb)
        with patch.object(pm, '_save'):
            pm.add_pool(_make_pool("pool1"))


class TestPoolManagerSession:
    def test_get_router_for_session_resets(self):
        pm = PoolManager()
        pool = _make_pool("pool1")
        with patch.object(pm, '_save'):
            pm.add_pool(pool)
        router = pm.get_router("pool1")
        ki, mid, kc, mo = router.select_entry()
        router.report_error(ki, mid, kc)
        assert router._key_errors[0] > 0
        router2 = pm.get_router_for_session("pool1")
        assert router2 is router
        assert router._key_errors[0] == 0

    def test_get_router_for_session_nonexistent(self):
        pm = PoolManager()
        assert pm.get_router_for_session("nonexistent") is None


class TestPoolManagerSingleAI:
    def _make_single(self, name="test-ai", models=None):
        kc = ApiKeyConfig(
            base_url="https://api.example.com/v1",
            api_key="sk-test",
            label="TestAI",
            errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=40),
        )
        return SingleAI(name=name, key=kc, models=models or {"gpt-4": ModelOverride(model_id="gpt-4")})

    def test_add_single(self):
        pm = PoolManager()
        single = self._make_single()
        with patch.object(pm, '_save'):
            pm.add_entry(single)
        assert pm.get_single("test-ai") is single
        assert pm.is_single("test-ai") is True
        assert pm.is_pool("test-ai") is False

    def test_add_single_no_router(self):
        pm = PoolManager()
        single = self._make_single()
        with patch.object(pm, '_save'):
            pm.add_entry(single)
        assert pm.get_router("test-ai") is None

    def test_remove_single(self):
        pm = PoolManager()
        single = self._make_single()
        with patch.object(pm, '_save'):
            pm.add_entry(single)
            pm.remove_entry("test-ai")
        assert pm.get_single("test-ai") is None

    def test_get_single_names(self):
        pm = PoolManager()
        with patch.object(pm, '_save'):
            pm.add_entry(self._make_single("ai1"))
            pm.add_entry(self._make_single("ai2"))
        names = pm.get_single_names()
        assert set(names) == {"ai1", "ai2"}

    def test_rename_single(self):
        pm = PoolManager()
        with patch.object(pm, '_save'):
            pm.add_entry(self._make_single("old-name"))
            result = pm.rename_entry("old-name", "new-name")
        assert result is True
        assert pm.get_single("new-name") is not None
        assert pm.get_single("old-name") is None

    def test_update_single(self):
        pm = PoolManager()
        single = self._make_single(models={"m1": ModelOverride(model_id="m1")})
        with patch.object(pm, '_save'):
            pm.add_entry(single)
        updated = self._make_single(models={"m1": ModelOverride(model_id="m1"), "m2": ModelOverride(model_id="m2")})
        with patch.object(pm, '_save'):
            pm.update_entry(updated)
        assert len(pm.get_single("test-ai").models) == 2

    def test_add_temp_no_persistence(self, tmp_path):
        pm = PoolManager()
        single = self._make_single()
        with patch("core.pool.manager.POOLS_FILE", str(tmp_path / "pools.json")):
            with patch("core.pool.manager._DATA_DIR", str(tmp_path)):
                pm.add_temp(single)
                assert pm.get_single("test-ai") is not None
                assert not (tmp_path / "pools.json").exists()

    def test_get_entry(self):
        pm = PoolManager()
        single = self._make_single()
        with patch.object(pm, '_save'):
            pm.add_entry(single)
        assert pm.get_entry("test-ai") is single

    def test_get_names(self):
        pm = PoolManager()
        with patch.object(pm, '_save'):
            pm.add_entry(self._make_single("ai1"))
            pm.add_pool(_make_pool("pool1"))
        names = pm.get_names()
        assert set(names) == {"ai1", "pool1"}


class TestPoolManagerResolveModel:
    def test_resolve_by_entry_name(self):
        pm = PoolManager()
        with patch.object(pm, '_save'):
            pm.add_entry(SingleAI(
                name="my-ai",
                key=ApiKeyConfig(base_url="", api_key=""),
                models={"gpt-4": ModelOverride(model_id="gpt-4")},
            ))
        result = pm.resolve_model("my-ai")
        assert result is not None
        assert result[0] == "my-ai"
        assert result[2] is False

    def test_resolve_by_alias(self):
        pm = PoolManager()
        with patch.object(pm, '_save'):
            pm.add_entry(SingleAI(
                name="my-ai",
                alias="ma",
                key=ApiKeyConfig(base_url="", api_key=""),
                models={"gpt-4": ModelOverride(model_id="gpt-4")},
            ))
        result = pm.resolve_model("ma")
        assert result is not None
        assert result[0] == "my-ai"

    def test_resolve_by_model_id(self):
        pm = PoolManager()
        with patch.object(pm, '_save'):
            pm.add_entry(SingleAI(
                name="my-ai",
                key=ApiKeyConfig(base_url="", api_key=""),
                models={"gpt-4": ModelOverride(model_id="gpt-4")},
            ))
        result = pm.resolve_model("gpt-4")
        assert result is not None
        assert result[1] == "gpt-4"

    def test_resolve_empty_query(self):
        pm = PoolManager()
        assert pm.resolve_model("") is None

    def test_resolve_nonexistent(self):
        pm = PoolManager()
        assert pm.resolve_model("nonexistent") is None

    def test_resolve_pool_by_name(self):
        pm = PoolManager()
        with patch.object(pm, '_save'):
            pm.add_pool(_make_pool("my-pool"))
        result = pm.resolve_model("my-pool")
        assert result is not None
        assert result[0] == "my-pool"
        assert result[2] is True


class TestPoolManagerGetAllEntriesInfo:
    def test_mixed_entries(self):
        pm = PoolManager()
        with patch.object(pm, '_save'):
            pm.add_pool(_make_pool("pool1"))
            pm.add_entry(SingleAI(
                name="ai1",
                alias="a1",
                key=ApiKeyConfig(base_url="", api_key="", label="MyAI"),
                models={"m1": ModelOverride(model_id="m1"), "m2": ModelOverride(model_id="m2")},
            ))
        info = pm.get_all_entries_info()
        assert len(info) == 2
        pool_info = [i for i in info if i["is_pool"]][0]
        single_info = [i for i in info if not i["is_pool"]][0]
        assert pool_info["name"] == "pool1"
        assert pool_info["key_count"] == 1
        assert single_info["name"] == "ai1"
        assert single_info["alias"] == "a1"
        assert single_info["model_count"] == 2