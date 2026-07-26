"""MoveEngine - 移动与碰撞引擎"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

from ..domain.direction import Direction
from ..domain.map import GameMap
from ..domain.position import Position
from ..domain.tile import TileType

logger = logging.getLogger(__name__)


class MoveType(Enum):
    MOVE = "move"
    PUSH = "push"


@dataclass(frozen=True, slots=True)
class MoveResult:
    success: bool
    move_type: MoveType | None
    direction: Direction
    box_new_pos: Position | None = None


class MoveEngine:
    """移动引擎：处理玩家移动和推箱子逻辑"""

    def try_move(self, game_map: GameMap, direction: Direction) -> MoveResult:
        """尝试向指定方向移动，返回移动结果但不修改地图"""
        player_pos = game_map.player
        next_pos = player_pos + direction.offset

        if not game_map.is_valid_position(next_pos):
            logger.debug("移动失败: 位置越界 %s", next_pos)
            return MoveResult(success=False, move_type=None, direction=direction)

        next_tile = game_map.get_tile(next_pos)

        # 前方是墙
        if next_tile.is_wall:
            logger.debug("移动失败: 前方是墙 %s", next_pos)
            return MoveResult(success=False, move_type=None, direction=direction)

        # 前方有箱子
        if game_map.has_box(next_pos):
            return self._try_push(game_map, direction, player_pos, next_pos)

        # 前方是空地/目标点，直接移动
        if next_tile.is_walkable:
            logger.debug("移动成功: %s -> %s", player_pos, next_pos)
            return MoveResult(success=True, move_type=MoveType.MOVE, direction=direction)

        logger.debug("移动失败: 未知情况 %s tile=%s", next_pos, next_tile)
        return MoveResult(success=False, move_type=None, direction=direction)

    def execute_move(self, game_map: GameMap, result: MoveResult) -> None:
        """根据移动结果修改地图状态"""
        if not result.success:
            return

        old_player = game_map.player
        new_player = old_player + result.direction.offset

        if result.move_type == MoveType.PUSH and result.box_new_pos is not None:
            box_pos = new_player
            game_map.move_box(box_pos, result.box_new_pos)
            logger.debug("推箱子: %s -> %s", box_pos, result.box_new_pos)

        game_map.player = new_player
        logger.debug("玩家移动: %s -> %s", old_player, new_player)

    def move(self, game_map: GameMap, direction: Direction) -> MoveResult:
        """尝试移动并执行，返回移动结果"""
        result = self.try_move(game_map, direction)
        self.execute_move(game_map, result)
        return result

    def _try_push(self, game_map: GameMap, direction: Direction,
                  player_pos: Position, box_pos: Position) -> MoveResult:
        """尝试推箱子"""
        box_new_pos = box_pos + direction.offset

        if not game_map.is_valid_position(box_new_pos):
            logger.debug("推箱子失败: 箱子目标越界 %s", box_new_pos)
            return MoveResult(success=False, move_type=None, direction=direction)

        box_new_tile = game_map.get_tile(box_new_pos)

        if not box_new_tile.is_walkable or game_map.has_box(box_new_pos):
            logger.debug("推箱子失败: 箱子前方不可通行 %s tile=%s has_box=%s",
                         box_new_pos, box_new_tile, game_map.has_box(box_new_pos))
            return MoveResult(success=False, move_type=None, direction=direction)

        logger.debug("推箱子成功: %s -> %s", box_pos, box_new_pos)
        return MoveResult(success=True, move_type=MoveType.PUSH,
                          direction=direction, box_new_pos=box_new_pos)
