"""国际化管理器

负责翻译字典的加载、语言切换、翻译查找与格式化。
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any

from core.log.logger import get_logger
from core.i18n.detector import detect_system_locale

_logger = get_logger("I18nManager")

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "data",
)
LOCALES_DIR = os.path.join(_DATA_DIR, "locales")


class _SafeDict(dict):
    """安全字典，缺失键时保留原始占位符文本"""

    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


class I18nManager:
    """国际化管理器（单例）

    负责翻译字典的加载、语言切换、翻译查找与格式化。
    """

    SUPPORTED_LOCALES: dict[str, str] = {
        "zh-CN": "简体中文",
        "en":    "English",
        "ja":    "日本語",
        "ko":    "한국어",
        "ru":    "Русский",
        "es":    "Español",
        "pt":    "Português",
        "fr":    "Français",
    }

    FALLBACK_LOCALE: str = "zh-CN"

    def __init__(self):
        self._current_locale: str = self.FALLBACK_LOCALE
        self._catalogs: dict[str, dict[str, str]] = {}
        self._loaded: set[str] = set()
        self._lock = threading.Lock()

    # ── 初始化 ──────────────────────────────────────────────────────────────

    def init(self) -> None:
        """初始化：从 settings 读取语言偏好，无则检测系统语言"""
        from core.settings import settings_manager

        saved = settings_manager.get("language")
        if saved and saved in self.SUPPORTED_LOCALES:
            self._current_locale = saved
            _logger.debug("从设置恢复语言: %s", saved)
        else:
            detected = detect_system_locale(self.SUPPORTED_LOCALES, self.FALLBACK_LOCALE)
            self._current_locale = detected
            settings_manager.set("language", detected)
            _logger.debug("系统语言检测: %s", detected)

        self._ensure_catalog(self._current_locale)
        self._ensure_catalog(self.FALLBACK_LOCALE)

    # ── 语言管理 ────────────────────────────────────────────────────────────

    def get_locale(self) -> str:
        """获取当前语言代码"""
        with self._lock:
            return self._current_locale

    def set_locale(self, locale: str) -> bool:
        """切换语言，验证有效性并持久化

        Args:
            locale: 目标语言代码

        Returns:
            切换成功返回 True，locale 无效返回 False
        """
        if locale not in self.SUPPORTED_LOCALES:
            return False

        with self._lock:
            self._current_locale = locale
            self._ensure_catalog(locale)

        from core.settings import settings_manager
        try:
            settings_manager.set("language", locale)
            settings_manager.save()
        except Exception as e:
            _logger.error("保存语言偏好失败: %s", e)

        return True

    def get_supported_locales(self) -> dict[str, str]:
        """获取所有支持的语言（locale -> 本地化名称）"""
        return dict(self.SUPPORTED_LOCALES)

    # ── 翻译 ────────────────────────────────────────────────────────────────

    def translate(self, key: str, **kwargs: Any) -> str:
        """翻译指定键，支持命名占位符格式化

        查找顺序：current_locale -> FALLBACK_LOCALE -> 返回 key 本身

        Args:
            key:    翻译键，如 "pool.deleted"
            kwargs: 占位符变量，如 name="mypool"

        Returns:
            翻译后的文本
        """
        with self._lock:
            locale = self._current_locale

        catalog = self._ensure_catalog(locale)
        text = catalog.get(key)

        if text is None and locale != self.FALLBACK_LOCALE:
            fallback_catalog = self._ensure_catalog(self.FALLBACK_LOCALE)
            text = fallback_catalog.get(key)

        if text is None:
            _logger.warning("翻译键缺失: %s", key)
            return key

        if kwargs:
            try:
                text = text.format_map(_SafeDict(kwargs))
            except Exception as e:
                _logger.warning("翻译格式化失败: key=%s, error=%s", key, e)

        return text

    # ── 内部方法 ────────────────────────────────────────────────────────────

    def _load_catalog(self, locale: str) -> dict[str, str]:
        """加载指定 locale 的翻译字典（JSON）

        Args:
            locale: 语言代码

        Returns:
            翻译字典，加载失败时返回空字典
        """
        filepath = os.path.join(LOCALES_DIR, f"{locale}.json")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                _logger.warning("翻译字典格式错误: %s（期望 dict，得到 %s）", locale, type(data).__name__)
                return {}
            _logger.debug("翻译字典已加载: %s（%d 键）", locale, len(data))
            return data
        except FileNotFoundError:
            _logger.warning("翻译字典文件缺失: %s", filepath)
            return {}
        except json.JSONDecodeError as e:
            _logger.warning("翻译字典 JSON 损坏: %s, error=%s", locale, e)
            return {}
        except Exception as e:
            _logger.warning("翻译字典加载异常: %s, error=%s", locale, e)
            return {}

    def _ensure_catalog(self, locale: str) -> dict[str, str]:
        """确保字典已加载，未加载则触发加载

        Args:
            locale: 语言代码

        Returns:
            翻译字典
        """
        if locale not in self._loaded:
            self._catalogs[locale] = self._load_catalog(locale)
            self._loaded.add(locale)
        return self._catalogs[locale]


# ── 模块级单例 ─────────────────────────────────────────────────────────────────

i18n_manager = I18nManager()