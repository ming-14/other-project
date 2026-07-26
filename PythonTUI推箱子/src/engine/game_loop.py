"""GameLoop - 游戏主循环与状态管理"""

from __future__ import annotations

import enum
import logging
import time

from .data.levels import get_level, level_count
from .domain.direction import Direction
from .domain.map import GameMap
from .io.input_engine import InputAction, InputEngine
from .io.terminal_info import TerminalInfo
from .logic.map_engine import MapEngine
from .logic.move_engine import MoveEngine, MoveType
from .logic.win_engine import WinEngine
from .render.layout_engine import LayoutEngine

logger = logging.getLogger(__name__)


class GameState(enum.Enum):
    PLAYING = "playing"
    WON = "won"
    ALL_CLEAR = "all_clear"
    QUIT = "quit"


class GameLoop:
    """游戏主循环：输入→逻辑→渲染"""

    def __init__(self, use_color: bool = True) -> None:
        self._input = InputEngine()
        self._move = MoveEngine()
        self._win = WinEngine()
        self._layout = LayoutEngine(use_color=use_color)
        self._terminal = TerminalInfo()
        self._state = GameState.PLAYING
        self._level_index = 0
        self._game_map: GameMap | None = None
        self._steps = 0
        self._pushes = 0
        self._undo_stack: list[tuple[GameMap, int, int]] = []
        self._use_color = use_color

    @property
    def state(self) -> GameState:
        return self._state

    @property
    def level_index(self) -> int:
        return self._level_index

    @property
    def steps(self) -> int:
        return self._steps

    @property
    def pushes(self) -> int:
        return self._pushes

    def load_level(self, index: int) -> None:
        level_data = get_level(index)
        self._game_map = MapEngine.parse(level_data)
        self._level_index = index
        self._steps = 0
        self._pushes = 0
        self._undo_stack.clear()
        self._state = GameState.PLAYING
        if self._layout.buffer:
            self._layout.buffer.request_full_redraw()
        logger.info("加载关卡 %d", index + 1)

    def restart(self) -> None:
        self.load_level(self._level_index)

    def next_level(self) -> bool:
        next_idx = self._level_index + 1
        if next_idx < level_count():
            self.load_level(next_idx)
            return True
        self._state = GameState.ALL_CLEAR
        return False

    def _save_undo(self) -> None:
        if self._game_map:
            self._undo_stack.append((self._game_map.deep_copy(), self._steps, self._pushes))
            if len(self._undo_stack) > 1000:
                self._undo_stack.pop(0)

    def undo(self) -> None:
        if self._undo_stack:
            self._game_map, self._steps, self._pushes = self._undo_stack.pop()
            logger.debug("撤销: 步数=%d 推箱=%d", self._steps, self._pushes)

    def _action_to_direction(self, action: InputAction) -> Direction | None:
        mapping = {
            InputAction.MOVE_UP: Direction.UP,
            InputAction.MOVE_DOWN: Direction.DOWN,
            InputAction.MOVE_LEFT: Direction.LEFT,
            InputAction.MOVE_RIGHT: Direction.RIGHT,
        }
        return mapping.get(action)

    def process_action(self, action: InputAction) -> None:
        if action == InputAction.NONE:
            return

        if action == InputAction.QUIT:
            self._state = GameState.QUIT
            return

        if action == InputAction.RESTART:
            self.restart()
            return

        if action == InputAction.UNDO:
            self.undo()
            return

        if self._state != GameState.PLAYING:
            if action in (InputAction.MOVE_UP, InputAction.MOVE_DOWN,
                          InputAction.MOVE_LEFT, InputAction.MOVE_RIGHT):
                if self._state == GameState.WON:
                    self.next_level()
            return

        direction = self._action_to_direction(action)
        if direction is None or self._game_map is None:
            return

        self._save_undo()
        result = self._move.move(self._game_map, direction)

        if result.success:
            self._steps += 1
            if result.move_type == MoveType.PUSH:
                self._pushes += 1

            win_result = self._win.check(self._game_map)
            if win_result.won:
                self._state = GameState.WON
                logger.info("关卡 %d 通关! 步数=%d 推箱=%d",
                            self._level_index + 1, self._steps, self._pushes)

    def render(self) -> None:
        if self._game_map is None:
            return

        state_str = self._state.value
        self._layout.render(
            self._game_map, self._level_index, level_count(),
            self._steps, self._pushes, state=state_str
        )
        self._layout.flush()

    def run(self) -> None:
        """主循环入口"""
        self._layout.init(self._terminal.rows, self._terminal.cols)
        self._layout.init_screen()
        self.load_level(0)

        try:
            while self._state != GameState.QUIT:
                if self._terminal.poll():
                    self._layout.resize(self._terminal.rows, self._terminal.cols)
                    self._layout.buffer.init_screen()

                self.render()
                action = self._input.read_action()
                self.process_action(action)
                time.sleep(0.03)
        except KeyboardInterrupt:
            logger.info("用户中断游戏")
        finally:
            self._layout.restore_screen()
