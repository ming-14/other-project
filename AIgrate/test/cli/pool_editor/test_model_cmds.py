import pytest
from core.models import AIPool, ApiKeyConfig, ModelOverride, ErrorConfig
from cli.pool_editor.model_cmds import ModelCommands
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


class TestDoModelAdd:
    def test_add_model(self, capsys):
        editor = _make_editor()
        editor.do_model_add("0 model-b")
        assert "model-b" in editor.pool.keys[0].models
        assert editor.modified is True

    def test_add_duplicate(self, capsys):
        editor = _make_editor()
        editor.do_model_add("0 model-a")
        captured = capsys.readouterr()
        assert "已存在" in captured.out

    def test_no_args(self, capsys):
        editor = _make_editor()
        editor.do_model_add("0")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out

    def test_invalid_key_index(self, capsys):
        editor = _make_editor()
        editor.do_model_add("5 model-b")
        captured = capsys.readouterr()
        assert "越界" in captured.err or "越界" in captured.out


class TestDoModelRemove:
    def test_remove_model(self, capsys):
        editor = _make_editor()
        editor.do_model_remove("0 model-a")
        assert "model-a" not in editor.pool.keys[0].models
        assert editor.modified is True

    def test_remove_nonexistent(self, capsys):
        editor = _make_editor()
        editor.do_model_remove("0 model-z")
        captured = capsys.readouterr()
        assert "不存在" in captured.err or "不存在" in captured.out

    def test_no_args(self, capsys):
        editor = _make_editor()
        editor.do_model_remove("0")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out


class TestDoModelParam:
    def test_set_concurrency(self, capsys):
        editor = _make_editor()
        editor.do_model_param("0 model-a concurrency 5")
        assert editor.pool.keys[0].models["model-a"].max_concurrency == 5
        assert editor.modified is True

    def test_set_timeout(self, capsys):
        editor = _make_editor()
        editor.do_model_param("0 model-a timeout 120")
        assert editor.pool.keys[0].models["model-a"].timeout == 120

    def test_set_max_errors(self, capsys):
        editor = _make_editor()
        editor.do_model_param("0 model-a max-errors 10")
        assert editor.pool.keys[0].models["model-a"].max_errors == 10

    def test_set_max_requests(self, capsys):
        editor = _make_editor()
        editor.do_model_param("0 model-a max-requests 500")
        assert editor.pool.keys[0].models["model-a"].max_requests == 500

    def test_set_failure_pause(self, capsys):
        editor = _make_editor()
        editor.do_model_param("0 model-a failure-pause 30")
        assert editor.pool.keys[0].models["model-a"].failure_pause == 30

    def test_set_context_length(self, capsys):
        editor = _make_editor()
        editor.do_model_param("0 model-a context-length 8192")
        assert editor.pool.keys[0].models["model-a"].context_length == 8192

    def test_unknown_field(self, capsys):
        editor = _make_editor()
        editor.do_model_param("0 model-a unknown 5")
        captured = capsys.readouterr()
        assert "未知" in captured.err or "未知" in captured.out

    def test_invalid_value(self, capsys):
        editor = _make_editor()
        editor.do_model_param("0 model-a concurrency abc")
        captured = capsys.readouterr()
        assert "整数" in captured.err or "整数" in captured.out

    def test_nonexistent_model(self, capsys):
        editor = _make_editor()
        editor.do_model_param("0 model-z concurrency 5")
        captured = capsys.readouterr()
        assert "不存在" in captured.err or "不存在" in captured.out

    def test_insufficient_args(self, capsys):
        editor = _make_editor()
        editor.do_model_param("0 model-a concurrency")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out