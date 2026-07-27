from __future__ import annotations

import shlex

from core.models import LimitRule
from core.i18n import t
from ..printer.format import error, success, header
from .helpers import parse_idx, get_key


class LimitCommands:
    def do_rate_limit_add(self, arg):
        parts = shlex.split(arg)
        if len(parts) < 3:
            error(t("limit.error.usage_add"))
            error(t("limit.info.types"))
            return
        idx = parse_idx(parts[0])
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        rule_type = parts[1]
        try:
            rule_time = int(parts[2])
        except ValueError:
            error(t("limit.error.time_not_int"))
            return

        if rule_type == "time_per_req":
            rule = LimitRule(type=rule_type, time=rule_time)
        elif rule_type == "count_per_time":
            if len(parts) < 4:
                error(t("limit.error.count_required"))
                return
            try:
                count = int(parts[3])
            except ValueError:
                error(t("limit.error.count_not_int"))
                return
            rule = LimitRule(type=rule_type, time=rule_time, count=count)
        elif rule_type == "tokens_per_time":
            if len(parts) < 4:
                error(t("limit.error.tokens_required"))
                return
            try:
                tokens = int(parts[3])
            except ValueError:
                error(t("limit.error.tokens_not_int"))
                return
            rule = LimitRule(type=rule_type, time=rule_time, tokens=tokens)
        else:
            error(t("limit.error.unknown_type", type=rule_type))
            return

        if kc.rate_limits is None:
            kc.rate_limits = []
        kc.rate_limits.append(rule)
        self._mark_modified()
        success(t("limit.success.added", desc=rule.describe()))

    def do_rate_limit_list(self, arg):
        idx = parse_idx(arg)
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        if not kc.rate_limits:
            from ..printer.format import info
            info(t("limit.info.no_rules"))
            return
        header(t("limit.header.list", label=kc.label or kc.base_url))
        for i, rule in enumerate(kc.rate_limits):
            print(f"  [{i}] {rule.describe()}")

    def do_rate_limit_remove(self, arg):
        parts = shlex.split(arg)
        if len(parts) < 2:
            error(t("limit.error.usage_remove"))
            return
        idx = parse_idx(parts[0])
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        rule_idx = parse_idx(parts[1])
        if rule_idx is None:
            return
        if not kc.rate_limits or rule_idx < 0 or rule_idx >= len(kc.rate_limits):
            error(t("limit.error.index_out_of_range"))
            return
        rule = kc.rate_limits.pop(rule_idx)
        self._mark_modified()
        success(t("limit.success.removed", desc=rule.describe()))
