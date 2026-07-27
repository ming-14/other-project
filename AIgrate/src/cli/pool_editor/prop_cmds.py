from __future__ import annotations

import shlex

from core.i18n import t
from ..printer.format import error, success
from .helpers import parse_idx, get_key


class PropCommands:
    def do_concurrency(self, arg):
        parts = shlex.split(arg)
        if not parts:
            error(t("prop.error.usage_concurrency"))
            return
        idx = parse_idx(parts[0])
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        if len(parts) >= 2:
            try:
                kc.errors.max_concurrency = int(parts[1])
                self._mark_modified()
                success(t("prop.success.concurrency_set", val=kc.errors.max_concurrency))
            except ValueError:
                error(t("prop.error.not_int"))
        else:
            from ..printer.format import info
            info(t("prop.info.current_concurrency", val=kc.errors.max_concurrency))

    def do_timeout(self, arg):
        parts = shlex.split(arg)
        if not parts:
            error(t("prop.error.usage_timeout"))
            return
        idx = parse_idx(parts[0])
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        if len(parts) >= 2:
            try:
                kc.errors.timeout = int(parts[1])
                self._mark_modified()
                success(t("prop.success.timeout_set", val=kc.errors.timeout))
            except ValueError:
                error(t("prop.error.not_int"))
        else:
            from ..printer.format import info
            info(t("prop.info.current_timeout", val=kc.errors.timeout))

    def do_max_errors(self, arg):
        parts = shlex.split(arg)
        if not parts:
            error(t("prop.error.usage_max_errors"))
            return
        idx = parse_idx(parts[0])
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        if len(parts) >= 2:
            try:
                kc.errors.max_errors = int(parts[1])
                self._mark_modified()
                success(t("prop.success.max_errors_set", val=kc.errors.max_errors))
            except ValueError:
                error(t("prop.error.not_int"))
        else:
            from ..printer.format import info
            info(t("prop.info.current_max_errors", val=kc.errors.max_errors))

    def do_max_requests(self, arg):
        parts = shlex.split(arg)
        if not parts:
            error(t("prop.error.usage_max_requests"))
            return
        idx = parse_idx(parts[0])
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        if len(parts) >= 2:
            try:
                kc.max_requests = int(parts[1])
                self._mark_modified()
                success(t("prop.success.max_requests_set", val=kc.max_requests))
            except ValueError:
                error(t("prop.error.not_int"))
        else:
            from ..printer.format import info
            info(t("prop.info.current_max_requests", val=kc.max_requests or t("prop.display.unlimited")))

    def do_failure_pause(self, arg):
        parts = shlex.split(arg)
        if not parts:
            error(t("prop.error.usage_failure_pause"))
            return
        idx = parse_idx(parts[0])
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        if len(parts) >= 2:
            try:
                kc.errors.failure_pause = int(parts[1])
                self._mark_modified()
                success(t("prop.success.failure_pause_set", val=kc.errors.failure_pause))
            except ValueError:
                error(t("prop.error.not_int"))
        else:
            from ..printer.format import info
            info(t("prop.info.current_failure_pause", val=kc.errors.failure_pause))
