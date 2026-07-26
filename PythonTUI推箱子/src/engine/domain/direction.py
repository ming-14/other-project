"""Direction - 方向枚举与偏移量映射"""

from __future__ import annotations

import enum

from .position import Position


class Direction(enum.Enum):
    """四方向枚举，值对应Position偏移量"""

    UP = Position(-1, 0)
    DOWN = Position(1, 0)
    LEFT = Position(0, -1)
    RIGHT = Position(0, 1)

    @property
    def offset(self) -> Position:
        return self.value

    @property
    def opposite(self) -> Direction:
        opposites = {
            Direction.UP: Direction.DOWN,
            Direction.DOWN: Direction.UP,
            Direction.LEFT: Direction.RIGHT,
            Direction.RIGHT: Direction.LEFT,
        }
        return opposites[self]
