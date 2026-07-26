"""TerminalInfo - 终端尺寸检测与监控"""

import logging
import os
import sys

logger = logging.getLogger(__name__)

MIN_COLS = 60
MIN_ROWS = 20


class TerminalInfo:
    """终端尺寸信息，支持检测和轮询变化"""

    def __init__(self) -> None:
        self._cols = MIN_COLS
        self._rows = MIN_ROWS
        self._update_size()

    def _update_size(self) -> None:
        try:
            size = os.get_terminal_size()
            self._cols = max(size.columns, MIN_COLS)
            self._rows = max(size.lines, MIN_ROWS)
        except OSError:
            logger.debug("无法获取终端尺寸，使用默认值 %dx%d", MIN_COLS, MIN_ROWS)

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def rows(self) -> int:
        return self._rows

    def poll(self) -> bool:
        """轮询终端尺寸变化，返回是否变化"""
        old_cols, old_rows = self._cols, self._rows
        self._update_size()
        changed = self._cols != old_cols or self._rows != old_rows
        if changed:
            logger.info("终端尺寸变化: %dx%d -> %dx%d",
                        old_cols, old_rows, self._cols, self._rows)
        return changed

    def __repr__(self) -> str:
        return f"TerminalInfo({self._cols}x{self._rows})"
