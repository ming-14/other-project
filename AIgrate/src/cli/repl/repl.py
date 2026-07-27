"""CLI REPL 主入口

提供交互式命令行界面，支持聊天、切换模型、管理配置等功能。
"""

from __future__ import annotations

import sys

from core.pool import pool_manager
from core.settings import settings_manager
from core.models import ChatParams
from core.i18n import i18n_manager, t
from cli.printer.format import error, system
from cli.printer.help_text import print_help, welcome
from cli.repl.lang_cmds import LanguageCommands
from cli.repl.chat_cmds import ChatCommands
from cli.repl.pool_cmds import PoolCommands
from cli.repl.direct_cmds import DirectCommands
from cli.repl.sender import Sender


class REPL(LanguageCommands, ChatCommands, PoolCommands, DirectCommands, Sender):
    """交互式命令行主类"""

    def __init__(self):
        self.params = ChatParams()
        self.messages: list[dict] = []
        self.streaming = False
        self.stop_flag = False
        self.current_entry_name = ""
        self.selected_model = ""
        self.mode = ""       # "", "pool", "single"
        self.selected_pool_key = None  # None=路由, int=直连
        pool_manager.load()
        settings_manager.load()
        i18n_manager.init()

    def _update_prompt(self) -> str:
        """更新提示符（当前条目/模型变化时调用）"""
        if not self.current_entry_name:
            return "> "
        if self.mode == "pool" and self.selected_pool_key is not None:
            # 池直连模式：显示 池名:Key索引:模型
            return f"[{self.current_entry_name}:{self.selected_pool_key}:{self.selected_model}] > "
        if self.mode == "pool":
            # 池路由模式：不显示具体模型（路由器动态选择）
            return f"[{self.current_entry_name} {t('repl.prompt.route')}] > "
        # 普通 AI 模式：显示 条目名:模型
        model_part = f":{self.selected_model}" if self.selected_model else ""
        return f"[{self.current_entry_name}{model_part}] > "

    def run(self):
        """启动 REPL 主循环"""
        welcome()
        while True:
            try:
                prompt = self._update_prompt()
                raw = input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                system(t("repl.exit.goodbye"))
                break
            if not raw:
                continue
            if raw.startswith("/"):
                self._dispatch(raw)
            else:
                self._send_message(raw)

    def _dispatch(self, cmd_line: str):
        """解析并分发命令

        Args:
            cmd_line: 以 / 开头的完整命令行
        """
        parts = cmd_line.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        # 内置退出/帮助命令
        if cmd in ("/exit", "/quit"):
            system(t("repl.exit.goodbye"))
            sys.exit(0)
        elif cmd == "/help":
            print_help()
            return

        # 委托给各个 do_* 方法（按 MRO 搜索）
        method_name = f"do_{cmd[1:]}"
        for cls in type(self).__mro__:
            if method_name in cls.__dict__:
                getattr(self, method_name)(arg)
                return
        error(t("repl.error.unknown_command", cmd=cmd))


def main():
    """REPL 入口函数"""
    repl = REPL()
    try:
        repl.run()
    except KeyboardInterrupt:
        print()
        system(t("repl.exit.goodbye"))
    except Exception as e:
        error(t("repl.error.fatal", e=e))
        sys.exit(1)


if __name__ == "__main__":
    main()