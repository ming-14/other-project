"""TileRendererV2单元测试"""

from src.engine.tile_renderer_v2 import TileRendererV2, COLOR_STYLES, PLAIN_STYLES_V2
from src.engine.tile import TileType


class TestTileRendererV2:
    def test_render_color(self):
        r = TileRendererV2()
        result = r.render(TileType.WALL, use_color=True)
        assert "██" in result
        assert "\033[" in result

    def test_render_no_color(self):
        r = TileRendererV2()
        result = r.render(TileType.WALL, use_color=False)
        assert result == "██"

    def test_render_plain(self):
        r = TileRendererV2(PLAIN_STYLES_V2)
        for tile in TileType:
            result = r.render_plain(tile)
            assert len(result) == 2

    def test_char_width(self):
        r = TileRendererV2()
        assert r.char_width() == 2

    def test_all_tiles_have_styles(self):
        r = TileRendererV2()
        for tile in TileType:
            result = r.render(tile, use_color=False)
            assert len(result) == 2

    def test_player_render(self):
        r = TileRendererV2()
        result = r.render(TileType.PLAYER, use_color=False)
        assert result == "♦♦"

    def test_box_on_target(self):
        r = TileRendererV2()
        result = r.render(TileType.BOX_ON_TARGET, use_color=False)
        assert result == "★★"
