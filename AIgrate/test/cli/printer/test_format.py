import pytest
from cli.printer.format import (
    info, success, error, warning, system, user, ai, dim, header, divider, bold,
    INFO_PREFIX, SUCCESS_PREFIX, ERROR_PREFIX, WARNING_PREFIX, SYSTEM_PREFIX,
)


class TestPrefixes:
    def test_info_prefix(self):
        assert INFO_PREFIX == "[i]"

    def test_success_prefix(self):
        assert SUCCESS_PREFIX == "[+]"

    def test_error_prefix(self):
        assert ERROR_PREFIX == "[-]"

    def test_warning_prefix(self):
        assert WARNING_PREFIX == "[!]"

    def test_system_prefix(self):
        assert SYSTEM_PREFIX == "[*]"


class TestInfo:
    def test_info_prints_to_stdout(self, capsys):
        info("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out


class TestSuccess:
    def test_success_prints_to_stdout(self, capsys):
        success("done")
        captured = capsys.readouterr()
        assert "done" in captured.out


class TestError:
    def test_error_prints_to_stderr(self, capsys):
        error("fail")
        captured = capsys.readouterr()
        assert "fail" in captured.err


class TestWarning:
    def test_warning_prints_to_stdout(self, capsys):
        warning("warn")
        captured = capsys.readouterr()
        assert "warn" in captured.out


class TestSystem:
    def test_system_prints_to_stdout(self, capsys):
        system("sys")
        captured = capsys.readouterr()
        assert "sys" in captured.out


class TestUser:
    def test_user_prints_to_stdout(self, capsys):
        user("msg")
        captured = capsys.readouterr()
        assert "msg" in captured.out


class TestAi:
    def test_ai_prints_without_newline(self, capsys):
        ai("partial")
        captured = capsys.readouterr()
        assert "partial" in captured.out
        assert not captured.out.endswith("\n")


class TestDim:
    def test_dim_prints_to_stdout(self, capsys):
        dim("dim text")
        captured = capsys.readouterr()
        assert "dim text" in captured.out


class TestHeader:
    def test_header_contains_title(self, capsys):
        header("Title")
        captured = capsys.readouterr()
        assert "Title" in captured.out
        assert "---" in captured.out

    def test_header_has_leading_newline(self, capsys):
        header("X")
        captured = capsys.readouterr()
        assert captured.out.startswith("\n")


class TestDivider:
    def test_divider_prints_dashes(self, capsys):
        divider()
        captured = capsys.readouterr()
        assert "-" in captured.out


class TestBold:
    def test_bold_returns_same_text(self):
        assert bold("text") == "text"

    def test_bold_empty_string(self):
        assert bold("") == ""