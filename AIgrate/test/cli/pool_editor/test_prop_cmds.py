import pytest
from core.models import AIPool, ApiKeyConfig, ModelOverride, ErrorConfig
from cli.pool_editor.prop_cmds import PropCommands
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
                max_requests=100,
                models={"model-a": ModelOverride(model_id="model-a")},
            ),
        ],
    )
    return PoolEditor("test-pool", pool)


class TestDoConcurrency:
    def test_set_concurrency(self, capsys):
        editor = _make_editor()
        editor.do_concurrency("0 5")
        assert editor.pool.keys[0].errors.max_concurrency == 5
        assert editor.modified is True

    def test_view_concurrency(self, capsys):
        editor = _make_editor()
        editor.do_concurrency("0")
        captured = capsys.readouterr()
        assert "1" in captured.out

    def test_no_args(self, capsys):
        editor = _make_editor()
        editor.do_concurrency("")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out

    def test_invalid_value(self, capsys):
        editor = _make_editor()
        editor.do_concurrency("0 abc")
        captured = capsys.readouterr()
        assert "整数" in captured.err or "整数" in captured.out

    def test_invalid_index(self, capsys):
        editor = _make_editor()
        editor.do_concurrency("abc 5")
        captured = capsys.readouterr()
        assert "数字" in captured.err or "数字" in captured.out


class TestDoTimeout:
    def test_set_timeout(self, capsys):
        editor = _make_editor()
        editor.do_timeout("0 60")
        assert editor.pool.keys[0].errors.timeout == 60
        assert editor.modified is True

    def test_view_timeout(self, capsys):
        editor = _make_editor()
        editor.do_timeout("0")
        captured = capsys.readouterr()
        assert "30" in captured.out


class TestDoMaxErrors:
    def test_set_max_errors(self, capsys):
        editor = _make_editor()
        editor.do_max_errors("0 10")
        assert editor.pool.keys[0].errors.max_errors == 10
        assert editor.modified is True

    def test_view_max_errors(self, capsys):
        editor = _make_editor()
        editor.do_max_errors("0")
        captured = capsys.readouterr()
        assert "3" in captured.out


class TestDoMaxRequests:
    def test_set_max_requests(self, capsys):
        editor = _make_editor()
        editor.do_max_requests("0 200")
        assert editor.pool.keys[0].max_requests == 200
        assert editor.modified is True

    def test_view_max_requests(self, capsys):
        editor = _make_editor()
        editor.do_max_requests("0")
        captured = capsys.readouterr()
        assert "100" in captured.out


class TestDoFailurePause:
    def test_set_failure_pause(self, capsys):
        editor = _make_editor()
        editor.do_failure_pause("0 20")
        assert editor.pool.keys[0].errors.failure_pause == 20
        assert editor.modified is True

    def test_view_failure_pause(self, capsys):
        editor = _make_editor()
        editor.do_failure_pause("0")
        captured = capsys.readouterr()
        assert "40" in captured.out