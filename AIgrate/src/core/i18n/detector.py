"""系统语言检测器

通过环境变量和 Windows API 检测操作系统语言偏好，
并映射到应用支持的语言列表中。
"""

from __future__ import annotations

import os
import sys


def detect_system_locale(supported: dict[str, str], fallback: str) -> str:
    """检测系统语言并映射到最近的支持语言

    检测优先级：
        1. 环境变量 LANGUAGE
        2. 环境变量 LC_ALL
        3. 环境变量 LC_MESSAGES
        4. 环境变量 LANG
        5. Windows API GetUserDefaultUILanguage（仅 Windows）

    Args:
        supported: 支持的语言映射 {locale: name}
        fallback:  回退语言代码

    Returns:
        映射后的 locale 代码
    """
    env_vars = ["LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"]

    for var in env_vars:
        val = os.environ.get(var)
        if val:
            parsed = _parse_env_locale(val)
            if parsed:
                mapped = _map_locale(parsed, supported)
                if mapped:
                    return mapped

    if sys.platform == "win32":
        win_locale = _detect_windows_locale()
        if win_locale:
            mapped = _map_locale(win_locale, supported)
            if mapped:
                return mapped

    return fallback


def _parse_env_locale(env_val: str) -> str | None:
    """解析环境变量中的 locale 值，提取语言代码

    例如: "zh_CN.UTF-8" -> "zh-CN", "en_GB" -> "en"

    Args:
        env_val: 环境变量原始值

    Returns:
        标准化后的 locale 代码，解析失败返回 None
    """
    try:
        val = env_val.strip().split(":")[0].split(".")[0]
        val = val.replace("_", "-")
        if not val or not val[0].isalpha():
            return None
        return val
    except Exception:
        return None


def _map_locale(raw: str, supported: dict[str, str]) -> str | None:
    """将原始 locale 映射到支持列表中的最近语言

    映射规则：
        - 精确匹配（如 "zh-CN" -> "zh-CN"）
        - 语言前缀匹配（如 "zh-TW" -> "zh-CN"，"en-GB" -> "en"）
        - 无匹配返回 None

    Args:
        raw:      原始 locale 代码
        supported: 支持的语言映射

    Returns:
        映射后的 locale 代码，无匹配返回 None
    """
    if raw in supported:
        return raw

    prefix = raw.split("-")[0]
    if prefix:
        for supported_locale in supported:
            if supported_locale.split("-")[0] == prefix:
                return supported_locale

    return None


def _detect_windows_locale() -> str | None:
    """通过 Windows API 检测系统 UI 语言（仅 Windows）

    Returns:
        标准化后的 locale 代码，检测失败返回 None
    """
    try:
        import ctypes
        windll = ctypes.windll.kernel32
        lang_id = windll.GetUserDefaultUILanguage()

        lang_map = {
            0x0804: "zh-CN", 0x0404: "zh-CN",
            0x0409: "en",    0x0809: "en", 0x0C09: "en", 0x1009: "en", 0x1409: "en",
            0x0411: "ja",
            0x0412: "ko",
            0x0419: "ru",
            0x0C0A: "es",    0x040A: "es", 0x080A: "es",
            0x0416: "pt",    0x0816: "pt",
            0x040C: "fr",    0x080C: "fr", 0x0C0C: "fr",
        }

        if lang_id in lang_map:
            return lang_map[lang_id]

        primary = lang_id & 0xFF
        primary_map = {
            0x04: "zh-CN",
            0x09: "en",
            0x11: "ja",
            0x12: "ko",
            0x19: "ru",
            0x0A: "es",
            0x16: "pt",
            0x0C: "fr",
        }
        return primary_map.get(primary)

    except Exception:
        return None