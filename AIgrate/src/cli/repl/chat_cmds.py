from __future__ import annotations

import shlex

from core.models import ChatParams
from core.i18n import t
from ..printer.format import error, success, header, dim


_PARAM_ALIASES: dict[str, tuple[str, str]] = {
    "temp":       ("temperature",   "Temperature"),
    "temperature":("temperature",   "Temperature"),
    "max":        ("max_tokens",    "Max Tokens"),
    "maxtokens":  ("max_tokens",    "Max Tokens"),
    "max_tokens": ("max_tokens",    "Max Tokens"),
    "top":        ("top_p",         "Top P"),
    "topp":       ("top_p",         "Top P"),
    "top_p":      ("top_p",         "Top P"),
    "sys":        ("system_prompt", "sys_prompt"),
    "system":     ("system_prompt", "sys_prompt"),
}


def _parse_and_validate(name: str, raw_value: str, target: ChatParams) -> tuple[bool, str]:
    """解析并验证参数值，返回 (ok, message)"""
    attr, display_key = _PARAM_ALIASES[name]
    display = t("param.alias.system_prompt") if display_key == "sys_prompt" else display_key
    try:
        if attr == "temperature":
            val = float(raw_value)
            if not 0 <= val <= 2:
                return False, t("param.error.temp_range", display=display)
            target.temperature = val
        elif attr == "max_tokens":
            val = int(raw_value)
            if val <= 0:
                return False, t("param.error.max_tokens_positive", display=display)
            target.max_tokens = val
        elif attr == "top_p":
            val = float(raw_value)
            if not 0 <= val <= 1:
                return False, t("param.error.top_p_range", display=display)
            target.top_p = val
        elif attr == "system_prompt":
            target.system_prompt = raw_value
        return True, f"{display} = {raw_value}"
    except ValueError:
        return False, t("param.error.invalid_value", display=display, raw_value=raw_value)


def _show_params(params: ChatParams, names: list[str] | None = None):
    """显示参数，names 为空则显示全部"""
    sys_display = t("param.alias.system_prompt")
    items = [
        ("temp",  "Temperature",   params.temperature),
        ("max",   "Max Tokens",    params.max_tokens),
        ("top",   "Top P",         params.top_p),
        ("sys",   sys_display,     params.system_prompt or t("param.display.none")),
    ]
    if names:
        resolved = set()
        for n in names:
            key = n.lower()
            if key in _PARAM_ALIASES:
                resolved.add(_PARAM_ALIASES[key][0])
            else:
                error(t("param.error.unknown", n=n))
                return
        items = [(k, d, v) for k, d, v in items if _PARAM_ALIASES[k][0] in resolved]

    header(t("param.header.chat_params"))
    for key, display, value in items:
        print(f"  {display.ljust(12)} = {value}")
    print()


def _reset_params(params: ChatParams, names: list[str] | None = None):
    """重置参数，names 为空则重置全部"""
    defaults = ChatParams()
    if not names:
        params.temperature = defaults.temperature
        params.max_tokens = defaults.max_tokens
        params.top_p = defaults.top_p
        params.system_prompt = defaults.system_prompt
        success(t("param.success.all_reset"))
    else:
        reset_list = []
        for n in names:
            key = n.lower()
            if key not in _PARAM_ALIASES:
                error(t("param.error.unknown", n=n))
                return
            attr, display_key = _PARAM_ALIASES[key]
            display = t("param.alias.system_prompt") if display_key == "sys_prompt" else display_key
            setattr(params, attr, getattr(defaults, attr))
            reset_list.append(display)
        success(t("param.success.reset", list=", ".join(reset_list)))


class ChatCommands:
    def do_params(self, arg: str):
        """
        /params                         查看所有参数
        /params temp=0.7                设置 Temperature
        /params max=2048                设置 Max Tokens
        /params temp=0.7 max=2048       同时设置多个
        /params sys="你是助手"           设置系统提示词
        /params reset                   全部恢复默认值
        /params temp max                查看指定参数
        /params reset temp max          重置指定参数
        """
        raw = arg.strip()
        if not raw:
            _show_params(self.params)
            return

        try:
            tokens = shlex.split(raw)
        except ValueError:
            tokens = raw.split()

        if tokens[0].lower() == "reset":
            reset_names = tokens[1:] if len(tokens) > 1 else None
            _reset_params(self.params, reset_names)
            return

        has_equals = any("=" in t for t in tokens)
        if has_equals:
            results = []
            for token in tokens:
                if "=" not in token:
                    error(t("param.error.invalid_format", token=token))
                    return
                name, _, raw_value = token.partition("=")
                name = name.lower()
                if name not in _PARAM_ALIASES:
                    error(t("param.error.unknown", n=name))
                    return
                ok, msg = _parse_and_validate(name, raw_value, self.params)
                if not ok:
                    error(msg)
                    return
                results.append(msg)
            success(t("param.success.set", results=", ".join(results)))
        else:
            _show_params(self.params, tokens)

    def do_new(self, arg):
        from ..printer.format import system, warning, info
        if self.streaming:
            warning(t("chat.warning.stop_first"))
            return
        if self.messages:
            self.messages = []
            system(t("chat.success.new_conversation"))
        else:
            info(t("chat.info.already_empty"))

    def do_clear(self, arg):
        import os
        if self.streaming:
            from ..printer.format import warning
            warning(t("chat.warning.stop_first"))
            return
        os.system("cls")

    def do_export(self, arg):
        import os
        import time
        from ..printer.format import error, success
        if not self.messages:
            error(t("export.error.empty"))
            return
        filename = arg.strip() or f"chat_export_{int(time.time())}.txt"
        try:
            with open(filename, "w", encoding="utf-8") as f:
                for msg in self.messages:
                    role = msg.get("role", "unknown")
                    content = msg.get("content", "")
                    label = "You" if role == "user" else "AI" if role == "assistant" else role
                    f.write(f"[{label}] {content}\n\n")
            success(t("export.success.exported", path=os.path.abspath(filename)))
        except Exception as e:
            error(t("export.error.failed", e=e))
