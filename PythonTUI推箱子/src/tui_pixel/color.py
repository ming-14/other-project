"""Color - 颜色系统，RGBA与ANSI转义码"""

from __future__ import annotations


class Color:
    """RGBA颜色，不可变。RGB各分量0-255，Alpha 0-255(0=全透明,255=全不透明)"""

    __slots__ = ("_r", "_g", "_b", "_a")

    def __init__(self, r: int, g: int, b: int, a: int = 255) -> None:
        if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
            raise ValueError(f"RGB分量必须在0-255范围内: ({r},{g},{b})")
        if not (0 <= a <= 255):
            raise ValueError(f"Alpha必须在0-255范围内: {a}")
        self._r = r
        self._g = g
        self._b = b
        self._a = a

    @property
    def r(self) -> int:
        return self._r

    @property
    def g(self) -> int:
        return self._g

    @property
    def b(self) -> int:
        return self._b

    @property
    def a(self) -> int:
        return self._a

    @property
    def is_opaque(self) -> bool:
        return self._a == 255

    @property
    def is_transparent(self) -> bool:
        return self._a == 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Color):
            return NotImplemented
        return (self._r == other._r and self._g == other._g
                and self._b == other._b and self._a == other._a)

    def __hash__(self) -> int:
        return hash((self._r, self._g, self._b, self._a))

    def __repr__(self) -> str:
        if self._a == 255:
            return f"Color({self._r},{self._g},{self._b})"
        return f"Color({self._r},{self._g},{self._b},{self._a})"

    def fg_truecolor(self) -> str:
        """TrueColor前景色ANSI码: \033[38;2;R;G;Bm"""
        return f"\033[38;2;{self._r};{self._g};{self._b}m"

    def bg_truecolor(self) -> str:
        """TrueColor背景色ANSI码: \033[48;2;R;G;Bm"""
        return f"\033[48;2;{self._r};{self._g};{self._b}m"

    def fg_256(self) -> str:
        """ANSI 256色前景色ANSI码"""
        return f"\033[38;5;{self.to_256()}m"

    def bg_256(self) -> str:
        """ANSI 256色背景色ANSI码"""
        return f"\033[48;5;{self.to_256()}m"

    def to_256(self) -> int:
        """将RGB转换为ANSI 256色号(0-255)"""
        r, g, b = self._r, self._g, self._b

        if r == g == b:
            if r < 8:
                return 16
            if r > 248:
                return 231
            idx = round((r - 8) / 10)
            return 232 + min(idx, 23)

        return 16 + (36 * _scale_256(r) + 6 * _scale_256(g) + _scale_256(b))

    def alpha_blend(self, bg: Color) -> Color:
        """将此颜色(alpha混合)到背景色上，返回不透明结果

        out = src * alpha + bg * (1 - alpha)
        """
        if self._a == 255:
            return Color(self._r, self._g, self._b)
        if self._a == 0:
            return bg
        sa = self._a
        da = 255 - sa
        r = (self._r * sa + bg._r * da + 127) // 255
        g = (self._g * sa + bg._g * da + 127) // 255
        b = (self._b * sa + bg._b * da + 127) // 255
        return Color(r, g, b)

    @classmethod
    def from_hex(cls, hex_str: str) -> Color:
        """从十六进制字符串创建Color: '#RRGGBB'/'#RRGGBBAA' 或不带#"""
        h = hex_str.lstrip("#")
        if len(h) == 6:
            return cls(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        if len(h) == 8:
            return cls(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16))
        raise ValueError(f"无效十六进制颜色: {hex_str}")

    @classmethod
    def from_256(cls, code: int) -> Color:
        """从ANSI 256色号反推近似RGB(不透明)"""
        if not (0 <= code <= 255):
            raise ValueError(f"ANSI 256色号必须在0-255范围内: {code}")
        if code < 16:
            return _STANDARD_COLORS_256[code]
        if code < 232:
            code -= 16
            b = code % 6
            code //= 6
            g = code % 6
            r = code // 6
            return Color(_unscale_256(r), _unscale_256(g), _unscale_256(b))
        gray = 8 + (code - 232) * 10
        return Color(gray, gray, gray)


TRANSPARENT = Color(0, 0, 0, 0)


def _scale_256(v: int) -> int:
    """将0-255映射到0-5的6级"""
    if v < 48:
        return 0
    if v < 115:
        return 1
    return min(5, round((v - 35) / 40))


def _unscale_256(v: int) -> int:
    """将0-5映射回0-255"""
    if v == 0:
        return 0
    return 55 + v * 40


_STANDARD_COLORS_256: list[Color] = [
    Color(0, 0, 0), Color(128, 0, 0), Color(0, 128, 0), Color(128, 128, 0),
    Color(0, 0, 128), Color(128, 0, 128), Color(0, 128, 128), Color(192, 192, 192),
    Color(128, 128, 128), Color(255, 0, 0), Color(0, 255, 0), Color(255, 255, 0),
    Color(0, 0, 255), Color(255, 0, 255), Color(0, 255, 255), Color(255, 255, 255),
]

ANSI_RESET = "\033[0m"
