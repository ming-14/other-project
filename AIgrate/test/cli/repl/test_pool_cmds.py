import pytest
from unittest.mock import patch, MagicMock
from core.models import AIPool, ApiKeyConfig, ModelOverride, ErrorConfig, SingleAI
from core.pool.manager import PoolManager
from cli.repl.pool_cmds import PoolCommands


class FakeREPL(PoolCommands):
    def __init__(self):
        self.mode = ""
        self.current_pool_name = None
        self.selected_model = ""
        self.selected_pool_key = None
        self.streaming = False
        self.stop_flag = False
        self.messages = []

    def _set_mode(self, mode, pool_name=None):
        self.mode = mode
        self.current_pool_name = pool_name


class TestDoDelete:
    def test_delete_nonexistent(self, capsys):
        repl = FakeREPL()
        repl.do_delete("nonexistent")
        captured = capsys.readouterr()
        assert "不存在" in captured.err or "不存在" in captured.out

    def test_delete_no_name(self, capsys):
        repl = FakeREPL()
        repl.do_delete("")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out


class TestDoRename:
    def test_rename_no_args(self, capsys):
        repl = FakeREPL()
        repl.do_rename("")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out

    def test_rename_one_arg(self, capsys):
        repl = FakeREPL()
        repl.do_rename("only_one")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out


class TestDoPoolCreate:
    def test_no_name(self, capsys):
        repl = FakeREPL()
        repl.do_pool_create("")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out


class TestDoTest:
    def test_no_name_no_current(self, capsys):
        repl = FakeREPL()
        repl.current_pool_name = None
        repl.do_test("")
        captured = capsys.readouterr()
        assert "用法" in captured.err or "用法" in captured.out

    def test_single_ai_not_supported(self, capsys):
        repl = FakeREPL()
        with patch("cli.repl.pool_cmds.pool_manager") as mock_pm:
            mock_pm.is_single.return_value = True
            mock_pm.get_pool.return_value = None
            repl.do_test("my-ai")
            captured = capsys.readouterr()
            assert "不支持" in captured.err or "不支持" in captured.out


class TestDoGroups:
    def _make_connected_repl(self):
        repl = FakeREPL()
        repl.mode = "pool"
        repl.current_pool_name = "test-pool"
        return repl

    def test_not_connected(self, capsys):
        repl = FakeREPL()
        repl.do_groups("")
        captured = capsys.readouterr()
        assert "connect" in captured.err or "connect" in captured.out

    def test_view_groups(self, capsys):
        repl = self._make_connected_repl()
        with patch("cli.repl.pool_cmds.pool_manager") as mock_pm:
            mock_pm.is_pool.return_value = True
            mock_pm.get_all_groups.return_value = {"free", "cn", "other"}
            mock_pm.get_active_groups.return_value = None
            repl.do_groups("")
            captured = capsys.readouterr()
            assert "free" in captured.out
            assert "cn" in captured.out
            assert "other" in captured.out
            assert "全部活跃" in captured.out

    def test_disable_group(self, capsys):
        repl = self._make_connected_repl()
        with patch("cli.repl.pool_cmds.pool_manager") as mock_pm:
            mock_pm.is_pool.return_value = True
            mock_pm.get_all_groups.return_value = {"free", "cn", "other"}
            mock_pm.get_active_groups.return_value = None
            repl.do_groups("disable free")
            captured = capsys.readouterr()
            assert "禁用" in captured.out
            mock_pm.set_active_groups.assert_called_once()
            call_args = mock_pm.set_active_groups.call_args
            assert call_args[0][0] == "test-pool"
            active = call_args[0][1]
            assert "free" not in active
            assert "cn" in active
            assert "other" in active

    def test_enable_group(self, capsys):
        repl = self._make_connected_repl()
        with patch("cli.repl.pool_cmds.pool_manager") as mock_pm:
            mock_pm.is_pool.return_value = True
            mock_pm.get_all_groups.return_value = {"free", "cn", "other"}
            mock_pm.get_active_groups.return_value = {"cn", "other"}
            repl.do_groups("enable free")
            captured = capsys.readouterr()
            mock_pm.set_active_groups.assert_called_once()
            call_args = mock_pm.set_active_groups.call_args
            # 启用后应全部活跃，重置为 None
            assert call_args[0][1] is None

    def test_reset(self, capsys):
        repl = self._make_connected_repl()
        with patch("cli.repl.pool_cmds.pool_manager") as mock_pm:
            mock_pm.is_pool.return_value = True
            mock_pm.get_all_groups.return_value = {"free", "cn"}
            mock_pm.get_active_groups.return_value = {"cn"}
            repl.do_groups("reset")
            captured = capsys.readouterr()
            mock_pm.set_active_groups.assert_called_once_with("test-pool", None)
            assert "重置" in captured.out

    def test_unknown_group(self, capsys):
        repl = self._make_connected_repl()
        with patch("cli.repl.pool_cmds.pool_manager") as mock_pm:
            mock_pm.is_pool.return_value = True
            mock_pm.get_all_groups.return_value = {"free", "cn"}
            mock_pm.get_active_groups.return_value = None
            repl.do_groups("disable unknown")
            captured = capsys.readouterr()
            assert "未知组" in captured.err or "未知组" in captured.out

    def test_invalid_subcommand(self, capsys):
        repl = self._make_connected_repl()
        with patch("cli.repl.pool_cmds.pool_manager") as mock_pm:
            mock_pm.is_pool.return_value = True
            mock_pm.get_all_groups.return_value = {"free"}
            mock_pm.get_active_groups.return_value = None
            repl.do_groups("invalid_cmd")
            captured = capsys.readouterr()
            assert "用法" in captured.err or "用法" in captured.out