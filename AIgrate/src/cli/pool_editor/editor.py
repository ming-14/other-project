"""AI 池编辑器

对 AIPool 进行交互式编辑，组合 KeyCommands、ModelCommands、
LimitCommands、PropCommands 提供完整的编辑界面。
"""

from __future__ import annotations

import copy
import shlex

from core.models import AIPool
from core.i18n import t
from cli.printer.format import error, success, info, header, divider
from cli.pool_editor.key_cmds import KeyCommands
from cli.pool_editor.model_cmds import ModelCommands
from cli.pool_editor.limit_cmds import LimitCommands
from cli.pool_editor.prop_cmds import PropCommands

from core.pool.manager import pool_manager


class PoolEditor(KeyCommands, ModelCommands, LimitCommands, PropCommands):
    """AI 池编辑器

    提供交互式编辑界面，支持 Key、Model、限流规则、属性的增删改查。
    """

    def __init__(self, name: str, pool: AIPool | None = None):
        self.name = name
        self.is_new = pool is None
        if pool is None:
            self.pool = AIPool(name=name)
        else:
            self.pool = copy.deepcopy(pool)
        self._modified = False

    @property
    def modified(self) -> bool:
        return self._modified

    @modified.setter
    def modified(self, value: bool):
        self._modified = value

    def _mark_modified(self):
        """标记池已修改"""
        self._modified = True

    def do_save(self, arg: str) -> bool:
        if self.is_new:
            pool_manager.add_pool(self.pool)
        else:
            pool_manager.update_pool(self.name, self.pool)
        success(t("editor.pool.saved", name=self.name))
        return True

    def do_cancel(self, arg: str) -> bool:
        info(t("editor.info.cancelled"))
        return True

    def do_show(self, arg: str):
        divider()
        print(f"  {t('editor.show.name')}: {self.pool.name}")
        print(f"  {t('editor.show.key_count')}: {len(self.pool.keys)}")
        for i, kc in enumerate(self.pool.keys):
            label = kc.label or kc.base_url
            print(f"    [{i}] {label} — {kc.base_url}")
        divider()

    def do_EOF(self, arg: str) -> bool:
        return True

    def default(self, line: str):
        if not line:
            return None
        error(t("editor.error.unknown_command", line=line))
        return None

    def run(self):
        """启动编辑器主循环"""
        header(t("editor.header.edit_pool", name=self.name))
        self._show_help()
        while True:
            try:
                raw = input(f"[{self.name} edit] > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                info(t("editor.info.exit"))
                break
            if not raw:
                continue
            if raw.lower() in ("exit", "quit", "q"):
                if self._modified:
                    resp = input(t("editor.prompt.unsaved_confirm")).strip().lower()
                    if resp != "y":
                        continue
                break
            if raw.lower() in ("save", "s"):
                if self._modified:
                    success(t("editor.success.marked_save"))
                else:
                    info(t("editor.info.no_changes"))
                break

            parts = shlex.split(raw)
            cmd = parts[0].lower()
            arg = " ".join(parts[1:]) if len(parts) > 1 else ""

            if cmd in ("help", "h", "?"):
                self._show_help()
                continue

            method_name = f"do_{cmd.replace('-', '_')}"
            found = False
            for cls in type(self).__mro__:
                if method_name in cls.__dict__:
                    getattr(self, method_name)(arg)
                    found = True
                    break
            if not found:
                self.default(raw)

    def _show_help(self):
        """显示编辑器帮助"""
        print()
        print(t("editor.help.title"))
        divider()
        print("  keys                     列出所有 API Key")
        print("  key-add <标签> <url> <key> [type]  添加 Key")
        print("  key-remove <索引>       删除 Key")
        print("  key-edit <索引>         编辑 Key")
        print("  key-enable <索引>       启用 Key")
        print("  key-disable <索引>      禁用 Key")
        print()
        print("  models [key索引]        列出模型")
        print("  model-add <key索引> <model_id>    添加模型")
        print("  model-remove <key索引> <model_id> 删除模型")
        print("  model-enable <key索引> <model_id>  启用模型")
        print("  model-disable <key索引> <model_id> 禁用模型")
        print("  model-param <key索引> <model_id> <字段> <值>  设置模型参数")
        print("    字段: concurrency | timeout | max-errors | max-requests | failure-pause | context-length")
        print()
        print("  rate-limit-add <key索引> <type> <time> [count|tokens]  添加限流规则")
        print("     type: time-per-req | count-per-time | tokens-per-time")
        print("  rate-limit-list <key索引>  列出限流规则")
        print("  rate-limit-remove <key索引> <规则索引>  删除限流规则")
        print()
        print("  concurrency <key索引> [值]  查看/设置最大并发")
        print("  timeout <key索引> [值]      查看/设置超时")
        print("  max-errors <key索引> [值]   查看/设置最大错误")
        print("  max-requests <key索引> [值] 查看/设置最大请求")
        print("  failure-pause <key索引> [值] 查看/设置失败暂停")
        print()
        print("  save   保存并退出")
        print("  exit   退出（不保存）")
        print("  help   显示帮助")
        divider()
        print()
