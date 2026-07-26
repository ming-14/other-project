"""WinEngine - 胜利判定引擎"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..domain.map import GameMap

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class WinCheckResult:
    won: bool
    total_targets: int
    covered_targets: int


class WinEngine:
    """胜利判定引擎：检查所有目标点是否都有箱子"""

    @staticmethod
    def check(game_map: GameMap) -> WinCheckResult:
        targets = game_map.targets
        boxes = game_map.boxes
        total = len(targets)
        covered = len(targets & boxes)
        won = total > 0 and covered == total
        if won:
            logger.info("胜利! %d/%d 目标点已覆盖", covered, total)
        return WinCheckResult(won=won, total_targets=total, covered_targets=covered)
