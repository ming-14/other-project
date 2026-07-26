"""WinEngine单元测试"""

from src.engine.map_engine import MapEngine
from src.engine.win_engine import WinEngine


class TestWinEngine:
    def test_not_won_initial(self):
        level = [
            "######",
            "#.@$ #",
            "######",
        ]
        game_map = MapEngine.parse(level)
        result = WinEngine.check(game_map)
        assert result.won is False
        assert result.total_targets == 1
        assert result.covered_targets == 0

    def test_won_all_on_target(self):
        level = [
            "######",
            "# *  #",
            "#  @ #",
            "######",
        ]
        game_map = MapEngine.parse(level)
        result = WinEngine.check(game_map)
        assert result.won is True
        assert result.total_targets == 1
        assert result.covered_targets == 1

    def test_partial_covered(self):
        level = [
            "#######",
            "# *$. #",
            "#  @  #",
            "#######",
        ]
        game_map = MapEngine.parse(level)
        result = WinEngine.check(game_map)
        assert result.won is False
        assert result.total_targets == 2
        assert result.covered_targets == 1

    def test_no_targets(self):
        from src.engine.map import GameMap
        from src.engine.position import Position
        m = GameMap(3, 3)
        m.player = Position(1, 1)
        m.targets = frozenset()
        result = WinEngine.check(m)
        assert result.won is False
        assert result.total_targets == 0
