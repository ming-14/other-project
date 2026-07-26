"""内置关卡数据 - 经典Sokoban关卡"""

from typing import Sequence

BUILTIN_LEVELS: list[list[str]] = [
    [
        "#####",
        "# @ #",
        "# $ #",
        "# . #",
        "#   #",
        "#####",
    ],
    [
        "######",
        "#    #",
        "# .$ #",
        "#  @ #",
        "# .$ #",
        "#    #",
        "######",
    ],
    [
        "######",
        "#    #",
        "# .$ #",
        "# $@.#",
        "#    #",
        "######",
    ],
]


def get_level(index: int) -> Sequence[str]:
    if 0 <= index < len(BUILTIN_LEVELS):
        return BUILTIN_LEVELS[index]
    raise IndexError(f"关卡索引越界: {index}")


def level_count() -> int:
    return len(BUILTIN_LEVELS)
