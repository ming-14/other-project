"""HalfBlockRenderer - 半块渲染器，PixelBuffer → ANSI终端输出

原理：每个终端字符单元用 ▀ (U+2580 UPPER HALF BLOCK) 表示2个垂直像素
- 前景色 = 上半像素颜色
- 背景色 = 下半像素颜色

半透明像素在渲染时与bg_color(默认终端背景色)做alpha混合后输出。
"""

from __future__ import annotations

import enum

from .color import Color, TRANSPARENT, ANSI_RESET
from .pixel_buffer import PixelBuffer


class ColorMode(enum.Enum):
    TRUECOLOR = "truecolor"
    ANSI256 = "ansi256"


class HalfBlockRenderer:
    """半块渲染器：将PixelBuffer渲染为ANSI字符串行列表

    每两行像素合并为一个终端行（半块方格）
    半透明像素与bg_color混合后输出为不透明色
    """

    def __init__(
        self,
        color_mode: ColorMode = ColorMode.TRUECOLOR,
        bg_color: Color = Color(0, 0, 0),
    ) -> None:
        self._color_mode = color_mode
        self._bg_color = bg_color

    @property
    def color_mode(self) -> ColorMode:
        return self._color_mode

    @property
    def bg_color(self) -> Color:
        return self._bg_color

    def render(self, buf: PixelBuffer) -> list[str]:
        """渲染PixelBuffer为ANSI字符串行列表

        Returns:
            终端行列表，每行是带ANSI转义码的字符串
        """
        lines: list[str] = []
        for y in range(0, buf.height, 2):
            line = self._render_row_pair(buf, y)
            lines.append(line)
        return lines

    def _flatten_pixel(self, pixel: Color) -> Color | None:
        """将像素与背景色混合，返回不透明Color或None(全透明)"""
        if pixel.is_transparent:
            return None
        if pixel.is_opaque:
            return pixel
        return pixel.alpha_blend(self._bg_color)

    def _render_row_pair(self, buf: PixelBuffer, y: int) -> str:
        """渲染一对像素行(y, y+1)为一个终端行"""
        parts: list[str] = []
        prev_fg: Color | None = None
        prev_bg: Color | None = None
        prev_is_fullblock = False

        for x in range(buf.width):
            top_raw = buf.get_pixel(x, y)
            bottom_raw = buf.get_pixel(x, y + 1) if y + 1 < buf.height else TRANSPARENT

            top = self._flatten_pixel(top_raw)
            bottom = self._flatten_pixel(bottom_raw)

            char, fg, bg, is_fullblock = self._compute_cell(top, bottom)

            if char == " ":
                if prev_fg is not None or prev_bg is not None:
                    parts.append(ANSI_RESET)
                    prev_fg = None
                    prev_bg = None
                    prev_is_fullblock = False
                parts.append(" ")
                continue

            need_fg = fg != prev_fg
            need_bg = bg != prev_bg
            need_reset_style = prev_is_fullblock != is_fullblock

            if need_fg or need_bg or need_reset_style:
                if prev_fg is not None or prev_bg is not None or prev_is_fullblock:
                    parts.append(ANSI_RESET)
                if fg is not None:
                    parts.append(self._fg_code(fg))
                if bg is not None:
                    parts.append(self._bg_code(bg))
                prev_fg = fg
                prev_bg = bg
                prev_is_fullblock = is_fullblock

            parts.append(char)

        if prev_fg is not None or prev_bg is not None:
            parts.append(ANSI_RESET)

        return "".join(parts)

    def _compute_cell(
        self, top: Color | None, bottom: Color | None
    ) -> tuple[str, Color | None, Color | None, bool]:
        """计算单个终端字符单元

        Args中Color均为不透明(已flatten)，None=透明
        Returns: (char, fg, bg, is_fullblock)
        """
        if top is None and bottom is None:
            return (" ", None, None, False)

        if top is not None and bottom is not None and top == bottom:
            return ("█", top, None, True)

        if top is not None and bottom is None:
            return ("▀", top, None, False)

        if top is None and bottom is not None:
            return ("▄", bottom, None, False)

        return ("▀", top, bottom, False)

    def _fg_code(self, color: Color) -> str:
        if self._color_mode == ColorMode.TRUECOLOR:
            return color.fg_truecolor()
        return color.fg_256()

    def _bg_code(self, color: Color) -> str:
        if self._color_mode == ColorMode.TRUECOLOR:
            return color.bg_truecolor()
        return color.bg_256()

    def render_plain(self, buf: PixelBuffer) -> list[str]:
        """Debug接口: 无ANSI纯文本渲染

        有颜色(含半透明)→█，全透明→空格
        """
        lines: list[str] = []
        for y in range(0, buf.height, 2):
            chars: list[str] = []
            for x in range(buf.width):
                top = buf.get_pixel(x, y)
                bottom = buf.get_pixel(x, y + 1) if y + 1 < buf.height else TRANSPARENT
                if top.is_transparent and bottom.is_transparent:
                    chars.append(" ")
                else:
                    chars.append("█")
            lines.append("".join(chars))
        return lines

    def render_debug(self, buf: PixelBuffer) -> list[str]:
        """Debug接口: 显示半块字符选择逻辑"""
        lines: list[str] = []
        for y in range(0, buf.height, 2):
            chars: list[str] = []
            for x in range(buf.width):
                top_raw = buf.get_pixel(x, y)
                bottom_raw = buf.get_pixel(x, y + 1) if y + 1 < buf.height else TRANSPARENT
                top = self._flatten_pixel(top_raw)
                bottom = self._flatten_pixel(bottom_raw)
                if top is None and bottom is None:
                    chars.append(" ")
                elif top is not None and bottom is not None and top == bottom:
                    chars.append("█")
                elif top is not None and bottom is None:
                    chars.append("▀")
                elif top is None and bottom is not None:
                    chars.append("▄")
                else:
                    chars.append("▀")
            lines.append("".join(chars))
        return lines
