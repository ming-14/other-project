"""TileRenderer - 单宽地图渲染器，每格1列宽"""

from dataclasses import dataclass

from ..domain.tile import TileType


@dataclass(frozen=True, slots=True)
class TileStyle:
    char: str
    fg: str
    bg: str = ""


COLOR_STYLES: dict[TileType, TileStyle] = {
    TileType.WALL:             TileStyle("█", "\033[97;100m"),
    TileType.FLOOR:            TileStyle("·", "\033[90m"),
    TileType.TARGET:           TileStyle("○", "\033[91m"),
    TileType.BOX:              TileStyle("□", "\033[93m"),
    TileType.BOX_ON_TARGET:    TileStyle("★", "\033[92m"),
    TileType.PLAYER:           TileStyle("♦", "\033[96m"),
    TileType.PLAYER_ON_TARGET: TileStyle("♦", "\033[96m"),
}

PLAIN_STYLES: dict[TileType, TileStyle] = {
    TileType.WALL:             TileStyle("#", ""),
    TileType.FLOOR:            TileStyle(" ", ""),
    TileType.TARGET:           TileStyle(".", ""),
    TileType.BOX:              TileStyle("$", ""),
    TileType.BOX_ON_TARGET:    TileStyle("*", ""),
    TileType.PLAYER:           TileStyle("@", ""),
    TileType.PLAYER_ON_TARGET: TileStyle("+", ""),
}

ANSI_RESET = "\033[0m"


class TileRenderer:
    """单宽渲染器：每个TileType渲染为1列宽字符串"""

    def __init__(self, styles: dict[TileType, TileStyle] | None = None) -> None:
        self._styles = styles or COLOR_STYLES

    def render(self, tile: TileType, use_color: bool = True) -> str:
        style = self._styles.get(tile, TileStyle("?", ""))
        if use_color and style.fg:
            return f"{style.fg}{style.char}{ANSI_RESET}"
        return style.char

    def render_plain(self, tile: TileType) -> str:
        style = self._styles.get(tile, TileStyle("?", ""))
        return style.char

    def char_width(self) -> int:
        return 1
