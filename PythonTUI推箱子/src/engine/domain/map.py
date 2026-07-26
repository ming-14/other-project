"""GameMap - 推箱子游戏地图数据结构"""

from __future__ import annotations

import copy
from typing import Sequence

from .position import Position
from .tile import TileType


class GameMap:
    """推箱子游戏地图，存储网格数据和实体位置"""

    def __init__(self, rows: int, cols: int) -> None:
        self._rows = rows
        self._cols = cols
        self._grid: list[list[TileType]] = [
            [TileType.FLOOR] * cols for _ in range(rows)
        ]
        self._player: Position | None = None
        self._boxes: set[Position] = set()
        self._targets: frozenset[Position] = frozenset()

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def player(self) -> Position:
        if self._player is None:
            raise ValueError("地图中没有玩家")
        return self._player

    @player.setter
    def player(self, pos: Position) -> None:
        self._player = pos

    @property
    def boxes(self) -> frozenset[Position]:
        return frozenset(self._boxes)

    @boxes.setter
    def boxes(self, value: frozenset[Position]) -> None:
        self._boxes = set(value)

    @property
    def targets(self) -> frozenset[Position]:
        return self._targets

    @targets.setter
    def targets(self, value: frozenset[Position]) -> None:
        self._targets = value

    def get_tile(self, pos: Position) -> TileType:
        if not pos.is_valid(self._rows, self._cols):
            return TileType.WALL
        return self._grid[pos.row][pos.col]

    def set_tile(self, pos: Position, tile: TileType) -> None:
        if pos.is_valid(self._rows, self._cols):
            self._grid[pos.row][pos.col] = tile

    def add_box(self, pos: Position) -> None:
        self._boxes.add(pos)

    def remove_box(self, pos: Position) -> None:
        self._boxes.discard(pos)

    def has_box(self, pos: Position) -> bool:
        return pos in self._boxes

    def move_box(self, old: Position, new: Position) -> None:
        self._boxes.discard(old)
        self._boxes.add(new)

    def is_valid_position(self, pos: Position) -> bool:
        return pos.is_valid(self._rows, self._cols)

    def deep_copy(self) -> GameMap:
        return copy.deepcopy(self)

    def to_string_list(self) -> list[str]:
        """将地图导出为字符串列表（debug接口）"""
        lines: list[str] = []
        for r in range(self._rows):
            line = "".join(self._grid[r][c].value for c in range(self._cols))
            lines.append(line.rstrip())
        return lines

    def __repr__(self) -> str:
        return f"GameMap({self._rows}x{self._cols}, player={self._player}, boxes={len(self._boxes)}, targets={len(self._targets)})"
