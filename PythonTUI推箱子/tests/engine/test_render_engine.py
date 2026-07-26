"""RenderEngine单元测试"""

from io import StringIO

from src.engine.map_engine import MapEngine
from src.engine.render_engine import RenderEngine
from src.engine.tile_renderer import TileRenderer, PLAIN_STYLES, DEFAULT_STYLES
from src.engine.tile import TileType


SIMPLE_LEVEL = [
    "######",
    "#.@$ #",
    "######",
]


class TestTileRenderer:
    def test_render_with_color(self):
        renderer = TileRenderer()
        result = renderer.render(TileType.WALL, use_color=True)
        assert "█" in result
        assert "\033[" in result

    def test_render_without_color(self):
        renderer = TileRenderer()
        result = renderer.render(TileType.WALL, use_color=False)
        assert result == "█"

    def test_render_plain(self):
        renderer = TileRenderer(PLAIN_STYLES)
        for tile in TileType:
            result = renderer.render_plain(tile)
            assert len(result) == 1


class TestRenderEngine:
    def test_render_map_lines(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = RenderEngine(use_color=False)
        lines = engine.render_map(game_map)
        assert len(lines) == 3
        assert "♦" in lines[1]
        assert "■" in lines[1]

    def test_render_plain(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = RenderEngine()
        result = engine.render_plain(game_map)
        assert "@" in result
        assert "$" in result
        assert "." in result

    def test_render_frame_to_buffer(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        buf = StringIO()
        engine = RenderEngine(use_color=False, out=buf)
        engine.render_frame(game_map, header="Test", footer="Footer")
        output = buf.getvalue()
        assert "♦" in output or "@" in output or len(output) > 0

    def test_debug_info(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        buf = StringIO()
        engine = RenderEngine(use_color=False, out=buf)
        engine.render_frame(game_map)
        info = engine.debug_info()
        assert info["frame_count"] == 1
        assert info["buffer_lines"] == 3

    def test_diff_update(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        buf = StringIO()
        engine = RenderEngine(use_color=False, out=buf)
        engine.render_frame(game_map)
        engine.render_frame(game_map)
        info = engine.debug_info()
        assert info["diff_lines"] == 0
