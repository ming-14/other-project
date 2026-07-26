"""Direction单元测试"""

from src.engine.direction import Direction
from src.engine.position import Position


class TestDirection:
    def test_offset(self):
        assert Direction.UP.offset == Position(-1, 0)
        assert Direction.DOWN.offset == Position(1, 0)
        assert Direction.LEFT.offset == Position(0, -1)
        assert Direction.RIGHT.offset == Position(0, 1)

    def test_opposite(self):
        assert Direction.UP.opposite == Direction.DOWN
        assert Direction.DOWN.opposite == Direction.UP
        assert Direction.LEFT.opposite == Direction.RIGHT
        assert Direction.RIGHT.opposite == Direction.LEFT

    def test_offset_is_position(self):
        for d in Direction:
            assert isinstance(d.offset, Position)
