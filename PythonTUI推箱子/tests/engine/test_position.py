"""Position单元测试"""

from src.engine.position import Position


class TestPosition:
    def test_creation(self):
        p = Position(3, 5)
        assert p.row == 3
        assert p.col == 5

    def test_frozen(self):
        p = Position(1, 2)
        try:
            p.row = 99
            assert False, "应不可修改"
        except AttributeError:
            pass

    def test_add(self):
        a = Position(1, 2)
        b = Position(3, 4)
        result = a + b
        assert result == Position(4, 6)

    def test_sub(self):
        a = Position(5, 7)
        b = Position(2, 3)
        result = a - b
        assert result == Position(3, 4)

    def test_neg(self):
        p = Position(3, -5)
        assert -p == Position(-3, 5)

    def test_is_valid(self):
        p = Position(2, 3)
        assert p.is_valid(5, 5) is True
        assert p.is_valid(2, 5) is False
        assert p.is_valid(5, 3) is False
        assert Position(-1, 0).is_valid(5, 5) is False
        assert Position(0, -1).is_valid(5, 5) is False

    def test_equality(self):
        assert Position(1, 2) == Position(1, 2)
        assert Position(1, 2) != Position(2, 1)

    def test_hashable(self):
        s = {Position(1, 2), Position(1, 2), Position(3, 4)}
        assert len(s) == 2
