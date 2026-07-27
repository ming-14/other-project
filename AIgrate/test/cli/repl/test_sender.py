import pytest
from unittest.mock import patch, MagicMock
from core.models import ChatParams
from cli.repl.sender import Sender


class FakeREPL(Sender):
    def __init__(self):
        self.mode = ""
        self.current_pool_name = None
        self.selected_model = ""
        self.selected_pool_key = None
        self.streaming = False
        self.stop_flag = False
        self.messages = []
        self.params = ChatParams()

    def _timestamp(self):
        return "12:00:00"

    def _build_messages(self):
        return list(self.messages)

    def _update_prompt(self):
        pass


class TestSendNoConnection:
    def test_send_no_mode(self, capsys):
        repl = FakeREPL()
        repl.mode = ""
        repl._send("hello")
        captured = capsys.readouterr()
        assert "连接" in captured.err or "连接" in captured.out

    def test_send_no_pool_name(self, capsys):
        repl = FakeREPL()
        repl.mode = "pool"
        repl.current_pool_name = None
        repl._send("hello")
        captured = capsys.readouterr()
        assert "连接" in captured.err or "连接" in captured.out