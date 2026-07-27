"""路由状态显示

显示 PoolRouter 中所有 entry 的实时状态。
"""

from __future__ import annotations

import time

from core.pool.router import PoolRouter
from core.models import AIPool
from core.i18n import t
from .format import header, divider


def _status_dot(available: bool, cooldown: float) -> str:
    if available:
        return "+"
    if cooldown < 0:
        return "x"
    return "o"


def route_status(pool: AIPool, router: PoolRouter):
    now = time.time()
    divider()
    print(f"  {t('route_status.label.pool')}: {pool.name}")
    print()
    for ki, kc in enumerate(pool.keys):
        label = kc.label or kc.base_url
        print(f"  Key [{ki}] {label}")
        for mid, mo in kc.models.items():
            available, wait = router._entry_available(ki, mid, kc, mo)
            dot = _status_dot(available, wait)
            if available:
                status = t("route_status.status.available")
            elif wait == -1:
                errors = router._key_errors.get(ki, 0)
                max_err = kc.errors.max_errors
                if max_err and errors >= max_err:
                    status = t("route_status.status.disabled_errors", errors=errors, max_err=max_err)
                else:
                    status = t("route_status.status.disabled")
            elif wait > 0:
                status = t("route_status.status.cooldown", wait=f"{wait:.0f}")
            else:
                status = t("route_status.status.disabled")
            print(f"    [{dot}] {mid} — {status}")
        print()
    divider()


def print_route_status(router: PoolRouter):
    print()
    header(t("route_status.header.route_status"))
    status_text = router.get_status_text()
    if status_text:
        print(status_text)
    else:
        print(f"  {t('route_status.info.no_route_info')}")
    print()
