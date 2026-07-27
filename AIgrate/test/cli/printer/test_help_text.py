import pytest
from cli.printer.help_text import welcome, print_help


class TestWelcome:
    def test_contains_title(self, capsys):
        welcome()
        captured = capsys.readouterr()
        assert "AI 池" in captured.out

    def test_contains_help_hint(self, capsys):
        welcome()
        captured = capsys.readouterr()
        assert "/help" in captured.out

    def test_contains_exit_hint(self, capsys):
        welcome()
        captured = capsys.readouterr()
        assert "/exit" in captured.out


class TestPrintHelp:
    def test_contains_connect(self, capsys):
        print_help()
        captured = capsys.readouterr()
        assert "/connect" in captured.out

    def test_contains_pool_create(self, capsys):
        print_help()
        captured = capsys.readouterr()
        assert "/pool create" in captured.out or "pool create" in captured.out

    def test_contains_help(self, capsys):
        print_help()
        captured = capsys.readouterr()
        assert "/help" in captured.out

    def test_contains_exit(self, capsys):
        print_help()
        captured = capsys.readouterr()
        assert "/exit" in captured.out

    def test_contains_model(self, capsys):
        print_help()
        captured = capsys.readouterr()
        assert "/model" in captured.out

    def test_contains_params(self, capsys):
        print_help()
        captured = capsys.readouterr()
        assert "/params" in captured.out

    def test_contains_api_type_flags(self, capsys):
        print_help()
        captured = capsys.readouterr()
        assert "openai" in captured.out
        assert "azure" in captured.out