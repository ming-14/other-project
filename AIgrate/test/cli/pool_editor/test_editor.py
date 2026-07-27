import pytest
from unittest.mock import patch
from core.models import AIPool, ApiKeyConfig, ModelOverride, ErrorConfig
from cli.pool_editor.editor import PoolEditor


def _make_pool():
    return AIPool(
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


class TestPoolEditorInit:
    def test_new_pool(self):
        editor = PoolEditor("new-pool")
        assert editor.pool.name == "new-pool"
        assert editor.is_new is True
        assert editor.modified is False

    def test_existing_pool(self):
        pool = _make_pool()
        editor = PoolEditor("test-pool", pool)
        assert editor.pool.name == "test-pool"
        assert editor.is_new is False
        assert editor.modified is False
        assert len(editor.pool.keys) == 1

    def test_deepcopy_on_existing(self):
        pool = _make_pool()
        editor = PoolEditor("test-pool", pool)
        editor.pool.keys.append(ApiKeyConfig(base_url="url2", api_key="k2"))
        assert len(pool.keys) == 1
        assert len(editor.pool.keys) == 2


class TestPoolEditorSave:
    @patch("cli.pool_editor.editor.pool_manager")
    def test_save_new_pool(self, mock_pm):
        editor = PoolEditor("new-pool")
        result = editor.do_save("")
        assert result is True
        mock_pm.add_pool.assert_called_once()

    @patch("cli.pool_editor.editor.pool_manager")
    def test_save_existing_pool(self, mock_pm):
        pool = _make_pool()
        editor = PoolEditor("test-pool", pool)
        result = editor.do_save("")
        assert result is True
        mock_pm.update_pool.assert_called_once()


class TestPoolEditorCancel:
    def test_cancel_returns_true(self, capsys):
        pool = _make_pool()
        editor = PoolEditor("test-pool", pool)
        result = editor.do_cancel("")
        assert result is True


class TestPoolEditorShow:
    def test_show_displays_pool(self, capsys):
        pool = _make_pool()
        editor = PoolEditor("test-pool", pool)
        editor.do_show("")
        captured = capsys.readouterr()
        assert "test-pool" in captured.out
        assert "Key1" in captured.out


class TestPoolEditorMarkModified:
    def test_mark_modified(self):
        editor = PoolEditor("test-pool")
        assert editor.modified is False
        editor._mark_modified()
        assert editor.modified is True


class TestPoolEditorDefault:
    def test_unknown_command(self, capsys):
        editor = PoolEditor("test-pool")
        editor.default("badcmd")
        captured = capsys.readouterr()
        assert "未知" in captured.err or "未知" in captured.out

    def test_empty_line(self):
        editor = PoolEditor("test-pool")
        result = editor.default("")
        assert result is None


class TestPoolEditorEOF:
    def test_eof_returns_true(self):
        editor = PoolEditor("test-pool")
        assert editor.do_EOF("") is True