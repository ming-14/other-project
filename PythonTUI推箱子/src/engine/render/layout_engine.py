"""LayoutEngine - 全屏布局引擎，构建完整带ANSI的字符串行"""

import logging
import re

from src.tui_pixel.color import Color
from src.tui_pixel.pixel_buffer import PixelBuffer
from src.tui_pixel.renderer import HalfBlockRenderer, ColorMode
from src.tui_pixel.sprites.sokoban import (
    SPRITE_WALL, SPRITE_FLOOR, SPRITE_TARGET,
    SPRITE_BOX, SPRITE_BOX_ON_TARGET,
    SPRITE_PLAYER, SPRITE_PLAYER_ON_TARGET,
    FLOOR_COLOR,
)
from ..domain.map import GameMap
from ..domain.position import Position
from ..domain.tile import TileType
from .screen_buffer import ScreenBuffer

logger = logging.getLogger(__name__)

_ANSI_RE = re.compile(r'\033\[[0-9;]*[mKHJ]')


def _visible_len(s: str) -> int:
    """计算字符串可见宽度（去除ANSI转义码后的长度）"""
    return len(_ANSI_RE.sub('', s))

FG_TITLE = "\033[97;1m"
FG_SUBTITLE = "\033[37m"
FG_BORDER = "\033[90m"
FG_STATUS = "\033[97m"
FG_STATUS_KEY = "\033[93m"
FG_WIN = "\033[92;1m"
RST = "\033[0m"

BOX_TL = "┌"
BOX_TR = "┐"
BOX_BL = "└"
BOX_BR = "┘"
BOX_H = "─"
BOX_V = "│"


class LayoutEngine:
    """全屏布局引擎：构建带ANSI颜色的完整行，写入ScreenBuffer"""

    _TILE_SPRITES = {
        TileType.WALL: SPRITE_WALL,
        TileType.FLOOR: SPRITE_FLOOR,
        TileType.TARGET: SPRITE_TARGET,
        TileType.BOX: SPRITE_BOX,
        TileType.BOX_ON_TARGET: SPRITE_BOX_ON_TARGET,
        TileType.PLAYER: SPRITE_PLAYER,
        TileType.PLAYER_ON_TARGET: SPRITE_PLAYER_ON_TARGET,
    }

    SPRITE_SIZE = 16

    def __init__(self, use_color: bool = True) -> None:
        self._use_color = use_color
        color_mode = ColorMode.TRUECOLOR if use_color else ColorMode.ANSI256
        self._pixel_renderer = HalfBlockRenderer(color_mode, bg_color=FLOOR_COLOR)
        self._buffer: ScreenBuffer | None = None
        self._term_cols = 0
        self._term_rows = 0

    def init(self, term_rows: int, term_cols: int) -> ScreenBuffer:
        self._term_rows = term_rows
        self._term_cols = term_cols
        self._buffer = ScreenBuffer(term_rows, term_cols)
        return self._buffer

    def resize(self, term_rows: int, term_cols: int) -> None:
        if self._buffer:
            self._buffer.resize(term_rows, term_cols)
            self._term_rows = term_rows
            self._term_cols = term_cols

    @property
    def buffer(self) -> ScreenBuffer | None:
        return self._buffer

    def render(self, game_map: GameMap, level_index: int, total_levels: int,
               steps: int, pushes: int, state: str = "playing") -> None:
        if self._buffer is None:
            return

        self._buffer.clear_back()

        title_row = 0
        border_top = 1
        status_row = self._term_rows - 1
        map_area_top = border_top + 1
        map_area_bottom = status_row

        self._buffer.set_row(title_row, self._build_title(level_index, total_levels))
        self._buffer.set_row(border_top, self._build_h_border(BOX_TL, BOX_TR))
        self._buffer.set_row(status_row, self._build_h_border(BOX_BL, BOX_BR))

        self._draw_map_area(game_map, map_area_top, map_area_bottom)
        self._draw_status(status_row, steps, pushes, state)

        if state == "all_clear":
            self._draw_all_clear_overlay()

    def _build_title(self, level_index: int, total_levels: int) -> str:
        c = self._use_color
        title = f"{' ' + FG_TITLE if c else ' '}SOKOBAN{RST + ' ' if c else ' '}"
        level_text = f"{' ' + FG_SUBTITLE if c else ' '}Level {level_index + 1}/{total_levels}{RST + ' ' if c else ' '}"
        pad = self._term_cols - len(" SOKOBAN ") - len(f" Level {level_index + 1}/{total_levels} ")
        return title + " " * max(1, pad) + level_text

    def _build_h_border(self, left: str, right: str) -> str:
        c = self._use_color
        inner = BOX_H * (self._term_cols - 2)
        fg = FG_BORDER if c else ""
        rst = RST if c else ""
        return f"{fg}{left}{inner}{right}{rst}"

    def _build_v_border_row(self, content: str) -> str:
        c = self._use_color
        fg = FG_BORDER if c else ""
        rst = RST if c else ""
        return f"{fg}{BOX_V}{rst}{content}{fg}{BOX_V}{rst}"

    def _draw_map_area(self, game_map: GameMap, area_top: int, area_bottom: int) -> None:
        s = self.SPRITE_SIZE
        map_pixel_w = game_map.cols * s
        map_pixel_h = game_map.rows * s

        buf = PixelBuffer(map_pixel_w, map_pixel_h)
        buf.fill(FLOOR_COLOR)
        for r in range(game_map.rows):
            for c in range(game_map.cols):
                pos = Position(r, c)
                if pos == game_map.player:
                    tile = TileType.PLAYER_ON_TARGET if pos in game_map.targets else TileType.PLAYER
                elif game_map.has_box(pos):
                    tile = TileType.BOX_ON_TARGET if pos in game_map.targets else TileType.BOX
                else:
                    tile = game_map.get_tile(pos)
                sprite = self._TILE_SPRITES.get(tile, SPRITE_FLOOR)
                buf.blit(sprite.data, c * s, r * s)

        ansi_lines = self._pixel_renderer.render(buf)
        term_map_rows = len(ansi_lines)

        area_rows = area_bottom - area_top
        area_cols = self._term_cols - 2

        start_offset_r = max(0, (area_rows - term_map_rows) // 2)
        start_offset_c = max(0, (area_cols - map_pixel_w) // 2)

        for r in range(area_top, area_bottom):
            buf_row_idx = r - area_top
            map_r = buf_row_idx - start_offset_r

            if 0 <= map_r < term_map_rows:
                left_pad = " " * start_offset_c
                right_pad_len = area_cols - start_offset_c - map_pixel_w
                right_pad = " " * max(0, right_pad_len)
                content = left_pad + ansi_lines[map_r] + right_pad
            else:
                content = " " * area_cols

            self._buffer.set_row(r, self._build_v_border_row(content))

    def _draw_status(self, row: int, steps: int, pushes: int, state: str) -> None:
        c = self._use_color
        fg = FG_STATUS if c else ""
        fgk = FG_STATUS_KEY if c else ""
        rst = RST if c else ""

        left = f" {fg}Steps:{steps}  Pushes:{pushes}{rst}"

        if state == "playing":
            right = f"{fgk}Arrows/WASD{rst}{fg}:Move  {fgk}R{rst}{fg}:Restart  {fgk}Z{rst}{fg}:Undo  {fgk}Q{rst}{fg}:Quit{rst}"
        elif state == "won":
            right = f"{fg}★ CLEAR! Steps:{steps} Pushes:{pushes} ★{rst}"
        elif state == "all_clear":
            right = f"{fgk}Q{rst}{fg}:Quit{rst}"
        else:
            right = ""

        inner_width = self._term_cols - 2
        right_len_no_ansi = _visible_len(right)
        left_len_no_ansi = _visible_len(left)
        pad_len = max(1, inner_width - left_len_no_ansi - right_len_no_ansi)

        content = left + " " * pad_len + right
        fg_b = FG_BORDER if c else ""
        self._buffer.set_row(row, f"{fg_b}{BOX_V}{rst}{content}{fg_b}{BOX_V}{rst}")

    def _draw_win_overlay(self, game_map: GameMap, steps: int, pushes: int) -> None:
        c = self._use_color
        fg = FG_WIN if c else ""
        rst = RST if c else ""
        text = f"{fg}★ CLEAR! Steps:{steps} Pushes:{pushes} ★{rst}"
        mid_row = self._term_rows // 2 - 1
        current = self._buffer.get_row(mid_row)
        plain_len = _visible_len(text)
        start_col = max(1, (self._term_cols - plain_len) // 2)
        prefix = current[:start_col] if len(current) >= start_col else current + " " * (start_col - len(current))
        self._buffer.set_row(mid_row, prefix + text)

    def _draw_all_clear_overlay(self) -> None:
        c = self._use_color
        fg = FG_WIN if c else ""
        rst = RST if c else ""
        mid_row = self._term_rows // 2
        text1 = f"{fg}★ ALL LEVELS CLEAR! ★{rst}"
        text2 = f"{fg}Congratulations!{rst}"
        for text, row_off in [(text1, 0), (text2, 1)]:
            r = mid_row + row_off
            current = self._buffer.get_row(r)
            plain_len = _visible_len(text)
            start_col = max(1, (self._term_cols - plain_len) // 2)
            prefix = current[:start_col] if len(current) >= start_col else current + " " * (start_col - len(current))
            self._buffer.set_row(r, prefix + text)

    def flush(self) -> int:
        if self._buffer:
            return self._buffer.swap_and_flush()
        return 0

    def full_flush(self) -> None:
        if self._buffer:
            self._buffer.full_flush()

    def init_screen(self) -> None:
        if self._buffer:
            self._buffer.init_screen()

    def restore_screen(self) -> None:
        if self._buffer:
            self._buffer.restore_screen()
