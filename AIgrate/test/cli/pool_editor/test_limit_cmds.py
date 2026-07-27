import pytest
from core.models import AIPool, ApiKeyConfig, ModelOverride, ErrorConfig, LimitRule
from cli.pool_editor.limit_cmds import LimitCommands
from cli.pool_editor.editor import PoolEditor


def _make_editor():
    pool = AIPool(
        name="test-pool",
        keys=[
            ApiKeyConfig(
                base_url="https://api1.example.com/v1",
                api_key="sk-key1",
                label="Key1",
                errors=ErrorConfig(max_concurrency=1, timeout=30, max_errors=3, failure_pause=40),
                models={"model-a": ModelOverride(model_id="model-a")},
            ),
        ],
    )
    return PoolEditor("test-pool", pool)


class TestDoRateLimitAdd:
    def test_add_time_per_req(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_add("0 time_per_req 5")
        assert editor.pool.keys[0].rate_limits is not None
        assert len(editor.pool.keys[0].rate_limits) == 1
        assert editor.pool.keys[0].rate_limits[0].type == "time_per_req"
        assert editor.modified is True

    def test_add_count_per_time(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_add("0 count_per_time 60 10")
        assert editor.pool.keys[0].rate_limits[0].type == "count_per_time"
        assert editor.pool.keys[0].rate_limits[0].count == 10

    def test_add_tokens_per_time(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_add("0 tokens_per_time 60 1000")
        assert editor.pool.keys[0].rate_limits[0].type == "tokens_per_time"
        assert editor.pool.keys[0].rate_limits[0].tokens == 1000

    def test_count_per_time_missing_count(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_add("0 count_per_time 60")
        captured = capsys.readouterr()
        assert "count" in captured.err or "count" in captured.out

    def test_tokens_per_time_missing_tokens(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_add("0 tokens_per_time 60")
        captured = capsys.readouterr()
        assert "tokens" in captured.err or "tokens" in captured.out

    def test_unknown_type(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_add("0 unknown 60")
        captured = capsys.readouterr()
        assert "未知" in captured.err or "未知" in captured.out

    def test_invalid_time(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_add("0 time_per_req abc")
        captured = capsys.readouterr()
        assert "整数" in captured.err or "整数" in captured.out

    def test_insufficient_args(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_add("0 time_per_req")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out

    def test_invalid_key_index(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_add("5 time_per_req 5")
        captured = capsys.readouterr()
        assert "越界" in captured.err or "越界" in captured.out

    def test_initializes_none_rate_limits(self, capsys):
        editor = _make_editor()
        assert editor.pool.keys[0].rate_limits is None
        editor.do_rate_limit_add("0 time_per_req 5")
        assert editor.pool.keys[0].rate_limits is not None


class TestDoRateLimitList:
    def test_list_with_rules(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_add("0 time_per_req 5")
        editor.modified = False
        editor.do_rate_limit_list("0")
        captured = capsys.readouterr()
        assert "5s/次" in captured.out

    def test_list_no_rules(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_list("0")
        captured = capsys.readouterr()
        assert "无限流" in captured.out or "限流" in captured.out

    def test_invalid_index(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_list("abc")
        captured = capsys.readouterr()
        assert "数字" in captured.err or "数字" in captured.out


class TestDoRateLimitRemove:
    def test_remove_rule(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_add("0 time_per_req 5")
        editor.modified = False
        editor.do_rate_limit_remove("0 0")
        assert len(editor.pool.keys[0].rate_limits) == 0
        assert editor.modified is True

    def test_remove_invalid_rule_index(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_add("0 time_per_req 5")
        editor.modified = False
        editor.do_rate_limit_remove("0 5")
        captured = capsys.readouterr()
        assert "越界" in captured.err or "越界" in captured.out

    def test_remove_insufficient_args(self, capsys):
        editor = _make_editor()
        editor.do_rate_limit_remove("0")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out