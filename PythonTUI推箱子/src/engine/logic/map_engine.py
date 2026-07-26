"""MapEngine - 地图引擎，负责地图的创建、解析、查询、验证"""

from __future__ import annotations

import logging
from typing import Sequence

from ..domain.map import GameMap
from ..domain.position import Position
from ..domain.tile import TileType

logger = logging.getLogger(__name__)


class MapValidationError(Exception):
    """地图验证失败异常"""


class MapEngine:
    """地图引擎：解析、构建、验证地图"""

    @staticmethod
    def parse(level_data: Sequence[str]) -> GameMap:
        """从字符串列表解析地图（标准Sokoban格式）

        行长度不等时以最长行为准，短行右侧补空格。
        地图外空白行会被裁剪。
        """
        trimmed = _trim_level_data(level_data)
        if not trimmed:
            raise MapValidationError("地图数据为空")

        max_col = max(len(line) for line in trimmed)
        rows = len(trimmed)

        game_map = GameMap(rows, max_col)
        boxes: set[Position] = set()
        targets: set[Position] = set()
        player: Position | None = None

        for r, line in enumerate(trimmed):
            for c, ch in enumerate(line):
                tile = TileType.from_char(ch)
                game_map.set_tile(Position(r, c), tile)
                pos = Position(r, c)

                if tile.is_player:
                    player = pos
                    # 底层地块是FLOOR还是TARGET
                    game_map.set_tile(pos, TileType.TARGET if tile == TileType.PLAYER_ON_TARGET else TileType.FLOOR)
                elif tile.is_box:
                    boxes.add(pos)
                    game_map.set_tile(pos, TileType.TARGET if tile == TileType.BOX_ON_TARGET else TileType.FLOOR)

                if tile.is_target:
                    targets.add(pos)

        if player is None:
            raise MapValidationError("地图中没有玩家")
        if len(boxes) < len(targets):
            raise MapValidationError(f"箱子数({len(boxes)})少于目标点数({len(targets)})")

        game_map.player = player
        game_map.boxes = frozenset(boxes)
        game_map.targets = frozenset(targets)

        logger.debug("地图解析完成: %dx%d, player=%s, boxes=%d, targets=%d",
                     rows, max_col, player, len(boxes), len(targets))
        return game_map

    @staticmethod
    def validate(game_map: GameMap) -> None:
        """验证地图合法性，不合法则抛出MapValidationError"""
        if game_map._player is None:
            raise MapValidationError("地图中没有玩家")
        if len(game_map.boxes) < len(game_map.targets):
            raise MapValidationError("箱子数少于目标点数")
        if not game_map.targets:
            raise MapValidationError("地图中没有目标点")
        logger.debug("地图验证通过")

    @staticmethod
    def debug_dump(game_map: GameMap) -> str:
        """Debug接口：导出地图完整状态为字符串"""
        lines = game_map.to_string_list()
        header = f"Map: {game_map.rows}x{game_map.cols}"
        player_line = f"Player: {game_map.player}"
        boxes_line = f"Boxes({len(game_map.boxes)}): {sorted(game_map.boxes, key=lambda p: (p.row, p.col))}"
        targets_line = f"Targets({len(game_map.targets)}): {sorted(game_map.targets, key=lambda p: (p.row, p.col))}"
        return "\n".join([header, player_line, boxes_line, targets_line, "---"] + lines)


def _trim_level_data(data: Sequence[str]) -> list[str]:
    """裁剪地图数据前后的空行"""
    start = 0
    for i, line in enumerate(data):
        if line.strip():
            start = i
            break
    else:
        return []

    end = len(data)
    for i in range(len(data) - 1, -1, -1):
        if data[i].strip():
            end = i + 1
            break

    return list(data[start:end])
