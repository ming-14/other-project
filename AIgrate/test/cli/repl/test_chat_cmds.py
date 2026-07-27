import pytest
from core.models import ChatParams
from cli.repl.chat_cmds import ChatCommands, _parse_and_validate, _show_params, _reset_params, _PARAM_ALIASES


class FakeREPL(ChatCommands):
    def __init__(self):
        self.params = ChatParams()
        self.streaming = False
        self.stop_flag = False
        self.messages = []


class TestParamAliases:
    def test_temp_alias(self):
        assert _PARAM_ALIASES["temp"][0] == "temperature"

    def test_max_alias(self):
        assert _PARAM_ALIASES["max"][0] == "max_tokens"

    def test_top_alias(self):
        assert _PARAM_ALIASES["top"][0] == "top_p"

    def test_sys_alias(self):
        assert _PARAM_ALIASES["sys"][0] == "system_prompt"

    def test_all_aliases_have_attr(self):
        defaults = ChatParams()
        for key, (attr, display) in _PARAM_ALIASES.items():
            assert hasattr(defaults, attr)


class TestParseAndValidate:
    def test_temperature_valid(self):
        p = ChatParams()
        ok, msg = _parse_and_validate("temp", "0.5", p)
        assert ok is True
        assert p.temperature == 0.5

    def test_temperature_out_of_range(self):
        p = ChatParams()
        ok, msg = _parse_and_validate("temp", "3.0", p)
        assert ok is False

    def test_max_tokens_valid(self):
        p = ChatParams()
        ok, msg = _parse_and_validate("max", "4096", p)
        assert ok is True
        assert p.max_tokens == 4096

    def test_max_tokens_zero_invalid(self):
        p = ChatParams()
        ok, msg = _parse_and_validate("max", "0", p)
        assert ok is False

    def test_top_p_valid(self):
        p = ChatParams()
        ok, msg = _parse_and_validate("top", "0.9", p)
        assert ok is True
        assert p.top_p == 0.9

    def test_top_p_out_of_range(self):
        p = ChatParams()
        ok, msg = _parse_and_validate("top", "1.5", p)
        assert ok is False

    def test_system_prompt(self):
        p = ChatParams()
        ok, msg = _parse_and_validate("sys", "You are helpful", p)
        assert ok is True
        assert p.system_prompt == "You are helpful"

    def test_invalid_value(self):
        p = ChatParams()
        ok, msg = _parse_and_validate("temp", "not_a_number", p)
        assert ok is False


class TestShowParams:
    def test_show_all(self, capsys):
        p = ChatParams()
        _show_params(p)
        captured = capsys.readouterr()
        assert "Temperature" in captured.out
        assert "Max Tokens" in captured.out
        assert "Top P" in captured.out

    def test_show_specific(self, capsys):
        p = ChatParams()
        _show_params(p, ["temp"])
        captured = capsys.readouterr()
        assert "Temperature" in captured.out


class TestResetParams:
    def test_reset_all(self):
        p = ChatParams(temperature=0.1, max_tokens=100)
        _reset_params(p)
        assert p.temperature == 0.7
        assert p.max_tokens == 2048

    def test_reset_specific(self):
        p = ChatParams(temperature=0.1, max_tokens=100)
        _reset_params(p, ["temp"])
        assert p.temperature == 0.7
        assert p.max_tokens == 100


class TestDoParams:
    def test_show_all_no_args(self, capsys):
        repl = FakeREPL()
        repl.do_params("")
        captured = capsys.readouterr()
        assert "Temperature" in captured.out

    def test_set_temperature(self, capsys):
        repl = FakeREPL()
        repl.do_params('temp=0.5')
        assert repl.params.temperature == 0.5

    def test_set_multiple(self, capsys):
        repl = FakeREPL()
        repl.do_params('temp=0.3 max=1024')
        assert repl.params.temperature == 0.3
        assert repl.params.max_tokens == 1024

    def test_reset_all(self, capsys):
        repl = FakeREPL()
        repl.params.temperature = 0.1
        repl.do_params('reset')
        assert repl.params.temperature == 0.7

    def test_unknown_param(self, capsys):
        repl = FakeREPL()
        repl.do_params('unknown=5')
        captured = capsys.readouterr()
        assert "未知" in captured.err or "未知" in captured.out

    def test_invalid_format(self, capsys):
        repl = FakeREPL()
        repl.do_params('temp=0.5 badformat')
        captured = capsys.readouterr()
        assert "无效" in captured.err or "无效" in captured.out


class TestDoNew:
    def test_new_clears_messages(self, capsys):
        repl = FakeREPL()
        repl.messages = [{"role": "user", "content": "hi"}]
        repl.do_new("")
        assert repl.messages == []

    def test_new_already_empty(self, capsys):
        repl = FakeREPL()
        repl.do_new("")
        captured = capsys.readouterr()
        assert "空" in captured.out

    def test_new_while_streaming(self, capsys):
        repl = FakeREPL()
        repl.streaming = True
        repl.messages = [{"role": "user", "content": "hi"}]
        repl.do_new("")
        assert len(repl.messages) == 1


class TestDoClear:
    def test_clear_empties_messages(self, capsys):
        repl = FakeREPL()
        repl.messages = [{"role": "user", "content": "hi"}]
        repl.do_clear("")
        assert repl.messages == []

    def test_clear_while_streaming(self, capsys):
        repl = FakeREPL()
        repl.streaming = True
        repl.messages = [{"role": "user", "content": "hi"}]
        repl.do_clear("")
        assert len(repl.messages) == 1


class TestDoExport:
    def test_export_empty_conversation(self, capsys):
        repl = FakeREPL()
        repl.do_export("")
        captured = capsys.readouterr()
        assert "空" in captured.err or "空" in captured.out

    def test_export_creates_file(self, tmp_path, capsys):
        repl = FakeREPL()
        repl.messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        export_file = str(tmp_path / "export.txt")
        repl.do_export(export_file)
        with open(export_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert "hello" in content
        assert "hi there" in content

    def test_export_with_default_filename(self, tmp_path, capsys):
        repl = FakeREPL()
        repl.messages = [{"role": "user", "content": "test"}]
        import os
        old_cwd = os.getcwd()
        os.chdir(str(tmp_path))
        try:
            repl.do_export("")
            captured = capsys.readouterr()
            assert "导出" in captured.out
        finally:
            os.chdir(old_cwd)