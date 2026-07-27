from __future__ import annotations

from core.models import AIPool
from core.i18n import t
from .format import info, header, divider, dim


def _groups_tag(groups: list[str]) -> str:
    if not groups or groups == ["other"]:
        return ""
    return f" [{t('pool_display.tag.group')}:{','.join(groups)}]"


def print_pools(pool_names: list[str]):
    if not pool_names:
        info(t("pool_display.info.no_pools"))
        return
    header(t("pool_display.header.pool_list"))
    for i, name in enumerate(pool_names, 1):
        print(f"  {i}. {name}")
    print()


def print_pool_detail(pool: AIPool):
    pool_tag = "" if pool.enabled else f" [{t('pool_display.status.disabled')}]"
    print(f"\n{t('pool_display.label.pool_name')}: {pool.name}{pool_tag}")
    divider()
    for ki, kc in enumerate(pool.keys):
        key_tag = ("" if kc.enabled else f" [{t('pool_display.status.disabled')}]") + _groups_tag(kc.groups)
        print(f"\n[{ki}] {kc.label or kc.base_url} ({t('pool_display.label.type')}: {kc.type}){key_tag}")
        print(f"      URL: {kc.base_url}")
        print(f"      Key: {kc.api_key[:8]}...")
        print(f"      {t('pool_display.field.concurrency')}: {kc.errors.max_concurrency}  |  "
              f"{t('pool_display.field.timeout')}: {kc.errors.timeout}s  |  "
              f"{t('pool_display.field.max_errors')}: {kc.errors.max_errors}  |  "
              f"{t('pool_display.field.max_requests')}: {kc.max_requests or t('pool_display.display.unlimited')}")
        print(f"      {t('pool_display.field.failure_pause')}: {kc.errors.failure_pause}s")
        if kc.rate_limits:
            rules_str = ", ".join(r.describe() for r in kc.rate_limits)
            print(f"      {t('pool_display.label.rate_limits')}: {rules_str}")
        print(f"      {t('pool_display.label.models')} ({len(kc.models)}):")
        for mid in kc.models:
            mo = kc.models[mid]
            model_tag = ("" if mo.enabled else f" [{t('pool_display.status.disabled')}]") + _groups_tag(mo.groups)
            overrides = []
            if mo.max_concurrency is not None:
                overrides.append(f"{t('pool_display.override.concurrency')}={mo.max_concurrency}")
            if mo.timeout is not None:
                overrides.append(f"{t('pool_display.override.timeout')}={mo.timeout}s")
            if mo.max_errors is not None:
                overrides.append(f"{t('pool_display.override.max_errors')}={mo.max_errors}")
            if mo.max_requests is not None:
                overrides.append(f"{t('pool_display.override.max_requests')}={mo.max_requests}")
            if mo.failure_pause is not None:
                overrides.append(f"{t('pool_display.override.failure_pause')}={mo.failure_pause}s")
            override_str = f" ({'; '.join(overrides)})" if overrides else ""
            print(f"        - {mid}{override_str}{model_tag}")
    print()
