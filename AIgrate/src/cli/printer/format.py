from __future__ import annotations

import sys


INFO_PREFIX = "[i]"
SUCCESS_PREFIX = "[+]"
ERROR_PREFIX = "[-]"
WARNING_PREFIX = "[!]"
SYSTEM_PREFIX = "[*]"


def info(text: str):
    print(text)


def success(text: str):
    print(text)


def error(text: str):
    print(text, file=sys.stderr)


def warning(text: str):
    print(text)


def system(text: str):
    print(text)


def user(text: str):
    print(text)


def ai(text: str):
    print(text, end="", flush=True)


def dim(text: str):
    print(text)


def header(text: str):
    line = f"--- {text} " + "-" * max(0, 56 - len(text))
    print(f"\n{line}")


def divider():
    print("-" * 60)


def bold(text: str) -> str:
    return text