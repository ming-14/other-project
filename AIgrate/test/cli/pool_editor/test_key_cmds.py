import pytest
from core.models import AIPool, ApiKeyConfig, ModelOverride, ErrorConfig
from cli.pool_editor.key_cmds import KeyCommands
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


class TestDoKeys:
    def test_list_keys(self, capsys):
        editor = _make_editor()
        editor.do_keys("")
        captured = capsys.readouterr()
        assert "Key1" in captured.out
        assert "0" in captured.out

    def test_empty_keys(self, capsys):
        editor = PoolEditor("empty-pool")
        editor.do_keys("")
        captured = capsys.readouterr()
        assert "暂无" in captured.out


class TestDoKeyAdd:
    def test_add_key(self, capsys):
        editor = _make_editor()
        editor.do_key_add('Key2 https://api2.example.com/v1 sk-key2')
        assert len(editor.pool.keys) == 2
        assert editor.pool.keys[1].label == "Key2"
        assert editor.modified is True

    def test_add_key_with_type(self, capsys):
        editor = _make_editor()
        editor.do_key_add('Key2 https://api2.example.com/v1 sk-key2 azure')
        assert editor.pool.keys[1].type == "azure"

    def test_add_key_default_type(self, capsys):
        editor = _make_editor()
        editor.do_key_add('Key2 https://api2.example.com/v1 sk-key2')
        assert editor.pool.keys[1].type == "openai"

    def test_add_key_invalid_type(self, capsys):
        editor = _make_editor()
        editor.do_key_add('Key2 https://api2.example.com/v1 sk-key2 invalid')
        captured = capsys.readouterr()
        assert "未知" in captured.err or "未知" in captured.out
        assert len(editor.pool.keys) == 1

    def test_insufficient_args(self, capsys):
        editor = _make_editor()
        editor.do_key_add('Key2 https://api2.example.com/v1')
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out


class TestDoKeyRemove:
    def test_remove_key(self, capsys):
        editor = _make_editor()
        editor.do_key_remove("0")
        assert len(editor.pool.keys) == 0
        assert editor.modified is True

    def test_remove_invalid_index(self, capsys):
        editor = _make_editor()
        editor.do_key_remove("5")
        captured = capsys.readouterr()
        assert "越界" in captured.err or "越界" in captured.out

    def test_remove_non_numeric(self, capsys):
        editor = _make_editor()
        editor.do_key_remove("abc")
        captured = capsys.readouterr()
        assert "数字" in captured.err or "数字" in captured.out