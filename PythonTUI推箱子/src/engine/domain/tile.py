"""TileType - 地块类型枚举"""

from __future__ import annotations

import enum


class TileType(enum.Enum):
    """推箱子地图地块类型，值对应标准Sokoban格式字符"""

    WALL = "#"
    FLOOR = " "
    TARGET = "."
    BOX = "$"
    BOX_ON_TARGET = "*"
    PLAYER = "@"
    PLAYER_ON_TARGET = "+"

    @classmethod
    def from_char(cls, ch: str) -> TileType:
        """从字符解析TileType，未知字符默认为FLOOR"""
        for member in cls:
            if member.value == ch:
                return member
        return cls.FLOOR

    @property
    def is_box(self) -> bool:
        return self in (TileType.BOX, TileType.BOX_ON_TARGET)

    @property
    def is_target(self) -> bool:
        return self in (TileType.TARGET, TileType.BOX_ON_TARGET, TileType.PLAYER_ON_TARGET)

    @property
    def is_player(self) -> bool:
        return self in (TileType.PLAYER, TileType.PLAYER_ON_TARGET)

    @property
    def is_walkable(self) -> bool:
        """玩家/箱子是否可以进入此地块（不含箱子阻挡）"""
        return self in (TileType.FLOOR, TileType.TARGET)

    @property
    def is_wall(self) -> bool:
        return self == TileType.WALL
