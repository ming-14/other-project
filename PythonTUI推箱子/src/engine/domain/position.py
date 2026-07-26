"""Position - 二维坐标值对象，不可变"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass(frozen=True, slots=True)
class Position:
    """不可变二维坐标 (row, col)，row向下为正，col向右为正"""

    row: int
    col: int

    def __add__(self, other: Position) -> Position:
        return Position(self.row + other.row, self.col + other.col)

    def __sub__(self, other: Position) -> Position:
        return Position(self.row - other.row, self.col - other.col)

    def __neg__(self) -> Position:
        return Position(-self.row, -self.col)

    def __repr__(self) -> str:
        return f"Pos({self.row},{self.col})"

    def is_valid(self, max_row: int, max_col: int) -> bool:
        """检查坐标是否在 [0, max_row) x [0, max_col) 范围内"""
        return 0 <= self.row < max_row and 0 <= self.col < max_col
