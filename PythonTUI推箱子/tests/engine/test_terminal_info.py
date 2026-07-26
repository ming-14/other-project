"""TerminalInfo单元测试"""

from src.engine.terminal_info import TerminalInfo, MIN_COLS, MIN_ROWS


class TestTerminalInfo:
    def test_default_minimum(self):
        info = TerminalInfo()
        assert info.cols >= MIN_COLS
        assert info.rows >= MIN_ROWS

    def test_poll_no_change(self):
        info = TerminalInfo()
        result = info.poll()
        assert isinstance(result, bool)

    def test_repr(self):
        info = TerminalInfo()
        r = repr(info)
        assert "TerminalInfo" in r
