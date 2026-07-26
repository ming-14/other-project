"""推箱子贴图定义单元测试 - 16x16 + alpha通道"""

import pytest

from src.tui_pixel.color import Color, TRANSPARENT
from src.tui_pixel.sprites.sokoban import (
    SPRITE_WALL, SPRITE_FLOOR, SPRITE_TARGET,
    SPRITE_BOX, SPRITE_BOX_ON_TARGET,
    SPRITE_PLAYER, SPRITE_PLAYER_ON_TARGET,
    create_sokoban_sheet,
    TARGET_GLOW, BOX_SHADOW, BOX_OK_GLOW,
)


class TestSpriteDimensions:
    @pytest.mark.parametrize("sprite", [
        SPRITE_WALL, SPRITE_FLOOR, SPRITE_TARGET,
        SPRITE_BOX, SPRITE_BOX_ON_TARGET,
        SPRITE_PLAYER, SPRITE_PLAYER_ON_TARGET,
    ])
    def test_16x16(self, sprite):
        assert sprite.width == 16
        assert sprite.height == 16


class TestSpriteNames:
    def test_all_names(self):
        assert SPRITE_WALL.name == "wall"
        assert SPRITE_FLOOR.name == "floor"
        assert SPRITE_TARGET.name == "target"
        assert SPRITE_BOX.name == "box"
        assert SPRITE_BOX_ON_TARGET.name == "box_on_target"
        assert SPRITE_PLAYER.name == "player"
        assert SPRITE_PLAYER_ON_TARGET.name == "player_on_target"


class TestSpriteContent:
    def test_wall_has_opaque(self):
        has = any(SPRITE_WALL.get_pixel(x, y).is_opaque for y in range(16) for x in range(16))
        assert has

    def test_floor_all_filled(self):
        for y in range(16):
            for x in range(16):
                assert SPRITE_FLOOR.get_pixel(x, y).is_opaque

    def test_target_has_transparent(self):
        assert SPRITE_TARGET.get_pixel(0, 0).is_transparent
        assert SPRITE_TARGET.get_pixel(8, 8).is_opaque

    def test_player_has_transparent(self):
        assert SPRITE_PLAYER.get_pixel(0, 0).is_transparent

    def test_player_has_body(self):
        assert SPRITE_PLAYER.get_pixel(4, 4).is_opaque


class TestSpriteAlpha:
    def test_target_has_glow(self):
        assert TARGET_GLOW.a < 255 and TARGET_GLOW.a > 0

    def test_box_has_shadow(self):
        assert BOX_SHADOW.a < 255 and BOX_SHADOW.a > 0

    def test_box_ok_has_glow(self):
        assert BOX_OK_GLOW.a < 255 and BOX_OK_GLOW.a > 0

    def test_target_uses_glow_pixels(self):
        glow_count = sum(
            1 for y in range(16) for x in range(16)
            if not SPRITE_TARGET.get_pixel(x, y).is_transparent
            and SPRITE_TARGET.get_pixel(x, y).a < 255
        )
        assert glow_count > 0

    def test_box_uses_shadow_pixels(self):
        shadow_count = sum(
            1 for y in range(16) for x in range(16)
            if not SPRITE_BOX.get_pixel(x, y).is_transparent
            and SPRITE_BOX.get_pixel(x, y).a < 255
        )
        assert shadow_count > 0


class TestSpriteSheet:
    def test_create_sheet(self):
        sheet = create_sokoban_sheet()
        assert sheet.count == 7


class TestSpriteDebugDump:
    def test_wall_dump(self):
        dump = SPRITE_WALL.debug_dump()
        assert len(dump.split("\n")) == 16

    def test_target_dump_shows_semi_transparent(self):
        dump = SPRITE_TARGET.debug_dump()
        assert "≈" in dump

    def test_box_dump_shows_semi_transparent(self):
        dump = SPRITE_BOX.debug_dump()
        assert "≈" in dump
