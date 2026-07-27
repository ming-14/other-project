from __future__ import annotations

from typing import Optional

from core.models import ApiKeyConfig
from core.i18n import t
from ..printer.format import error


def parse_idx(arg: str) -> Optional[int]:
    try:
        return int(arg.strip())
    except (ValueError, AttributeError):
        error(t("helper.error.invalid_index"))
        return None


def get_key(pool_keys: list, idx: int) -> Optional[ApiKeyConfig]:
    if idx < 0 or idx >= len(pool_keys):
        error(t("helper.error.index_out_of_range", n=len(pool_keys) - 1))
        return None
    return pool_keys[idx]
