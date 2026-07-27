"""普通 AI 编辑器

对 SingleAI 进行交互式编辑，支持查看和修改基本信息。
"""

from __future__ import annotations

import copy
import shlex

from core.models import SingleAI, ModelOverride, VALID_API_TYPES
from core.i18n import t
from cli.printer.format import error, success, info, header, divider

from core.pool.manager import pool_manager


class SingleEditor:
    """普通 AI 编辑器"""

    def __init__(self, name: str, entry: SingleAI):
        self.name = name
        self.original_name = name
        self.single = copy.deepcopy(entry)
        self._modified = False

    @property
    def modified(self) -> bool:
        return self._modified

    @modified.setter
    def modified(self, value: bool):
        self._modified = value

    def _mark_modified(self):
        """标记已修改"""
        self._modified = True

    def do_save(self, arg: str) -> bool:
        pool_manager.update_entry(self.single)
        success(t("single_editor.success.saved", name=self.name))
        return True

    def do_cancel(self, arg: str) -> bool:
        info(t("editor.info.cancelled"))
        return True

    def do_show(self, arg: str):
        divider()
        print(f"  {t('single_editor.show.name')}:      {self.single.name}")
        print(f"  {t('single_editor.show.alias')}:      {self.single.alias or t('single_editor.show.empty')}")
        status = t("single_editor.show.enabled") if self.single.enabled else t("single_editor.show.disabled")
        print(f"  {t('single_editor.show.status')}:      {status}")
        print(f"  Base URL:  {self.single.key.base_url}")
        api_key_display = self.single.key.api_key[:8] + "..." if self.single.key.api_key else t("single_editor.show.empty_key")
        print(f"  API Key:   {api_key_display}")
        print(f"  {t('single_editor.show.type')}:      {self.single.key.type}")
        print(f"  {t('single_editor.show.label')}:      {self.single.key.label or t('single_editor.show.empty')}")
        print(f"  {t('single_editor.show.model_count')}:    {len(self.single.models)}")
        if self.single.models:
            print(f"  {t('single_editor.show.model_list')}:")
            for mid, mo in self.single.models.items():
                tag = "" if mo.enabled else f" [{t('single_editor.show.disabled')}]"
                print(f"    - {mid}{tag}")
        divider()

    def do_EOF(self, arg: str) -> bool:
        return True

    def default(self, line: str):
        if not line:
            return None
        error(t("editor.error.unknown_command", line=line))
        return None

    def do_model_add(self, arg: str):
        if not arg:
            error(t("single_editor.error.usage_add_model"))
            return
        if arg in self.single.models:
            error(t("single_editor.error.model_exists", arg=arg))
            return
        self.single.models[arg] = ModelOverride(model_id=arg)
        self._mark_modified()
        success(t("single_editor.success.model_added", arg=arg))

    def do_model_remove(self, arg: str):
        if not arg:
            error(t("single_editor.error.usage_remove_model"))
            return
        if arg not in self.single.models:
            error(t("single_editor.error.model_not_found", arg=arg))
            return
        del self.single.models[arg]
        self._mark_modified()
        success(t("single_editor.success.model_removed", arg=arg))

    def do_url(self, arg: str):
        if not arg:
            error(t("single_editor.error.usage_url"))
            return
        self.single.key.base_url = arg
        self._mark_modified()
        success(t("single_editor.success.url_set", arg=arg))

    def do_key(self, arg: str):
        if not arg:
            error(t("single_editor.error.usage_key"))
            return
        self.single.key.api_key = arg
        self._mark_modified()
        success(t("single_editor.success.key_updated"))

    def do_label(self, arg: str):
        if not arg:
            error(t("single_editor.error.usage_label"))
            return
        self.single.key.label = arg
        self._mark_modified()
        success(t("single_editor.success.label_set", arg=arg))

    def run(self):
        """启动编辑器主循环"""
        header(t("single_editor.header.edit", name=self.name))
        self.do_show("")
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
            arg = parts[1] if len(parts) > 1 else ""

            if cmd in ("help", "h", "?"):
                self._show_help()
            elif cmd == "info":
                self.do_show("")
            elif cmd == "set-base-url":
                self.do_url(arg)
            elif cmd == "set-api-key":
                self.do_key(arg)
            elif cmd == "set-label":
                self.do_label(arg)
            elif cmd == "set-alias" and arg:
                self.single.alias = arg
                self._mark_modified()
                success(t("single_editor.success.alias_set", arg=arg))
            elif cmd == "set-type" and arg:
                if arg not in VALID_API_TYPES:
                    error(t("single_editor.error.invalid_type", arg=arg, valid=", ".join(sorted(VALID_API_TYPES))))
                    continue
                self.single.key.type = arg
                self._mark_modified()
                success(t("single_editor.success.type_set", arg=arg))
            elif cmd == "add-model":
                self.do_model_add(arg)
            elif cmd == "remove-model":
                self.do_model_remove(arg)
            elif cmd == "list-models":
                self.do_show("")
            elif cmd == "toggle-enabled":
                self.single.enabled = not self.single.enabled
                status = t("single_editor.show.enabled") if self.single.enabled else t("single_editor.show.disabled")
                self._mark_modified()
                success(t("single_editor.success.toggled", status=status))
            else:
                self.default(raw)

    def _show_help(self):
        """显示帮助"""
        print()
        print(t("editor.help.title"))
        divider()
        print("  info                    显示当前信息")
        print("  set-base-url <url>      设置 Base URL")
        print("  set-api-key <key>       设置 API Key")
        print("  set-label <label>       设置标签")
        print("  set-alias <alias>       设置别名")
        print("  set-type <type>         设置 API 类型 (openai|azure|anthropic|huggingface)")
        print("  add-model <model_id>    添加模型")
        print("  remove-model <model_id> 移除模型")
        print("  list-models             列出所有模型")
        print("  toggle-enabled          切换启用/禁用")
        print()
        print("  save   保存并退出")
        print("  exit   退出（不保存）")
        print("  help   显示帮助")
        divider()
        print()
