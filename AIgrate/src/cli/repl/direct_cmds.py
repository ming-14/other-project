"""直连与新建连接命令

提供 /connect 命令的实现，支持直接从命令行连接新的 API。
"""

from __future__ import annotations

import shlex

from core.pool import pool_manager
from core.models import SingleAI, ApiKeyConfig, ModelOverride, VALID_API_TYPES
from core.i18n import t
from cli.printer.format import error, success, warning


class DirectCommands:
    """直连/新建连接命令混入类"""

    def _update_prompt(self) -> str:
        """更新提示符（由子类重写）"""
        return "> "

    def do_connect(self, arg: str):
        """
        /connect <url> <key> [flags]

        新建普通 AI 并切换（持久保存）。
        Flags:
            --type TYPE          API 类型: openai|azure|anthropic|huggingface
            --label LABEL        显示标签
            --name NAME          配置条目名（默认取 label）
            --model M1 M2 ...    指定模型列表
        """
        parts = shlex.split(arg)
        if len(parts) < 2:
            error(t("connect.error.usage"))
            return

        base_url = parts[0]
        api_key = parts[1]

        flags = {"type": "openai", "label": "", "name": "", "models": []}
        i = 2
        while i < len(parts):
            if parts[i] == "--type" and i + 1 < len(parts):
                flags["type"] = parts[i + 1]
                i += 2
            elif parts[i] == "--label" and i + 1 < len(parts):
                flags["label"] = parts[i + 1]
                i += 2
            elif parts[i] == "--name" and i + 1 < len(parts):
                flags["name"] = parts[i + 1]
                i += 2
            elif parts[i] == "--model":
                i += 1
                models = []
                while i < len(parts) and not parts[i].startswith("--"):
                    models.append(parts[i])
                    i += 1
                flags["models"] = models
            else:
                error(t("connect.error.unknown_flag", flag=parts[i]))
                return

        if flags["type"] not in VALID_API_TYPES:
            error(t("connect.error.invalid_api_type", type=flags["type"], valid=", ".join(sorted(VALID_API_TYPES))))
            return

        name = flags["name"] or flags["label"] or base_url
        existing = pool_manager.get_entry(name)
        if existing and isinstance(existing, SingleAI):
            existing.key.base_url = base_url
            existing.key.api_key = api_key
            existing.key.type = flags["type"]
            if flags["label"]:
                existing.key.label = flags["label"]
            if flags["models"]:
                existing.models = {m: ModelOverride(model_id=m) for m in flags["models"]}
            pool_manager.update_entry(existing)
            success(t("connect.success.updated", name=name))
            self.mode = "single"
            self.current_entry_name = name
            self.selected_model = flags["models"][0] if flags["models"] else ""
            self.selected_pool_key = None
            self._update_prompt()
            return
        elif existing:
            warning(t("connect.warning.entry_exists", name=name))
            self.mode = "single"
            self.current_entry_name = name
            self.selected_model = ""
            self.selected_pool_key = None
            self._update_prompt()
            return

        kc = ApiKeyConfig(
            base_url=base_url,
            api_key=api_key,
            label=flags["label"],
            type=flags["type"],
        )
        entry = SingleAI(name=name, key=kc, models=flags["models"])
        pool_manager.add_entry(entry)

        self.mode = "single"
        self.current_entry_name = name
        self.selected_model = flags["models"][0] if flags["models"] else ""
        self.selected_pool_key = None
        success(t("connect.success.connected", name=name, type=flags["type"]))
        self._update_prompt()
