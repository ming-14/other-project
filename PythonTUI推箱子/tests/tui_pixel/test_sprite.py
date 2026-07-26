"""Sprite与SpriteSheet单元测试"""

import pytest

from src.tui_pixel.color import Color, TRANSPARENT
from src.tui_pixel.sprite import Sprite, SpriteSheet

C = Color


class TestSpriteCreation:
    def test_basic(self):
        data = (
            (C(255, 0, 0), TRANSPARENT),
            (TRANSPARENT, C(0, 255, 0)),
        )
        s = Sprite("test", data)
        assert s.name == "test"
        assert s.width == 2
        assert s.height == 2

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            Sprite("bad", ())

    def test_inconsistent_width_raises(self):
        data = (
            (C(255, 0, 0), C(0, 255, 0)),
            (C(0, 0, 255),),
        )
        with pytest.raises(ValueError):
            Sprite("bad", data)


class TestSpriteAccess:
    def test_get_pixel(self):
        data = (
            (C(255, 0, 0), TRANSPARENT),
            (TRANSPARENT, C(0, 255, 0)),
        )
        s = Sprite("test", data)
        assert s.get_pixel(0, 0) == C(255, 0, 0)
        assert s.get_pixel(1, 0).is_transparent
        assert s.get_pixel(0, 1).is_transparent
        assert s.get_pixel(1, 1) == C(0, 255, 0)

    def test_get_pixel_out_of_bounds(self):
        s = Sprite("test", ((C(1, 1, 1),),))
        assert s.get_pixel(-1, 0).is_transparent
        assert s.get_pixel(1, 0).is_transparent

    def test_data_property(self):
        data = ((C(255, 0, 0), C(0, 255, 0)),)
        s = Sprite("test", data)
        assert s.data == data


class TestSpriteToBuffer:
    def test_to_buffer(self):
        data = (
            (C(255, 0, 0), TRANSPARENT),
            (TRANSPARENT, C(0, 255, 0)),
        )
        s = Sprite("test", data)
        buf = s.to_buffer()
        assert buf.width == 2
        assert buf.height == 2
        assert buf.get_pixel(0, 0) == C(255, 0, 0)
        assert buf.get_pixel(1, 0).is_transparent


class TestSpriteAlpha:
    def test_alpha_pixel(self):
        data = ((C(255, 0, 0, 128),),)
        s = Sprite("test_alpha", data)
        p = s.get_pixel(0, 0)
        assert p.a == 128
        assert not p.is_opaque
        assert not p.is_transparent

    def test_debug_dump_semi_transparent(self):
        data = ((C(255, 0, 0, 128), TRANSPARENT),)
        s = Sprite("test", data)
        dump = s.debug_dump()
        assert "≈" in dump
        assert "·" in dump


class TestSpriteDebug:
    def test_debug_dump(self):
        data = (
            (C(255, 0, 0), TRANSPARENT),
            (TRANSPARENT, C(0, 255, 0)),
        )
        s = Sprite("test", data)
        assert s.debug_dump() == "█·\n·█"

    def test_repr(self):
        s = Sprite("test", ((C(1, 1, 1),),))
        assert repr(s) == "Sprite('test', 1x1)"


class TestSpriteSheet:
    def test_add_and_get(self):
        sheet = SpriteSheet("test_sheet")
        s = Sprite("wall", ((C(100, 100, 100),),))
        sheet.add(s)
        assert sheet.get("wall") is s
        assert sheet.get("floor") is None

    def test_getitem(self):
        sheet = SpriteSheet("test_sheet")
        s = Sprite("wall", ((C(100, 100, 100),),))
        sheet.add(s)
        assert sheet["wall"] is s
        with pytest.raises(KeyError):
            sheet["floor"]

    def test_contains(self):
        sheet = SpriteSheet("test_sheet")
        sheet.add(Sprite("wall", ((C(100, 100, 100),),)))
        assert "wall" in sheet
        assert "floor" not in sheet

    def test_names_and_count(self):
        sheet = SpriteSheet("test_sheet")
        sheet.add(Sprite("a", ((C(1, 1, 1),),)))
        sheet.add(Sprite("b", ((C(2, 2, 2),),)))
        assert sheet.count == 2
        assert set(sheet.names) == {"a", "b"}
