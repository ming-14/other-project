"""LayoutEngine单元测试"""

from src.engine.layout_engine import LayoutEngine
from src.engine.map_engine import MapEngine
from src.engine.screen_buffer import ScreenBuffer


SIMPLE_LEVEL = [
    "######",
    "#.@$ #",
    "######",
]


class TestLayoutEngine:
    def test_init(self):
        engine = LayoutEngine(use_color=False)
        buf = engine.init(24, 80)
        assert isinstance(buf, ScreenBuffer)
        assert buf.rows == 24
        assert buf.cols == 80

    def test_render_title(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = LayoutEngine(use_color=False)
        engine.init(24, 80)
        engine.render(game_map, 0, 3, steps=0, pushes=0)
        title = engine.buffer.debug_dump_row(0)
        assert "SOKOBAN" in title

    def test_render_border(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = LayoutEngine(use_color=False)
        engine.init(24, 80)
        engine.render(game_map, 0, 3, steps=0, pushes=0)
        top_row = engine.buffer.debug_dump_row(1)
        assert top_row.startswith("┌")
        assert top_row.endswith("┐")

    def test_render_status(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = LayoutEngine(use_color=False)
        engine.init(24, 80)
        engine.render(game_map, 0, 3, steps=5, pushes=2)
        status = engine.buffer.debug_dump_row(23)
        assert "5" in status
        assert "2" in status

    def test_render_map_content(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = LayoutEngine(use_color=False)
        engine.init(24, 80)
        engine.render(game_map, 0, 3, steps=0, pushes=0)
        found = False
        for r in range(2, 23):
            row = engine.buffer.debug_dump_row(r)
            if "@@" in row:
                found = True
                break
        assert found, "地图内容应该被渲染"

    def test_render_win_overlay(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = LayoutEngine(use_color=False)
        engine.init(24, 80)
        engine.render(game_map, 0, 3, steps=1, pushes=1, state="won")
        found = False
        for r in range(24):
            row = engine.buffer.debug_dump_row(r)
            if "CLEAR" in row:
                found = True
                break
        assert found

    def test_resize(self):
        engine = LayoutEngine(use_color=False)
        engine.init(24, 80)
        engine.resize(30, 100)
        assert engine.buffer.rows == 30
        assert engine.buffer.cols == 100

    def test_level_info_in_title(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = LayoutEngine(use_color=False)
        engine.init(24, 80)
        engine.render(game_map, 2, 5, steps=0, pushes=0)
        title = engine.buffer.debug_dump_row(0)
        assert "3" in title
        assert "5" in title

    def test_map_area_has_borders(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = LayoutEngine(use_color=False)
        engine.init(24, 80)
        engine.render(game_map, 0, 3, steps=0, pushes=0)
        for r in range(2, 23):
            row = engine.buffer.debug_dump_row(r)
            if row:
                assert row.startswith("│") or row.strip() == ""
                if row.strip():
                    assert row.rstrip().endswith("│")
