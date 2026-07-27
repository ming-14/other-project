import pytest
from unittest.mock import patch, MagicMock
from core.models import AIPool, ApiKeyConfig, ModelOverride, ErrorConfig, SingleAI
from core.pool.manager import PoolManager
from cli.repl.direct_cmds import DirectCommands


class FakeREPL(DirectCommands):
    def __init__(self):
        self.mode = ""
        self.current_pool_name = None
        self.selected_model = ""
        self.selected_pool_key = None
        self.all_models = []
        self.model_details = {}
        self.streaming = False
        self.stop_flag = False
        self.messages = []
        self.settings = {}
        self.pm = PoolManager()
        self._timestamp = lambda: "12:00:00"

    def _set_mode(self, mode, pool_name=None):
        self.mode = mode
        self.current_pool_name = pool_name

    def _update_prompt(self):
        pass

    def _switch_to_entry(self, name, entry):
        from core.pool.manager import pool_manager as _pm
        if _pm.is_pool(name):
            self._set_mode("pool", name)
            self.selected_pool_key = None
        else:
            self._set_mode("single", name)
            self.selected_pool_key = None
            self.all_models = list(entry.models) if hasattr(entry, 'models') else []


class TestDoModel:
    def test_model_no_args_no_mode(self, capsys):
        repl = FakeREPL()
        repl.do_model("")
        captured = capsys.readouterr()
        assert "未选择" in captured.out or "未连接" in captured.out

    def test_model_no_args_with_mode(self, capsys):
        repl = FakeREPL()
        repl.mode = "single"
        repl.current_pool_name = "test-ai"
        repl.selected_model = "gpt-4"
        repl.do_model("")
        captured = capsys.readouterr()
        assert "gpt-4" in captured.out


class TestResolvePoolKey:
    def test_numeric_index(self):
        repl = FakeREPL()
        pool = AIPool(
            name="p",
            keys=[
                ApiKeyConfig(base_url="", api_key="", label="K1"),
                ApiKeyConfig(base_url="", api_key="", label="K2"),
            ],
        )
        assert repl._resolve_pool_key(pool, "1") == 0
        assert repl._resolve_pool_key(pool, "2") == 1

    def test_label_match(self):
        repl = FakeREPL()
        pool = AIPool(
            name="p",
            keys=[
                ApiKeyConfig(base_url="", api_key="", label="MyKey"),
            ],
        )
        assert repl._resolve_pool_key(pool, "MyKey") == 0

    def test_invalid_index(self):
        repl = FakeREPL()
        pool = AIPool(name="p", keys=[ApiKeyConfig(base_url="", api_key="", label="K1")])
        assert repl._resolve_pool_key(pool, "5") is None

    def test_invalid_label(self):
        repl = FakeREPL()
        pool = AIPool(name="p", keys=[ApiKeyConfig(base_url="", api_key="", label="K1")])
        assert repl._resolve_pool_key(pool, "NonExistent") is None


class TestWarnRateLimits:
    def test_no_limits_no_warning(self, capsys):
        repl = FakeREPL()
        kc = ApiKeyConfig(base_url="", api_key="", label="K")
        repl._warn_rate_limits(kc, "m1")
        captured = capsys.readouterr()
        assert "限速" not in captured.out

    def test_key_limits_shows_warning(self, capsys):
        from core.models import LimitRule
        repl = FakeREPL()
        kc = ApiKeyConfig(
            base_url="", api_key="", label="K",
            rate_limits=[LimitRule(type="time_per_req", time=5)],
        )
        repl._warn_rate_limits(kc, "m1")
        captured = capsys.readouterr()
        assert "限速" in captured.out