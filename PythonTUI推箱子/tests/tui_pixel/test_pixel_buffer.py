"""PixelBuffer类单元测试 - 含alpha通道"""

import pytest

from src.tui_pixel.color import Color, TRANSPARENT
from src.tui_pixel.pixel_buffer import PixelBuffer

C = Color


class TestPixelBufferCreation:
    def test_basic(self):
        buf = PixelBuffer(8, 8)
        assert buf.width == 8
        assert buf.height == 8

    def test_all_transparent(self):
        buf = PixelBuffer(4, 3)
        for y in range(3):
            for x in range(4):
                assert buf.get_pixel(x, y).is_transparent

    def test_invalid_size(self):
        with pytest.raises(ValueError):
            PixelBuffer(0, 5)


class TestPixelBufferSetGet:
    def test_set_and_get(self):
        buf = PixelBuffer(4, 4)
        red = C(255, 0, 0)
        buf.set_pixel(2, 1, red)
        assert buf.get_pixel(2, 1) == red

    def test_set_transparent(self):
        buf = PixelBuffer(4, 4)
        buf.set_pixel(1, 1, C(0, 0, 0))
        buf.set_pixel(1, 1, TRANSPARENT)
        assert buf.get_pixel(1, 1).is_transparent

    def test_get_out_of_bounds(self):
        buf = PixelBuffer(4, 4)
        assert buf.get_pixel(-1, 0).is_transparent
        assert buf.get_pixel(4, 0).is_transparent

    def test_set_out_of_bounds_ignored(self):
        buf = PixelBuffer(4, 4)
        buf.set_pixel(-1, 0, C(255, 0, 0))
        assert buf.get_pixel(0, 0).is_transparent


class TestPixelBufferFill:
    def test_fill_color(self):
        buf = PixelBuffer(3, 2)
        blue = C(0, 0, 255)
        buf.fill(blue)
        for y in range(2):
            for x in range(3):
                assert buf.get_pixel(x, y) == blue

    def test_clear(self):
        buf = PixelBuffer(3, 2)
        buf.fill(C(100, 100, 100))
        buf.clear()
        for y in range(2):
            for x in range(3):
                assert buf.get_pixel(x, y).is_transparent


class TestPixelBufferBlit:
    def test_blit_basic(self):
        buf = PixelBuffer(8, 8)
        sprite = (
            (C(255, 0, 0), C(0, 255, 0)),
            (C(0, 0, 255), C(255, 255, 0)),
        )
        buf.blit(sprite, 2, 3)
        assert buf.get_pixel(2, 3) == C(255, 0, 0)
        assert buf.get_pixel(3, 3) == C(0, 255, 0)
        assert buf.get_pixel(2, 4) == C(0, 0, 255)
        assert buf.get_pixel(3, 4) == C(255, 255, 0)
        assert buf.get_pixel(2, 5).is_transparent

    def test_blit_transparent_skipped(self):
        buf = PixelBuffer(8, 8)
        buf.fill(C(100, 100, 100))
        sprite = (
            (C(255, 0, 0), TRANSPARENT),
            (TRANSPARENT, C(0, 255, 0)),
        )
        buf.blit(sprite, 0, 0)
        assert buf.get_pixel(0, 0) == C(255, 0, 0)
        assert buf.get_pixel(1, 0) == C(100, 100, 100)
        assert buf.get_pixel(0, 1) == C(100, 100, 100)
        assert buf.get_pixel(1, 1) == C(0, 255, 0)

    def test_blit_alpha_blend(self):
        buf = PixelBuffer(8, 8)
        buf.fill(C(0, 0, 0))
        sprite = (
            (C(200, 100, 50, 128),),
        )
        buf.blit(sprite, 0, 0)
        result = buf.get_pixel(0, 0)
        assert result.is_opaque
        assert result.r > 0
        assert result.r < 200

    def test_blit_alpha_over_existing(self):
        buf = PixelBuffer(8, 8)
        buf.set_pixel(0, 0, C(255, 0, 0))
        sprite = ((C(0, 0, 255, 128),),)
        buf.blit(sprite, 0, 0)
        result = buf.get_pixel(0, 0)
        assert result.is_opaque
        assert result.b > 0
        assert result.r < 255

    def test_blit_clipped_right(self):
        buf = PixelBuffer(4, 4)
        sprite = ((C(255, 0, 0), C(0, 255, 0), C(0, 0, 255)),)
        buf.blit(sprite, 3, 0)
        assert buf.get_pixel(3, 0) == C(255, 0, 0)
        assert buf.get_pixel(4, 0).is_transparent

    def test_blit_buffer(self):
        buf = PixelBuffer(8, 8)
        src = PixelBuffer(2, 2)
        src.set_pixel(0, 0, C(255, 0, 0))
        src.set_pixel(1, 1, C(0, 255, 0))
        buf.blit_buffer(src, 3, 2)
        assert buf.get_pixel(3, 2) == C(255, 0, 0)
        assert buf.get_pixel(4, 3) == C(0, 255, 0)


class TestPixelBufferCrop:
    def test_crop_basic(self):
        buf = PixelBuffer(6, 6)
        buf.fill(C(100, 100, 100))
        buf.set_pixel(2, 2, C(255, 0, 0))
        sub = buf.crop(1, 1, 3, 3)
        assert sub.width == 3
        assert sub.height == 3
        assert sub.get_pixel(1, 1) == C(255, 0, 0)
        assert sub.get_pixel(0, 0) == C(100, 100, 100)


class TestPixelBufferData:
    def test_to_data(self):
        buf = PixelBuffer(2, 2)
        buf.set_pixel(0, 0, C(1, 2, 3))
        data = buf.to_data()
        assert data[0][0] == C(1, 2, 3)
        assert data[1][1].is_transparent

    def test_from_data(self):
        data = (
            (C(255, 0, 0), TRANSPARENT),
            (TRANSPARENT, C(0, 255, 0)),
        )
        buf = PixelBuffer.from_data(data)
        assert buf.width == 2
        assert buf.height == 2
        assert buf.get_pixel(0, 0) == C(255, 0, 0)
        assert buf.get_pixel(1, 0).is_transparent
        assert buf.get_pixel(1, 1) == C(0, 255, 0)

    def test_roundtrip(self):
        buf = PixelBuffer(3, 2)
        buf.set_pixel(0, 0, C(1, 1, 1))
        buf.set_pixel(2, 1, C(2, 2, 2))
        data = buf.to_data()
        buf2 = PixelBuffer.from_data(data)
        for y in range(buf.height):
            for x in range(buf.width):
                assert buf2.get_pixel(x, y) == buf.get_pixel(x, y)


class TestPixelBufferDebug:
    def test_debug_dump_opaque(self):
        buf = PixelBuffer(3, 2)
        buf.set_pixel(0, 0, C(1, 1, 1))
        buf.set_pixel(2, 1, C(2, 2, 2))
        dump = buf.debug_dump()
        assert "█" in dump
        assert "·" in dump

    def test_debug_dump_semi_transparent(self):
        buf = PixelBuffer(2, 1)
        buf.set_pixel(0, 0, C(255, 0, 0, 128))
        dump = buf.debug_dump()
        assert "≈" in dump

    def test_debug_pixel_at(self):
        buf = PixelBuffer(4, 4)
        buf.set_pixel(1, 2, C(255, 0, 0))
        assert "Color(255,0,0)" in buf.debug_pixel_at(1, 2)
        assert "transparent" in buf.debug_pixel_at(0, 0)
