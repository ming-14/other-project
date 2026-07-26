"""ScreenBuffer - 全屏虚拟缓冲区，基于行的双缓冲差异更新"""

import ctypes
import logging
import os
import sys

logger = logging.getLogger(__name__)


def _enable_vt100() -> bool:
    """Windows: 启用虚拟终端(VT100)处理，返回是否成功"""
    if os.name != "nt":
        return True
    try:
        kernel32 = ctypes.windll.kernel32
        STD_OUTPUT_HANDLE = -11
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        if handle == -1 or handle == 0:
            logger.warning("无法获取stdout句柄，VT100启用失败")
            return False
        mode = ctypes.c_ulong()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            logger.warning("GetConsoleMode失败，VT100启用失败")
            return False
        if mode.value & ENABLE_VIRTUAL_TERMINAL_PROCESSING == 0:
            new_mode = ctypes.c_ulong(mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
            if not kernel32.SetConsoleMode(handle, new_mode):
                logger.warning("SetConsoleMode失败，VT100启用失败")
                return False
            logger.debug("已启用Windows VT100虚拟终端")
        return True
    except Exception as e:
        logger.warning("VT100启用异常: %s", e)
        return False

ANSI_RESET = "\033[0m"
ANSI_CLEAR = "\033[2J\033[H"
ANSI_HIDE_CURSOR = "\033[?25l"
ANSI_SHOW_CURSOR = "\033[?25h"
ANSI_CLEAR_LINE = "\033[2K"


class ScreenBuffer:
    """全屏虚拟缓冲区：基于行的双缓冲差异输出

    _front: 上一帧已输出到终端的内容
    _back: 当前帧待输出的内容
    _need_full_redraw: 是否需要全量重绘（init/resize后首次渲染）
    """

    def __init__(self, rows: int, cols: int) -> None:
        self._rows = rows
        self._cols = cols
        self._front: list[str] = [""] * rows
        self._back: list[str] = [""] * rows
        self._out = sys.stdout
        self._need_full_redraw = True
        self._vt100_ok = True

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    def resize(self, rows: int, cols: int) -> None:
        if rows == self._rows and cols == self._cols:
            return
        self._rows = rows
        self._cols = cols
        self._front = [""] * rows
        self._back = [""] * rows
        self._need_full_redraw = True
        logger.debug("缓冲区调整: %dx%d", rows, cols)

    def clear_back(self) -> None:
        self._back = [""] * self._rows

    def set_row(self, row: int, content: str) -> None:
        if 0 <= row < self._rows:
            self._back[row] = content

    def get_row(self, row: int) -> str:
        if 0 <= row < self._rows:
            return self._back[row]
        return ""

    def swap_and_flush(self) -> int:
        """差异更新后缓冲区到终端，返回变化行数"""
        if self._need_full_redraw or not self._vt100_ok:
            return self._full_redraw()

        changed = 0
        parts: list[str] = []
        for r in range(self._rows):
            if self._front[r] != self._back[r]:
                changed += 1
                parts.append(f"\033[{r + 1};1H")
                parts.append(ANSI_CLEAR_LINE)
                parts.append(self._back[r])

        if changed > 0:
            parts.append(ANSI_RESET)
            self._out.write("".join(parts))
            self._out.flush()

        self._front = list(self._back)
        self.clear_back()
        return changed

    def _full_redraw(self) -> int:
        """全量重绘：清屏后输出所有行"""
        parts = [ANSI_CLEAR]
        for r in range(self._rows - 1):
            parts.append(self._back[r])
            parts.append("\n")
        if self._rows > 0:
            parts.append(self._back[self._rows - 1])
        parts.append(ANSI_RESET)
        self._out.write("".join(parts))
        self._out.flush()

        self._need_full_redraw = False
        self._front = list(self._back)
        self.clear_back()
        return self._rows

    def full_flush(self) -> None:
        """强制全量输出"""
        self._need_full_redraw = False
        self._full_redraw()

    def request_full_redraw(self) -> None:
        """标记下一帧需要全量重绘"""
        self._need_full_redraw = True

    def init_screen(self) -> None:
        """初始化屏幕：启用VT100、隐藏光标、清屏、标记需要全量重绘"""
        self._vt100_ok = _enable_vt100()
        if not self._vt100_ok:
            logger.warning("VT100不可用，回退到每帧全量重绘模式")
        self._out.write(ANSI_HIDE_CURSOR + ANSI_CLEAR)
        self._out.flush()
        self._need_full_redraw = True
        self._front = [""] * self._rows

    def restore_screen(self) -> None:
        """恢复屏幕：显示光标、清屏"""
        self._out.write(ANSI_SHOW_CURSOR + ANSI_CLEAR)
        self._out.flush()

    def debug_dump_row(self, row: int) -> str:
        """Debug接口：返回指定行去除ANSI码的纯文本"""
        if 0 <= row < self._rows:
            import re
            return re.sub(r'\033\[[0-9;]*m', '', self._back[row])
        return ""

    def debug_dump_front(self) -> str:
        """Debug接口：返回front缓冲区摘要"""
        non_empty = sum(1 for r in self._front if r)
        return f"Front: {self._rows} rows, {non_empty} non-empty, full_redraw={self._need_full_redraw}"
