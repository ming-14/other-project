"""InputEngine - 键盘输入处理引擎（Windows msvcrt）"""

from __future__ import annotations

import enum
import logging
import sys

logger = logging.getLogger(__name__)


class InputAction(enum.Enum):
    MOVE_UP = "move_up"
    MOVE_DOWN = "move_down"
    MOVE_LEFT = "move_left"
    MOVE_RIGHT = "move_right"
    RESTART = "restart"
    QUIT = "quit"
    UNDO = "undo"
    HELP = "help"
    NONE = "none"


class InputEngine:
    """键盘输入引擎：非阻塞读取，按键映射"""

    _KEY_MAP: dict[bytes | str, InputAction] = {}

    def __init__(self) -> None:
        self._history: list[InputAction] = []
        self._max_history = 100
        self._init_key_map()

    def _init_key_map(self) -> None:
        if sys.platform == "win32":
            self._KEY_MAP = {
                b"\xe0H": InputAction.MOVE_UP,
                b"\xe0P": InputAction.MOVE_DOWN,
                b"\xe0K": InputAction.MOVE_LEFT,
                b"\xe0M": InputAction.MOVE_RIGHT,
                b"H": InputAction.MOVE_UP,
                b"P": InputAction.MOVE_DOWN,
                b"K": InputAction.MOVE_LEFT,
                b"M": InputAction.MOVE_RIGHT,
                b"w": InputAction.MOVE_UP,
                b"W": InputAction.MOVE_UP,
                b"s": InputAction.MOVE_DOWN,
                b"S": InputAction.MOVE_DOWN,
                b"a": InputAction.MOVE_LEFT,
                b"A": InputAction.MOVE_LEFT,
                b"d": InputAction.MOVE_RIGHT,
                b"D": InputAction.MOVE_RIGHT,
                b"r": InputAction.RESTART,
                b"R": InputAction.RESTART,
                b"q": InputAction.QUIT,
                b"Q": InputAction.QUIT,
                b"\x1b": InputAction.QUIT,
                b"z": InputAction.UNDO,
                b"Z": InputAction.UNDO,
                b"h": InputAction.HELP,
                b"H": InputAction.HELP,
            }
        else:
            self._KEY_MAP = {
                b"\x1b[A": InputAction.MOVE_UP,
                b"\x1b[B": InputAction.MOVE_DOWN,
                b"\x1b[D": InputAction.MOVE_LEFT,
                b"\x1b[C": InputAction.MOVE_RIGHT,
                b"w": InputAction.MOVE_UP,
                b"W": InputAction.MOVE_UP,
                b"s": InputAction.MOVE_DOWN,
                b"S": InputAction.MOVE_DOWN,
                b"a": InputAction.MOVE_LEFT,
                b"A": InputAction.MOVE_LEFT,
                b"d": InputAction.MOVE_RIGHT,
                b"D": InputAction.MOVE_RIGHT,
                b"r": InputAction.RESTART,
                b"R": InputAction.RESTART,
                b"q": InputAction.QUIT,
                b"Q": InputAction.QUIT,
                b"\x1b": InputAction.QUIT,
                b"z": InputAction.UNDO,
                b"Z": InputAction.UNDO,
                b"h": InputAction.HELP,
                b"H": InputAction.HELP,
            }

    def read_action(self) -> InputAction:
        """非阻塞读取一个输入动作"""
        if sys.platform == "win32":
            return self._read_windows()
        return self._read_unix()

    def _read_windows(self) -> InputAction:
        import msvcrt
        if not msvcrt.kbhit():
            return InputAction.NONE

        ch = msvcrt.getch()
        if ch == b"\xe0" or ch == b"\x00":
            if msvcrt.kbhit():
                ch2 = msvcrt.getch()
                key = ch + ch2
            else:
                return InputAction.NONE
        else:
            key = ch

        action = self._KEY_MAP.get(key, InputAction.NONE)
        self._record(action, key)
        return action

    def _read_unix(self) -> InputAction:
        import select
        import tty
        import termios
        if not select.select([sys.stdin], [], [], 0)[0]:
            return InputAction.NONE

        old = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            ch = sys.stdin.buffer.read(1)
            if ch == b"\x1b":
                if select.select([sys.stdin], [], [], 0.05)[0]:
                    ch2 = sys.stdin.buffer.read(2)
                    key = ch + ch2
                else:
                    key = ch
            else:
                key = ch
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old)

        action = self._KEY_MAP.get(key, InputAction.NONE)
        self._record(action, key)
        return action

    def _record(self, action: InputAction, raw_key: bytes) -> None:
        self._history.append(action)
        if len(self._history) > self._max_history:
            self._history.pop(0)
        logger.debug("输入: raw=%s action=%s", raw_key, action.value)

    @property
    def history(self) -> list[InputAction]:
        return list(self._history)

    def debug_last_input(self) -> dict:
        """Debug接口：返回最近输入信息"""
        if not self._history:
            return {"last_action": None, "history_count": 0}
        return {
            "last_action": self._history[-1].value,
            "history_count": len(self._history),
        }
