from __future__ import annotations

from core.i18n import t
from .format import divider


def welcome():
    print()
    print(t("repl.welcome.title"))
    divider()
    print(t("repl.welcome.hint"))
    print(t("repl.welcome.chat_hint"))
    print()


def print_help():
    """打印格式化的帮助信息

    格式: (cmd, desc)，多行 cmd 用 \\n 分隔，第一行带 desc
    """
    sections = [
        (t("help.section.chat"), [
            ("<text>", t("help.chat.send")),
            ("/new", t("help.chat.new")),
            ("/clear", t("help.chat.clear")),
            ("/export [file]", t("help.chat.export")),
        ]),
        (t("help.section.switch"), [
            ("/model <id|name>\n"
             "       <pool>:<model>\n"
             "       <pool>:<N>:<model>",
             t("help.switch.model_entry") + "\n"
             + t("help.switch.model_pool_model") + "\n"
             + t("help.switch.model_pool_key_model")),
            ("/models", t("help.switch.models")),
            ("/models fetch", t("help.switch.models_fetch")),
            ("/status", t("help.switch.status")),
        ]),
        (t("help.section.manage"), [
            ("/connect <url> <key>\n"
             "        --type TYPE  (req)\n"
             "        --label LAB  (req)\n"
             "        --name NAME\n"
             "        --model M1 M2 ...",
             t("help.manage.connect_desc") + "\n"
             + t("help.manage.connect_type") + "\n"
             + t("help.manage.connect_label") + "\n"
             + t("help.manage.connect_name") + "\n"
             + t("help.manage.connect_model")),
            ("/pool create <name>", t("help.manage.pool_create")),
            ("      delete <name>", t("help.manage.pool_delete")),
            ("      rename <old> <new>", t("help.manage.pool_rename")),
            ("      edit <name>", t("help.manage.pool_edit")),
            ("      test <name>", t("help.manage.pool_test")),
        ]),
        (t("help.section.params"), [
            ("/params", t("help.params.view")),
            ("/params <k>=<v> ...", t("help.params.set")),
            ("/params reset [k...]", t("help.params.reset")),
        ]),
        (t("help.section.system"), [
            ("/language [locale]", t("help.system.language")),
            ("/help", t("help.system.help")),
            ("/exit or /quit", t("help.system.exit")),
        ]),
    ]

    for title, cmds in sections:
        print()
        print(f"  {title}")
        divider()
        for cmd, desc in cmds:
            cmd_lines = cmd.split("\n")
            desc_lines = desc.split("\n")
            for i, cl in enumerate(cmd_lines):
                dl = desc_lines[i] if i < len(desc_lines) else ""
                print(f"    {cl:<30} {dl}")
    print()
