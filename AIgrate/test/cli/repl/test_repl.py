import pytest
from unittest.mock import patch, MagicMock
from core.models import ChatParams
from cli.repl.repl import REPL as ChatREPL


class TestChatREPLInit:
    @patch("cli.repl.repl.pool_manager")
    @patch("cli.repl.repl.settings_manager")
    def test_init_sets_defaults(self, mock_sm, mock_pm):
        mock_sm.load.return_value = {}
        mock_pm.load.return_value = None
        mock_pm.get_pool_names.return_value = []
        mock_pm.get_single_names.return_value = []
        repl = ChatREPL()
        assert repl.mode == ""
        assert repl.selected_model == ""
        assert isinstance(repl.params, ChatParams)
        assert repl.messages == []

    @patch("cli.repl.repl.pool_manager")
    @patch("cli.repl.repl.settings_manager")
    def test_init_prompt(self, mock_sm, mock_pm):
        mock_sm.load.return_value = {}
        mock_pm.load.return_value = None
        mock_pm.get_pool_names.return_value = []
        mock_pm.get_single_names.return_value = []
        repl = ChatREPL()
        assert repl.prompt == "> "


class TestChatREPLTimestamp:
    @patch("cli.repl.repl.pool_manager")
    @patch("cli.repl.repl.settings_manager")
    def test_timestamp_format(self, mock_sm, mock_pm):
        mock_sm.load.return_value = {}
        mock_pm.load.return_value = None
        mock_pm.get_pool_names.return_value = []
        mock_pm.get_single_names.return_value = []
        repl = ChatREPL()
        ts = repl._timestamp()
        assert ":" in ts


class TestChatREPLBuildMessages:
    @patch("cli.repl.repl.pool_manager")
    @patch("cli.repl.repl.settings_manager")
    def test_no_system_prompt(self, mock_sm, mock_pm):
        mock_sm.load.return_value = {}
        mock_pm.load.return_value = None
        mock_pm.get_pool_names.return_value = []
        mock_pm.get_single_names.return_value = []
        repl = ChatREPL()
        repl.messages = [{"role": "user", "content": "hi"}]
        msgs = repl._build_messages()
        assert len(msgs) == 1

    @patch("cli.repl.repl.pool_manager")
    @patch("cli.repl.repl.settings_manager")
    def test_with_system_prompt(self, mock_sm, mock_pm):
        mock_sm.load.return_value = {}
        mock_pm.load.return_value = None
        mock_pm.get_pool_names.return_value = []
        mock_pm.get_single_names.return_value = []
        repl = ChatREPL()
        repl.params.system_prompt = "You are helpful"
        repl.messages = [{"role": "user", "content": "hi"}]
        msgs = repl._build_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"


class TestChatREPLEmptyline:
    @patch("cli.repl.repl.pool_manager")
    @patch("cli.repl.repl.settings_manager")
    def test_emptyline_returns_none(self, mock_sm, mock_pm):
        mock_sm.load.return_value = {}
        mock_pm.load.return_value = None
        mock_pm.get_pool_names.return_value = []
        mock_pm.get_single_names.return_value = []
        repl = ChatREPL()
        result = repl.emptyline()
        assert result is None


class TestChatREPLDoExit:
    @patch("cli.repl.repl.pool_manager")
    @patch("cli.repl.repl.settings_manager")
    def test_do_exit_returns_true(self, mock_sm, mock_pm):
        mock_sm.load.return_value = {}
        mock_pm.load.return_value = None
        mock_pm.get_pool_names.return_value = []
        mock_pm.get_single_names.return_value = []
        repl = ChatREPL()
        assert repl.do_exit("") is True

    @patch("cli.repl.repl.pool_manager")
    @patch("cli.repl.repl.settings_manager")
    def test_do_quit_returns_true(self, mock_sm, mock_pm):
        mock_sm.load.return_value = {}
        mock_pm.load.return_value = None
        mock_pm.get_pool_names.return_value = []
        mock_pm.get_single_names.return_value = []
        repl = ChatREPL()
        assert repl.do_quit("") is True

    @patch("cli.repl.repl.pool_manager")
    @patch("cli.repl.repl.settings_manager")
    def test_do_eof_returns_true(self, mock_sm, mock_pm):
        mock_sm.load.return_value = {}
        mock_pm.load.return_value = None
        mock_pm.get_pool_names.return_value = []
        mock_pm.get_single_names.return_value = []
        repl = ChatREPL()
        assert repl.do_EOF("") is True