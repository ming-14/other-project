"""!
@file core/audio.py
@brief 音频系统

事件驱动音效播放，终端环境下使用winsound或系统命令。
"""

import time
from typing import Callable, Optional

from core import log_manager

_logger = log_manager.get_logger('core.audio')


class AudioSystem:
    """!@brief 简易音频系统 - 事件驱动音效播放"""

    def __init__(self, event_bus=None):
        self._events = event_bus
        self._sounds: dict[str, str] = {}
        self._enabled = True
        self._volume = 1.0
        self._last_played: dict[str, float] = {}
        self._cooldown: float = 0.1

    def register_sound(self, name: str, file_path: str) -> None:
        self._sounds[name] = file_path

    def play(self, name: str) -> None:
        if not self._enabled or name not in self._sounds:
            return
        now = time.time()
        if name in self._last_played and now - self._last_played[name] < self._cooldown:
            return
        self._last_played[name] = now
        self._play_file(self._sounds[name])

    def _play_file(self, file_path: str) -> None:
        try:
            import os
            if not os.path.exists(file_path):
                return
            if os.name == 'nt':
                import winsound
                winsound.PlaySound(file_path,
                                   winsound.SND_FILENAME | winsound.SND_ASYNC)
            else:
                import subprocess
                subprocess.Popen(['aplay', '-q', file_path])
        except Exception as e:
            _logger.debug('音频播放失败: %s', e)

    def subscribe_events(self, event_map: dict) -> None:
        if not self._events:
            return
        for event_type, sound_name in event_map.items():
            self._events.subscribe(event_type,
                                   lambda data, sn=sound_name: self.play(sn))

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))

    @property
    def enabled(self) -> bool:
        return self._enabled
