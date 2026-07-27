import pytest
from unittest.mock import patch
from core.models import SingleAI, ApiKeyConfig, ModelOverride
from cli.pool_editor.single_editor import SingleEditor


def _make_single():
    kc = ApiKeyConfig(
        base_url="https://api.example.com/v1",
        api_key="sk-test123456",
        type="openai",
        label="TestAI",
    )
    return SingleAI(
        name="test-ai",
        key=kc,
        models={"gpt-4": ModelOverride(model_id="gpt-4"), "gpt-3.5-turbo": ModelOverride(model_id="gpt-3.5-turbo")},
    )


def _make_editor():
    single = _make_single()
    return SingleEditor("test-ai", single)


class TestSingleEditorInit:
    def test_init(self):
        editor = _make_editor()
        assert editor.single.name == "test-ai"
        assert editor.modified is False
        assert editor.original_name == "test-ai"

    def test_deepcopy(self):
        single = _make_single()
        editor = SingleEditor("test-ai", single)
        editor.single.models["new-model"] = ModelOverride(model_id="new-model")
        assert len(single.models) == 2
        assert len(editor.single.models) == 3


class TestSingleEditorSave:
    @patch("cli.pool_editor.single_editor.pool_manager")
    def test_save(self, mock_pm):
        editor = _make_editor()
        result = editor.do_save("")
        assert result is True
        mock_pm.update_entry.assert_called_once()


class TestSingleEditorCancel:
    def test_cancel(self, capsys):
        editor = _make_editor()
        result = editor.do_cancel("")
        assert result is True


class TestSingleEditorShow:
    def test_show(self, capsys):
        editor = _make_editor()
        editor.do_show("")
        captured = capsys.readouterr()
        assert "test-ai" in captured.out
        assert "TestAI" in captured.out
        assert "gpt-4" in captured.out


class TestSingleEditorModelAdd:
    def test_add_model(self, capsys):
        editor = _make_editor()
        editor.do_model_add("claude-3")
        assert "claude-3" in editor.single.models
        assert editor.modified is True

    def test_add_duplicate(self, capsys):
        editor = _make_editor()
        editor.do_model_add("gpt-4")
        captured = capsys.readouterr()
        assert "已存在" in captured.err or "已存在" in captured.out

    def test_no_args(self, capsys):
        editor = _make_editor()
        editor.do_model_add("")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out


class TestSingleEditorModelRemove:
    def test_remove_model(self, capsys):
        editor = _make_editor()
        editor.do_model_remove("gpt-4")
        assert "gpt-4" not in editor.single.models
        assert editor.modified is True

    def test_remove_nonexistent(self, capsys):
        editor = _make_editor()
        editor.do_model_remove("nonexistent")
        captured = capsys.readouterr()
        assert "不存在" in captured.err or "不存在" in captured.out

    def test_no_args(self, capsys):
        editor = _make_editor()
        editor.do_model_remove("")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out


class TestSingleEditorUrl:
    def test_set_url(self, capsys):
        editor = _make_editor()
        editor.do_url("https://new-api.example.com/v1")
        assert editor.single.key.base_url == "https://new-api.example.com/v1"
        assert editor.modified is True

    def test_no_args(self, capsys):
        editor = _make_editor()
        editor.do_url("")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out


class TestSingleEditorKey:
    def test_set_key(self, capsys):
        editor = _make_editor()
        editor.do_key("sk-newkey")
        assert editor.single.key.api_key == "sk-newkey"
        assert editor.modified is True

    def test_no_args(self, capsys):
        editor = _make_editor()
        editor.do_key("")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out


class TestSingleEditorLabel:
    def test_set_label(self, capsys):
        editor = _make_editor()
        editor.do_label("NewLabel")
        assert editor.single.key.label == "NewLabel"
        assert editor.modified is True

    def test_no_args(self, capsys):
        editor = _make_editor()
        editor.do_label("")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out


class TestSingleEditorDefault:
    def test_unknown_command(self, capsys):
        editor = _make_editor()
        editor.default("badcmd")
        captured = capsys.readouterr()
        assert "未知" in captured.err or "未知" in captured.out

    def test_empty_line(self):
        editor = _make_editor()
        result = editor.default("")
        assert result is None


class TestSingleEditorEOF:
    def test_eof_returns_true(self):
        editor = _make_editor()
        assert editor.do_EOF("") is True