"""InputEngine单元测试"""

from src.engine.input_engine import InputEngine, InputAction


class TestInputAction:
    def test_action_values(self):
        assert InputAction.MOVE_UP.value == "move_up"
        assert InputAction.MOVE_DOWN.value == "move_down"
        assert InputAction.MOVE_LEFT.value == "move_left"
        assert InputAction.MOVE_RIGHT.value == "move_right"
        assert InputAction.RESTART.value == "restart"
        assert InputAction.QUIT.value == "quit"
        assert InputAction.UNDO.value == "undo"
        assert InputAction.HELP.value == "help"
        assert InputAction.NONE.value == "none"


class TestInputEngine:
    def test_creation(self):
        engine = InputEngine()
        assert engine.history == []

    def test_debug_last_input_empty(self):
        engine = InputEngine()
        info = engine.debug_last_input()
        assert info["last_action"] is None
        assert info["history_count"] == 0

    def test_key_map_has_directions(self):
        engine = InputEngine()
        actions = set(engine._KEY_MAP.values())
        assert InputAction.MOVE_UP in actions
        assert InputAction.MOVE_DOWN in actions
        assert InputAction.MOVE_LEFT in actions
        assert InputAction.MOVE_RIGHT in actions

    def test_key_map_has_functions(self):
        engine = InputEngine()
        actions = set(engine._KEY_MAP.values())
        assert InputAction.RESTART in actions
        assert InputAction.QUIT in actions
        assert InputAction.UNDO in actions
        assert InputAction.HELP in actions

    def test_wasd_mapped(self):
        engine = InputEngine()
        assert engine._KEY_MAP.get(b"w") == InputAction.MOVE_UP
        assert engine._KEY_MAP.get(b"s") == InputAction.MOVE_DOWN
        assert engine._KEY_MAP.get(b"a") == InputAction.MOVE_LEFT
        assert engine._KEY_MAP.get(b"d") == InputAction.MOVE_RIGHT

    def test_function_keys_mapped(self):
        engine = InputEngine()
        assert engine._KEY_MAP.get(b"r") == InputAction.RESTART
        assert engine._KEY_MAP.get(b"q") == InputAction.QUIT
        assert engine._KEY_MAP.get(b"z") == InputAction.UNDO
