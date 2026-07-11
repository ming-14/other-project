"""!
@file platform/ansi_output.py
@brief ANSI真彩色序列输出实现

跨平台回退方案，使用ANSI 24位真彩色序列 + 半块字符渲染。
"""

import sys

from platform.base import PlatformOutput
from core import log_manager

_logger = log_manager.get_logger('platform.ansi_output')


class ANSIOutput(PlatformOutput):
    """!@brief ANSI序列输出实现"""

    def __init__(self):
        self._available = False

    def available(self):
        return self._available

    def write_frame(self, buffer, width, height, hud_text=''):
        """!@brief 通过render_pipeline的render_to_bytes输出

        @param buffer   像素缓冲区数据（list of list of tuple）
        @param width    终端列数
        @param height   终端行数
        @param hud_text HUD文本
        """
        pass

    def write_message(self, message):
        sys.stdout.write('\033[H' + message)
        sys.stdout.flush()

    def shutdown(self):
        pass
