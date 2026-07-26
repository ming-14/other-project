"""HalfBlockRenderer单元测试 - 含alpha通道"""

import pytest

from src.tui_pixel.color import Color, TRANSPARENT, ANSI_RESET
from src.tui_pixel.pixel_buffer import PixelBuffer
from src.tui_pixel.renderer import HalfBlockRenderer, ColorMode

C = Color


class TestHalfBlockRendererComputeCell:
    def setup_method(self):
        self.renderer = HalfBlockRenderer()

    def test_both_transparent(self):
        char, fg, bg, full = self.renderer._compute_cell(None, None)
        assert char == " "

    def test_both_same_color(self):
        red = C(255, 0, 0)
        char, fg, bg, full = self.renderer._compute_cell(red, red)
        assert char == "█"
        assert full is True

    def test_top_only(self):
        red = C(255, 0, 0)
        char, fg, bg, full = self.renderer._compute_cell(red, None)
        assert char == "▀"

    def test_bottom_only(self):
        blue = C(0, 0, 255)
        char, fg, bg, full = self.renderer._compute_cell(None, blue)
        assert char == "▄"

    def test_top_and_bottom_different(self):
        red = C(255, 0, 0)
        blue = C(0, 0, 255)
        char, fg, bg, full = self.renderer._compute_cell(red, blue)
        assert char == "▀"
        assert fg == red
        assert bg == blue


class TestHalfBlockRendererFlatten:
    def test_flatten_opaque(self):
        renderer = HalfBlockRenderer()
        result = renderer._flatten_pixel(C(255, 0, 0, 255))
        assert result == C(255, 0, 0)

    def test_flatten_transparent(self):
        renderer = HalfBlockRenderer()
        result = renderer._flatten_pixel(TRANSPARENT)
        assert result is None

    def test_flatten_semi_transparent_on_black(self):
        renderer = HalfBlockRenderer(bg_color=C(0, 0, 0))
        result = renderer._flatten_pixel(C(200, 100, 50, 128))
        assert result is not None
        assert result.is_opaque
        assert result.r > 0

    def test_flatten_semi_transparent_on_white(self):
        renderer = HalfBlockRenderer(bg_color=C(255, 255, 255))
        result = renderer._flatten_pixel(C(0, 0, 0, 128))
        assert result is not None
        assert result.is_opaque
        assert result.r < 255


class TestHalfBlockRendererRender:
    def test_empty_buffer(self):
        buf = PixelBuffer(4, 2)
        renderer = HalfBlockRenderer()
        lines = renderer.render(buf)
        assert len(lines) == 1
        assert lines[0] == "    "

    def test_single_pixel_top(self):
        buf = PixelBuffer(2, 2)
        buf.set_pixel(0, 0, C(255, 0, 0))
        renderer = HalfBlockRenderer(ColorMode.TRUECOLOR)
        lines = renderer.render(buf)
        assert len(lines) == 1
        assert "▀" in lines[0]

    def test_full_block_same_color(self):
        buf = PixelBuffer(2, 2)
        red = C(255, 0, 0)
        buf.set_pixel(0, 0, red)
        buf.set_pixel(0, 1, red)
        renderer = HalfBlockRenderer(ColorMode.TRUECOLOR)
        lines = renderer.render(buf)
        assert "█" in lines[0]

    def test_semi_transparent_pixel(self):
        buf = PixelBuffer(1, 2)
        buf.set_pixel(0, 0, C(255, 0, 0, 128))
        renderer = HalfBlockRenderer(ColorMode.TRUECOLOR, bg_color=C(0, 0, 0))
        lines = renderer.render(buf)
        assert len(lines) == 1
        assert "▀" in lines[0]

    def test_truecolor_mode(self):
        buf = PixelBuffer(1, 2)
        buf.set_pixel(0, 0, C(255, 128, 0))
        renderer = HalfBlockRenderer(ColorMode.TRUECOLOR)
        lines = renderer.render(buf)
        assert "\033[38;2;255;128;0m" in lines[0]

    def test_ansi256_mode(self):
        buf = PixelBuffer(1, 2)
        buf.set_pixel(0, 0, C(255, 0, 0))
        renderer = HalfBlockRenderer(ColorMode.ANSI256)
        lines = renderer.render(buf)
        assert "\033[38;5;" in lines[0]

    def test_ansi_reset_at_end(self):
        buf = PixelBuffer(1, 2)
        buf.set_pixel(0, 0, C(255, 0, 0))
        renderer = HalfBlockRenderer(ColorMode.TRUECOLOR)
        lines = renderer.render(buf)
        assert lines[0].endswith(ANSI_RESET)


class TestHalfBlockRendererBgColor:
    def test_custom_bg_color(self):
        buf = PixelBuffer(1, 2)
        buf.set_pixel(0, 0, C(255, 0, 0, 128))
        renderer = HalfBlockRenderer(bg_color=C(0, 0, 255))
        lines = renderer.render(buf)
        assert len(lines) == 1

    def test_bg_color_property(self):
        renderer = HalfBlockRenderer(bg_color=C(30, 30, 38))
        assert renderer.bg_color == C(30, 30, 38)


class TestHalfBlockRendererRenderPlain:
    def test_all_transparent(self):
        buf = PixelBuffer(3, 2)
        renderer = HalfBlockRenderer()
        lines = renderer.render_plain(buf)
        assert lines == ["   "]

    def test_with_pixels(self):
        buf = PixelBuffer(3, 2)
        buf.set_pixel(0, 0, C(255, 0, 0))
        buf.set_pixel(1, 1, C(0, 255, 0))
        buf.set_pixel(2, 0, C(0, 0, 255))
        renderer = HalfBlockRenderer()
        lines = renderer.render_plain(buf)
        assert lines == ["███"]

    def test_semi_transparent_shows_as_filled(self):
        buf = PixelBuffer(1, 2)
        buf.set_pixel(0, 0, C(255, 0, 0, 128))
        renderer = HalfBlockRenderer()
        lines = renderer.render_plain(buf)
        assert lines == ["█"]


class TestHalfBlockRendererRenderDebug:
    def test_chars(self):
        buf = PixelBuffer(5, 2)
        red = C(255, 0, 0)
        blue = C(0, 0, 255)
        buf.set_pixel(0, 0, red)
        buf.set_pixel(1, 1, blue)
        buf.set_pixel(2, 0, red)
        buf.set_pixel(2, 1, red)
        renderer = HalfBlockRenderer()
        lines = renderer.render_debug(buf)
        assert lines[0][0] == "▀"
        assert lines[0][1] == "▄"
        assert lines[0][2] == "█"
        assert lines[0][3] == " "
