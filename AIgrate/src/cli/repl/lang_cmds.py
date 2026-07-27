"""语言切换命令

提供 /language 命令的实现，支持查看和切换界面语言。
"""

from __future__ import annotations

from core.i18n import i18n_manager, t
from cli.printer.format import error, success, info, divider


class LanguageCommands:
    """语言切换命令混入类"""

    def do_language(self, arg: str):
        """/language [locale]  查看/切换界面语言"""
        arg = arg.strip()

        if not arg:
            self._show_language_info()
            return

        if arg not in i18n_manager.SUPPORTED_LOCALES:
            available = ", ".join(sorted(i18n_manager.SUPPORTED_LOCALES.keys()))
            error(t("language.unsupported", locale=arg))
            error(t("language.available_list", list=available))
            return

        name = i18n_manager.SUPPORTED_LOCALES[arg]
        if i18n_manager.set_locale(arg):
            success(t("language.switched", name=name, locale=arg))

    def _show_language_info(self):
        """显示当前语言和可选语言列表"""
        current = i18n_manager.get_locale()
        name = i18n_manager.SUPPORTED_LOCALES.get(current, current)
        info(t("language.current", name=name, locale=current))
        print()
        print(f"  {t('language.available')}")
        for locale, local_name in i18n_manager.SUPPORTED_LOCALES.items():
            print(f"    {locale:<6} {local_name}")
        print()
        dim(t("language.switch_hint"))


from cli.printer.format import dim