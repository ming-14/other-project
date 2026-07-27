"""应用设置管理器

负责用户设置的加载、保存和默认值管理。
将文件 I/O 从 UI 层抽离到 core 层，符合分层架构规范 §2.1。
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

from core.log.logger import get_logger

_logger = get_logger("SettingsManager")

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data",
)
SETTINGS_FILE = os.path.join(_DATA_DIR, "settings.json")

# ── 默认设置 ──────────────────────────────────────────────────────────────────

_DEFAULTS: dict[str, Any] = {
    "url_history": [],
    "theme": "DefaultNoMoreNagging",
    "auto_scroll": True,
    "show_timestamps": False,
    "clear_input_after_send": True,
    "auto_connect_last": False,
    "last_url": "",
    "last_key": "",
    "language": "zh-CN",
}


class SettingsManager:
    """应用设置管理器（单例）

    负责设置文件的读写，提供线程安全的存取接口。
    """

    def __init__(self):
        self._settings: dict[str, Any] = {}
        self._lock = threading.Lock()

    # ── 加载与保存 ──────────────────────────────────────────────────────────

    def load(self) -> dict[str, Any]:
        """从文件加载设置，缺失字段用默认值补全

        Returns:
            设置字典
        """
        with self._lock:
            self._settings = dict(_DEFAULTS)
            try:
                if os.path.exists(SETTINGS_FILE):
                    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    for key, val in _DEFAULTS.items():
                        if key in data:
                            self._settings[key] = data[key]
                    _logger.info("设置已加载")
            except Exception as e:
                _logger.warning("加载设置失败，使用默认值: %s", e)
            return dict(self._settings)

    def save(self) -> bool:
        """保存当前设置到文件

        Returns:
            保存成功返回 True
        """
        with self._lock:
            try:
                os.makedirs(_DATA_DIR, exist_ok=True)
                with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                    json.dump(self._settings, f, ensure_ascii=False, indent=2)
                _logger.debug("设置已保存到 %s", SETTINGS_FILE)
                return True
            except Exception as e:
                _logger.error("保存设置失败: %s", e)
                return False

    # ── 读写接口 ──────────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """获取单个设置项

        Args:
            key:     设置键名
            default: 默认值

        Returns:
            设置值
        """
        with self._lock:
            return self._settings.get(key, default)

    def set(self, key: str, value: Any):
        """设置单个设置项

        Args:
            key:   设置键名
            value: 设置值
        """
        with self._lock:
            self._settings[key] = value

    def update(self, d: dict[str, Any]):
        """批量更新设置

        Args:
            d: 要更新的键值对字典
        """
        with self._lock:
            self._settings.update(d)

    def get_all(self) -> dict[str, Any]:
        """获取全部设置的副本

        Returns:
            设置字典的浅拷贝
        """
        with self._lock:
            return dict(self._settings)

    def replace_all(self, settings: dict[str, Any]):
        """替换全部设置

        Args:
            settings: 新的设置字典
        """
        with self._lock:
            self._settings = dict(settings)


# ── 模块级单例 ─────────────────────────────────────────────────────────────────

settings_manager = SettingsManager()