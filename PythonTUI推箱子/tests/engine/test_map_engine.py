"""MapEngine单元测试"""

from src.engine.map_engine import MapEngine, MapValidationError
from src.engine.position import Position
from src.engine.tile import TileType


SIMPLE_LEVEL = [
    "#####",
    "#.@$#",
    "#####",
]

MULTI_BOX_LEVEL = [
    "######",
    "#.  $#",
    "# $@ #",
    "# .  #",
    "######",
]

PLAYER_ON_TARGET_LEVEL = [
    "#####",
    "#+$#",
    "#  #",
    "#####",
]


class TestMapEngineParse:
    def test_parse_simple(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        assert game_map.rows == 3
        assert game_map.cols == 5
        assert game_map.player == Position(1, 2)
        assert len(game_map.boxes) == 1
        assert Position(1, 3) in game_map.boxes
        assert len(game_map.targets) == 1
        assert Position(1, 1) in game_map.targets

    def test_parse_multi_box(self):
        game_map = MapEngine.parse(MULTI_BOX_LEVEL)
        assert game_map.player == Position(2, 3)
        assert len(game_map.boxes) == 2
        assert len(game_map.targets) == 2

    def test_parse_player_on_target(self):
        game_map = MapEngine.parse(PLAYER_ON_TARGET_LEVEL)
        assert game_map.player == Position(1, 1)
        assert Position(1, 1) in game_map.targets
        assert len(game_map.boxes) == 1
        assert Position(1, 2) in game_map.boxes

    def test_parse_empty_raises(self):
        try:
            MapEngine.parse([])
            assert False, "应抛出MapValidationError"
        except MapValidationError:
            pass

    def test_parse_no_player_raises(self):
        try:
            MapEngine.parse(["#####", "# $ #", "#####"])
            assert False, "应抛出MapValidationError"
        except MapValidationError:
            pass

    def test_parse_boxes_less_than_targets_raises(self):
        try:
            MapEngine.parse(["#####", "#..$#", "#####"])
            assert False, "应抛出MapValidationError"
        except MapValidationError:
            pass

    def test_parse_box_on_target(self):
        level = [
            "#####",
            "#*$.#",
            "#  @#",
            "#####",
        ]
        game_map = MapEngine.parse(level)
        assert Position(1, 1) in game_map.boxes
        assert Position(1, 1) in game_map.targets
        assert Position(1, 2) in game_map.boxes
        assert Position(1, 3) in game_map.targets
        assert len(game_map.boxes) == 2
        assert len(game_map.targets) == 2

    def test_parse_uneven_rows(self):
        level = [
            "#####",
            "#.@$#",
            "###",
        ]
        game_map = MapEngine.parse(level)
        assert game_map.cols == 5

    def test_parse_trims_blank_lines(self):
        level = [
            "",
            "  ",
            "#####",
            "#.@$#",
            "#####",
            "",
        ]
        game_map = MapEngine.parse(level)
        assert game_map.rows == 3


class TestMapEngineValidate:
    def test_validate_ok(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        MapEngine.validate(game_map)

    def test_validate_no_player(self):
        from src.engine.map import GameMap
        m = GameMap(3, 3)
        m.targets = frozenset({Position(1, 1)})
        try:
            MapEngine.validate(m)
            assert False, "应抛出MapValidationError"
        except MapValidationError:
            pass


class TestMapEngineDebug:
    def test_debug_dump(self):
        game_map = MapEngine.parse(SIMPLE_LEVEL)
        dump = MapEngine.debug_dump(game_map)
        assert "3x5" in dump
        assert "Player" in dump
        assert "Boxes" in dump
        assert "Targets" in dump
