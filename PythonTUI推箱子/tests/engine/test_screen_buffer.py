"""ScreenBuffer单元测试"""

from io import StringIO

from src.engine.screen_buffer import ScreenBuffer


class TestScreenBuffer:
    def test_creation(self):
        buf = ScreenBuffer(10, 20)
        assert buf.rows == 10
        assert buf.cols == 20

    def test_set_get_row(self):
        buf = ScreenBuffer(5, 10)
        buf.set_row(0, "Hello")
        assert buf.get_row(0) == "Hello"

    def test_set_row_out_of_bounds(self):
        buf = ScreenBuffer(5, 10)
        buf.set_row(-1, "X")
        buf.set_row(5, "X")

    def test_clear_back(self):
        buf = ScreenBuffer(5, 10)
        buf.set_row(0, "Hello")
        buf.clear_back()
        assert buf.get_row(0) == ""

    def test_resize(self):
        buf = ScreenBuffer(5, 10)
        buf.resize(8, 15)
        assert buf.rows == 8
        assert buf.cols == 15

    def test_resize_same(self):
        buf = ScreenBuffer(5, 10)
        buf.resize(5, 10)
        assert buf.rows == 5

    def test_first_flush_is_full_redraw(self):
        out = StringIO()
        buf = ScreenBuffer(3, 5)
        buf._out = out
        buf.set_row(0, "Hello")
        diff = buf.swap_and_flush()
        assert diff == 3
        output = out.getvalue()
        assert "Hello" in output

    def test_diff_update_no_change(self):
        out = StringIO()
        buf = ScreenBuffer(3, 5)
        buf._out = out
        buf.set_row(0, "Hello")
        buf.swap_and_flush()
        out.truncate(0)
        out.seek(0)
        buf.set_row(0, "Hello")
        diff = buf.swap_and_flush()
        assert diff == 0

    def test_diff_update_one_row_changed(self):
        out = StringIO()
        buf = ScreenBuffer(3, 5)
        buf._out = out
        buf.set_row(0, "Hello")
        buf.set_row(1, "World")
        buf.swap_and_flush()
        out.truncate(0)
        out.seek(0)
        buf.set_row(0, "Hello")
        buf.set_row(1, "Changed")
        diff = buf.swap_and_flush()
        assert diff == 1
        output = out.getvalue()
        assert "Changed" in output
        assert "\033[2;1H" in output

    def test_init_screen_sets_full_redraw(self):
        out = StringIO()
        buf = ScreenBuffer(3, 5)
        buf._out = out
        buf.set_row(0, "Hello")
        buf.swap_and_flush()
        buf.init_screen()
        buf.set_row(0, "Hello")
        diff = buf.swap_and_flush()
        assert diff == 3

    def test_resize_sets_full_redraw(self):
        out = StringIO()
        buf = ScreenBuffer(3, 5)
        buf._out = out
        buf.set_row(0, "Hello")
        buf.swap_and_flush()
        buf.resize(5, 10)
        buf.set_row(0, "Hello")
        diff = buf.swap_and_flush()
        assert diff == 5

    def test_debug_dump_row(self):
        buf = ScreenBuffer(3, 10)
        buf.set_row(1, "Hello")
        assert buf.debug_dump_row(1) == "Hello"

    def test_debug_dump_row_strips_ansi(self):
        buf = ScreenBuffer(3, 20)
        buf.set_row(0, "\033[31mRed\033[0m")
        assert buf.debug_dump_row(0) == "Red"

    def test_debug_dump_row_out_of_bounds(self):
        buf = ScreenBuffer(3, 5)
        assert buf.debug_dump_row(-1) == ""

    def test_debug_dump_front(self):
        buf = ScreenBuffer(3, 5)
        result = buf.debug_dump_front()
        assert "Front:" in result
        assert "full_redraw=" in result
