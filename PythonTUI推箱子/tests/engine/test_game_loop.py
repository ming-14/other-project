"""GameLoop单元测试"""

from src.engine.game_loop import GameLoop, GameState
from src.engine.input_engine import InputAction


class TestGameLoop:
    def test_load_level(self):
        game = GameLoop(use_color=False)
        game.load_level(0)
        assert game.state == GameState.PLAYING
        assert game.level_index == 0
        assert game.steps == 0

    def test_restart(self):
        game = GameLoop(use_color=False)
        game.load_level(0)
        game.process_action(InputAction.MOVE_DOWN)
        game.restart()
        assert game.steps == 0
        assert game.state == GameState.PLAYING

    def test_quit(self):
        game = GameLoop(use_color=False)
        game.load_level(0)
        game.process_action(InputAction.QUIT)
        assert game.state == GameState.QUIT

    def test_move_increments_steps(self):
        game = GameLoop(use_color=False)
        game.load_level(1)
        initial_steps = game.steps
        game.process_action(InputAction.MOVE_UP)
        assert game.steps == initial_steps + 1

    def test_wall_does_not_increment_steps(self):
        game = GameLoop(use_color=False)
        game.load_level(0)
        game.process_action(InputAction.MOVE_UP)
        assert game.steps == 0

    def test_undo(self):
        game = GameLoop(use_color=False)
        game.load_level(1)
        game.process_action(InputAction.MOVE_UP)
        assert game.steps == 1
        game.process_action(InputAction.UNDO)
        assert game.steps == 0

    def test_next_level(self):
        game = GameLoop(use_color=False)
        game.load_level(0)
        result = game.next_level()
        assert result is True
        assert game.level_index == 1

    def test_next_level_beyond(self):
        from src.engine.data.levels import level_count
        game = GameLoop(use_color=False)
        game.load_level(level_count() - 1)
        result = game.next_level()
        assert result is False
        assert game.state == GameState.ALL_CLEAR
