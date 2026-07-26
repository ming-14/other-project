"""Color类单元测试 - 含alpha通道"""

import pytest

from src.tui_pixel.color import Color, TRANSPARENT, ANSI_RESET


class TestColorCreation:
    def test_basic(self):
        c = Color(255, 128, 0)
        assert c.r == 255
        assert c.g == 128
        assert c.b == 0
        assert c.a == 255

    def test_with_alpha(self):
        c = Color(255, 128, 0, 128)
        assert c.a == 128

    def test_black(self):
        c = Color(0, 0, 0)
        assert c.r == c.g == c.b == 0

    def test_invalid_negative(self):
        with pytest.raises(ValueError):
            Color(-1, 0, 0)

    def test_invalid_over_255(self):
        with pytest.raises(ValueError):
            Color(256, 0, 0)

    def test_invalid_alpha(self):
        with pytest.raises(ValueError):
            Color(0, 0, 0, 256)
        with pytest.raises(ValueError):
            Color(0, 0, 0, -1)


class TestColorAlpha:
    def test_is_opaque(self):
        assert Color(100, 100, 100, 255).is_opaque
        assert not Color(100, 100, 100, 254).is_opaque

    def test_is_transparent(self):
        assert Color(0, 0, 0, 0).is_transparent
        assert not Color(0, 0, 0, 1).is_transparent

    def test_transparent_constant(self):
        assert TRANSPARENT.is_transparent
        assert TRANSPARENT.a == 0


class TestColorAlphaBlend:
    def test_opaque_over_bg(self):
        src = Color(255, 0, 0, 255)
        bg = Color(0, 0, 255)
        result = src.alpha_blend(bg)
        assert result == Color(255, 0, 0)

    def test_transparent_over_bg(self):
        src = Color(255, 0, 0, 0)
        bg = Color(0, 0, 255)
        result = src.alpha_blend(bg)
        assert result == bg

    def test_half_alpha_over_black(self):
        src = Color(200, 100, 50, 128)
        bg = Color(0, 0, 0)
        result = src.alpha_blend(bg)
        assert result.is_opaque
        assert result.r > 0
        assert result.g > 0
        assert result.b > 0

    def test_half_alpha_over_white(self):
        src = Color(0, 0, 0, 128)
        bg = Color(255, 255, 255)
        result = src.alpha_blend(bg)
        assert result.is_opaque
        assert result.r < 255
        assert result.r > 0

    def test_blend_idempotent_opaque(self):
        src = Color(100, 200, 50, 255)
        bg = Color(0, 0, 0)
        assert src.alpha_blend(bg) == Color(100, 200, 50)


class TestColorEquality:
    def test_equal(self):
        assert Color(10, 20, 30) == Color(10, 20, 30)
        assert Color(10, 20, 30, 128) == Color(10, 20, 30, 128)

    def test_not_equal_alpha(self):
        assert Color(10, 20, 30, 255) != Color(10, 20, 30, 128)

    def test_hash_equal(self):
        assert hash(Color(10, 20, 30)) == hash(Color(10, 20, 30))

    def test_hashable_in_set(self):
        s = {Color(1, 2, 3), Color(1, 2, 3), Color(4, 5, 6)}
        assert len(s) == 2


class TestColorAnsi:
    def test_fg_truecolor(self):
        c = Color(255, 128, 0)
        assert c.fg_truecolor() == "\033[38;2;255;128;0m"

    def test_bg_truecolor(self):
        c = Color(100, 200, 50)
        assert c.bg_truecolor() == "\033[48;2;100;200;50m"

    def test_fg_256(self):
        c = Color(255, 0, 0)
        code = c.to_256()
        assert c.fg_256() == f"\033[38;5;{code}m"


class TestColorTo256:
    def test_black(self):
        assert Color(0, 0, 0).to_256() == 16

    def test_white(self):
        assert Color(255, 255, 255).to_256() == 231

    def test_pure_red(self):
        assert Color(255, 0, 0).to_256() == 196

    def test_pure_green(self):
        assert Color(0, 255, 0).to_256() == 46

    def test_pure_blue(self):
        assert Color(0, 0, 255).to_256() == 21

    def test_gray_low(self):
        assert Color(8, 8, 8).to_256() == 232

    def test_gray_high(self):
        assert Color(248, 248, 248).to_256() == 255

    def test_gray_252(self):
        assert Color(252, 252, 252).to_256() == 231

    def test_result_in_range(self):
        for r in range(0, 256, 32):
            for g in range(0, 256, 32):
                for b in range(0, 256, 32):
                    code = Color(r, g, b).to_256()
                    assert 0 <= code <= 255


class TestColorFromHex:
    def test_with_hash(self):
        assert Color.from_hex("#FF8000") == Color(255, 128, 0)

    def test_without_hash(self):
        assert Color.from_hex("FF8000") == Color(255, 128, 0)

    def test_with_alpha(self):
        assert Color.from_hex("#FF800080") == Color(255, 128, 0, 128)

    def test_invalid_length(self):
        with pytest.raises(ValueError):
            Color.from_hex("#FFF")


class TestColorFrom256:
    def test_black(self):
        c = Color.from_256(16)
        assert c.r == 0 and c.g == 0 and c.b == 0

    def test_invalid(self):
        with pytest.raises(ValueError):
            Color.from_256(256)


class TestColorRepr:
    def test_repr_opaque(self):
        assert repr(Color(1, 2, 3)) == "Color(1,2,3)"

    def test_repr_with_alpha(self):
        assert repr(Color(1, 2, 3, 128)) == "Color(1,2,3,128)"
