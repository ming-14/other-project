from __future__ import annotations

import shlex

from core.models import VALID_API_TYPES, ApiKeyConfig
from core.i18n import t
from ..printer.format import error, success, warning, header, divider
from .helpers import parse_idx, get_key


class KeyCommands:
    def do_keys(self, arg):
        if not self.pool.keys:
            from ..printer.format import info
            info(t("key.info.no_keys"))
            return
        header(t("key.header.list", n=len(self.pool.keys)))
        for i, kc in enumerate(self.pool.keys):
            label = kc.label or kc.base_url
            models_count = len(kc.models)
            status = t("key.status.enabled") if kc.enabled else t("key.status.disabled")
            print(f"  [{i}] {label} ({t('key.label.type')}: {kc.type}) [{status}]")
            print(f"      URL: {kc.base_url}")
            print(f"      API Key: {kc.api_key[:8]}...")
            print(f"      {t('key.label.models')}: {models_count} 个")
            if kc.rate_limits:
                rules_str = ", ".join(r.describe() for r in kc.rate_limits)
                print(f"      {t('key.label.rate_limits')}: {rules_str}")
            print()
        divider()

    def do_key_enable(self, arg):
        """启用 API Key: key-enable <索引>"""
        idx = parse_idx(arg)
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        kc.enabled = True
        self._mark_modified()
        success(t("key.success.enabled", label=kc.label or kc.base_url))

    def do_key_disable(self, arg):
        """禁用 API Key: key-disable <索引>"""
        idx = parse_idx(arg)
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return
        kc.enabled = False
        self._mark_modified()
        success(t("key.success.disabled", label=kc.label or kc.base_url))

    def do_key_add(self, arg):
        parts = shlex.split(arg)
        if len(parts) < 3:
            error(t("key.error.usage_add"))
            error(t("key.info.api_types"))
            return
        label, base_url, api_key = parts[0], parts[1], parts[2]
        api_type = parts[3] if len(parts) >= 4 else "openai"
        if api_type not in VALID_API_TYPES:
            error(t("key.error.unknown_api_type", type=api_type, valid=", ".join(sorted(VALID_API_TYPES))))
            return
        kc = ApiKeyConfig(base_url=base_url, api_key=api_key, label=label, type=api_type)
        self.pool.keys.append(kc)
        self._mark_modified()
        success(t("key.success.added", label=label, type=api_type))

    def do_key_remove(self, arg):
        idx = parse_idx(arg)
        if idx is None:
            return
        if get_key(self.pool.keys, idx) is None:
            return
        kc = self.pool.keys.pop(idx)
        self._mark_modified()
        success(t("key.success.removed", label=kc.label or kc.base_url))

    def do_key_edit(self, arg):
        idx = parse_idx(arg)
        if idx is None:
            return
        kc = get_key(self.pool.keys, idx)
        if kc is None:
            return

        print(t("key.header.edit", label=kc.label or kc.base_url))
        label = input(f"  {t('key.edit.label')} [{kc.label}]: ").strip()
        if label:
            kc.label = label
        url = input(f"  {t('key.edit.base_url')} [{kc.base_url}]: ").strip()
        if url:
            kc.base_url = url
        api_key = input(f"  {t('key.edit.api_key')} [{kc.api_key[:8]}...]: ").strip()
        if api_key:
            kc.api_key = api_key
        raw_type = input(f"  {t('key.edit.api_type')} [{kc.type}] (openai|azure|anthropic|huggingface): ").strip()
        if raw_type:
            if raw_type in VALID_API_TYPES:
                kc.type = raw_type
            else:
                warning(t("key.warning.unknown_api_type", type=raw_type))
        raw = input(f"  {t('key.edit.max_concurrency')} [{kc.errors.max_concurrency}]: ").strip()
        if raw:
            try:
                kc.errors.max_concurrency = int(raw)
            except ValueError:
                warning(t("key.warning.invalid_input"))
        raw = input(f"  {t('key.edit.timeout')} [{kc.errors.timeout}]: ").strip()
        if raw:
            try:
                kc.errors.timeout = int(raw)
            except ValueError:
                warning(t("key.warning.invalid_input"))
        raw = input(f"  {t('key.edit.max_errors')} [{kc.errors.max_errors}]: ").strip()
        if raw:
            try:
                kc.errors.max_errors = int(raw)
            except ValueError:
                warning(t("key.warning.invalid_input"))
        raw = input(f"  {t('key.edit.max_requests')} [{kc.max_requests or t('key.display.unlimited')}]: ").strip()
        if raw:
            try:
                kc.max_requests = int(raw)
            except ValueError:
                warning(t("key.warning.invalid_input"))
        raw = input(f"  {t('key.edit.failure_pause')} [{kc.errors.failure_pause}]: ").strip()
        if raw:
            try:
                kc.errors.failure_pause = int(raw)
            except ValueError:
                warning(t("key.warning.invalid_input"))
        self._mark_modified()
        success(t("key.success.updated"))
