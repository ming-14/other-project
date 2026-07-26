"""TileType单元测试"""

from src.engine.tile import TileType


class TestTileType:
    def test_from_char(self):
        assert TileType.from_char("#") == TileType.WALL
        assert TileType.from_char(" ") == TileType.FLOOR
        assert TileType.from_char(".") == TileType.TARGET
        assert TileType.from_char("$") == TileType.BOX
        assert TileType.from_char("*") == TileType.BOX_ON_TARGET
        assert TileType.from_char("@") == TileType.PLAYER
        assert TileType.from_char("+") == TileType.PLAYER_ON_TARGET

    def test_from_char_unknown(self):
        assert TileType.from_char("X") == TileType.FLOOR
        assert TileType.from_char("") == TileType.FLOOR

    def test_is_box(self):
        assert TileType.BOX.is_box is True
        assert TileType.BOX_ON_TARGET.is_box is True
        assert TileType.WALL.is_box is False
        assert TileType.FLOOR.is_box is False

    def test_is_target(self):
        assert TileType.TARGET.is_target is True
        assert TileType.BOX_ON_TARGET.is_target is True
        assert TileType.PLAYER_ON_TARGET.is_target is True
        assert TileType.FLOOR.is_target is False

    def test_is_player(self):
        assert TileType.PLAYER.is_player is True
        assert TileType.PLAYER_ON_TARGET.is_player is True
        assert TileType.BOX.is_player is False

    def test_is_walkable(self):
        assert TileType.FLOOR.is_walkable is True
        assert TileType.TARGET.is_walkable is True
        assert TileType.WALL.is_walkable is False
        assert TileType.BOX.is_walkable is False

    def test_is_wall(self):
        assert TileType.WALL.is_wall is True
        assert TileType.FLOOR.is_wall is False
