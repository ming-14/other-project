"""GameMap单元测试"""

from src.engine.map import GameMap
from src.engine.position import Position
from src.engine.tile import TileType


class TestGameMap:
    def test_creation(self):
        m = GameMap(5, 3)
        assert m.rows == 5
        assert m.cols == 3
        assert m.get_tile(Position(0, 0)) == TileType.FLOOR

    def test_set_get_tile(self):
        m = GameMap(3, 3)
        m.set_tile(Position(1, 1), TileType.WALL)
        assert m.get_tile(Position(1, 1)) == TileType.WALL

    def test_out_of_bounds_returns_wall(self):
        m = GameMap(3, 3)
        assert m.get_tile(Position(-1, 0)) == TileType.WALL
        assert m.get_tile(Position(3, 0)) == TileType.WALL
        assert m.get_tile(Position(0, 3)) == TileType.WALL

    def test_player(self):
        m = GameMap(3, 3)
        m.player = Position(1, 1)
        assert m.player == Position(1, 1)

    def test_player_none_raises(self):
        m = GameMap(3, 3)
        try:
            _ = m.player
            assert False, "应抛出ValueError"
        except ValueError:
            pass

    def test_boxes(self):
        m = GameMap(5, 5)
        m.add_box(Position(2, 2))
        m.add_box(Position(3, 3))
        assert m.has_box(Position(2, 2)) is True
        assert m.has_box(Position(0, 0)) is False
        assert len(m.boxes) == 2

    def test_move_box(self):
        m = GameMap(5, 5)
        m.add_box(Position(2, 2))
        m.move_box(Position(2, 2), Position(2, 3))
        assert m.has_box(Position(2, 2)) is False
        assert m.has_box(Position(2, 3)) is True

    def test_remove_box(self):
        m = GameMap(5, 5)
        m.add_box(Position(2, 2))
        m.remove_box(Position(2, 2))
        assert m.has_box(Position(2, 2)) is False

    def test_targets_frozen(self):
        m = GameMap(5, 5)
        m.targets = frozenset({Position(1, 1), Position(2, 2)})
        assert len(m.targets) == 2
        assert isinstance(m.targets, frozenset)

    def test_deep_copy(self):
        m = GameMap(3, 3)
        m.player = Position(1, 1)
        m.add_box(Position(2, 2))
        m2 = m.deep_copy()
        m2.add_box(Position(0, 0))
        assert len(m.boxes) == 1
        assert len(m2.boxes) == 2

    def test_to_string_list(self):
        m = GameMap(2, 3)
        m.set_tile(Position(0, 0), TileType.WALL)
        m.set_tile(Position(0, 1), TileType.WALL)
        m.set_tile(Position(0, 2), TileType.WALL)
        lines = m.to_string_list()
        assert lines[0] == "###"
        assert lines[1] == ""

    def test_is_valid_position(self):
        m = GameMap(3, 3)
        assert m.is_valid_position(Position(0, 0)) is True
        assert m.is_valid_position(Position(3, 0)) is False
