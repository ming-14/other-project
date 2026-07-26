"""MoveEngine单元测试"""

from src.engine.direction import Direction
from src.engine.map_engine import MapEngine
from src.engine.move_engine import MoveEngine, MoveType
from src.engine.position import Position


SIMPLE_LEVEL = [
    "######",
    "#.@$ #",
    "######",
]

CORRIDOR_LEVEL = [
    "#######",
    "#  .$ #",
    "#  @  #",
    "#     #",
    "#######",
]

WALL_LEVEL = [
    "######",
    "#@$. #",
    "######",
]


class TestMoveEngineMove:
    def test_move_to_floor(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = MoveEngine()
        result = engine.move(game_map, Direction.LEFT)
        assert result.success is True
        assert result.move_type == MoveType.MOVE
        assert game_map.player == Position(1, 1)

    def test_move_into_wall(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = MoveEngine()
        result = engine.move(game_map, Direction.UP)
        assert result.success is False
        assert result.move_type is None
        assert game_map.player == Position(1, 2)

    def test_push_box(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = MoveEngine()
        result = engine.move(game_map, Direction.RIGHT)
        assert result.success is True
        assert result.move_type == MoveType.PUSH
        assert result.box_new_pos == Position(1, 4)
        assert game_map.player == Position(1, 3)
        assert game_map.has_box(Position(1, 4)) is True
        assert game_map.has_box(Position(1, 3)) is False

    def test_push_box_into_wall(self):
        level = [
            "######",
            "#@$# #",
            "######",
        ]
        game_map = MapEngine.parse(level)
        engine = MoveEngine()
        result = engine.move(game_map, Direction.RIGHT)
        assert result.success is False

    def test_push_box_into_box(self):
        level = [
            "#######",
            "#@$$. #",
            "#######",
        ]
        game_map = MapEngine.parse(level)
        engine = MoveEngine()
        result = engine.move(game_map, Direction.RIGHT)
        assert result.success is False
        assert game_map.player == Position(1, 1)

    def test_move_left_right(self):
        game_map = MapEngine.parse(CORRIDOR_LEVEL)
        engine = MoveEngine()
        result = engine.move(game_map, Direction.LEFT)
        assert result.success is True
        result2 = engine.move(game_map, Direction.RIGHT)
        assert result2.success is True

    def test_try_move_no_modify(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = MoveEngine()
        result = engine.try_move(game_map, Direction.RIGHT)
        assert result.success is True
        assert game_map.player == Position(1, 2)
        assert game_map.has_box(Position(1, 3)) is True

    def test_execute_move_after_try(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = MoveEngine()
        result = engine.try_move(game_map, Direction.RIGHT)
        engine.execute_move(game_map, result)
        assert game_map.player == Position(1, 3)
        assert game_map.has_box(Position(1, 4)) is True

    def test_move_down(self):
        game_map = MapEngine.parse(CORRIDOR_LEVEL)
        engine = MoveEngine()
        result = engine.move(game_map, Direction.DOWN)
        assert result.success is True
        assert game_map.player == Position(3, 3)

    def test_push_box_onto_target(self):
        level = [
            "######",
            "# @$.#",
            "######",
        ]
        game_map = MapEngine.parse(level)
        engine = MoveEngine()
        result = engine.move(game_map, Direction.RIGHT)
        assert result.success is True
        assert result.move_type == MoveType.PUSH
        assert result.box_new_pos == Position(1, 4)
        assert Position(1, 4) in game_map.targets

    def test_move_out_of_bounds(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        engine = MoveEngine()
        game_map.player = Position(0, 0)
        result = engine.move(game_map, Direction.UP)
        assert result.success is False
