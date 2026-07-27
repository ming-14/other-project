"""AI 池路由器 - 负责选择可用模型、追踪状态、自动重试与熔断"""

from __future__ import annotations

import random
import threading
import time
from collections import defaultdict
from typing import Optional, Callable

from core.models.entities import AIPool
from core.models.apikey import ApiKeyConfig
from core.models.overrides import ModelOverride
from core.pool.limiter import RateLimiter
from core.i18n import t


class PoolRouter:
    """AI 池路由器

    维护池内每个 entry（key + model）的状态，包括：
    - 并发计数
    - 连续错误计数与熔断
    - 冷却期
    - 速率限制
    - 请求总量限制
    """

    def __init__(self, pool: AIPool, on_log: Optional[Callable[[str], None]] = None):
        self.pool = pool
        self.on_log = on_log
        self.limiter = RateLimiter()
        self._lock = threading.Lock()
        self._active_groups: Optional[set] = None  # None = 全部活跃，无过滤
        self.reset_session()

    def _log(self, msg: str):
        if self.on_log:
            self.on_log(msg)

    def reset_session(self):
        """重置会话状态（用户切走池再切回来时调用）"""
        with self._lock:
            self.session_id = time.time()
            self._key_errors: dict[int, int] = defaultdict(int)
            self._key_reqs: dict[int, int] = defaultdict(int)
            self._key_conc: dict[int, int] = defaultdict(int)
            self._key_cooldown: dict[int, float] = {}
            self._mdl_errors: dict[tuple[int, str], int] = defaultdict(int)
            self._mdl_reqs: dict[tuple[int, str], int] = defaultdict(int)
            self._mdl_conc: dict[tuple[int, str], int] = defaultdict(int)
            self._mdl_cooldown: dict[tuple[int, str], float] = {}

    # ── 内部辅助 ──

    def _rate_scope_key(self, ki: int) -> str:
        return f"rate:key:{ki}"

    def _rate_scope_model(self, ki: int, mid: str) -> str:
        return f"rate:model:{ki}:{mid}"

    # ── 组过滤 ──

    def get_all_groups(self) -> set:
        """遍历所有 key/model 收集全部组名"""
        groups = set()
        for kc in self.pool.keys:
            groups.update(kc.groups)
            for mo in kc.models.values():
                groups.update(mo.groups)
        return groups

    def get_active_groups(self) -> Optional[set]:
        """返回当前活跃组集合，None 表示全部活跃"""
        return self._active_groups

    def set_active_groups(self, groups: Optional[set]):
        """设置活跃组集合，None 表示全部活跃（无过滤）"""
        with self._lock:
            self._active_groups = groups

    def _group_pass(self, cfg: ApiKeyConfig, mod: ModelOverride) -> tuple[bool, list[str]]:
        """检查组过滤：(key, model) 对通过当且仅当两者的所有组都在活跃列表中

        Returns:
            (pass, missing_groups)  missing_groups 为缺失的组名列表
        """
        if self._active_groups is None:
            return True, []
        missing = []
        for g in cfg.groups:
            if g not in self._active_groups:
                missing.append(g)
        for g in mod.groups:
            if g not in self._active_groups and g not in missing:
                missing.append(g)
        return len(missing) == 0, missing

    def _entry_available(self, ki: int, mid: str, cfg: ApiKeyConfig, mod: ModelOverride) -> tuple[bool, float]:
        """检查 (key_idx, model_id) 是否可用

        Returns:
            (available, wait_if_not)
            wait >= 0  暂时不可用，需等待
            wait == -1 永久禁用（错误超限或请求超限）
            wait == -2 组过滤禁用
        """
        now = time.time()
        max_wait = 0.0
        mk = (ki, mid)

        # ── 组过滤检查 ──
        group_pass, _ = self._group_pass(cfg, mod)
        if not group_pass:
            return False, -2

        # ── 启用状态检查 ──
        if not cfg.enabled:
            return False, -1
        if not mod.enabled:
            return False, -1

        # ── 永久禁用检查 ──
        if cfg.max_requests is not None and self._key_reqs[ki] >= cfg.max_requests:
            return False, -1
        if cfg.errors.max_errors is not None and self._key_errors[ki] >= cfg.errors.max_errors:
            return False, -1

        # max_errors_model：apikey 级别，按模型计数，仅禁用该模型
        if cfg.errors.max_errors_model is not None and self._mdl_errors[mk] >= cfg.errors.max_errors_model:
            return False, -1

        model_max_reqs = mod.max_requests if mod.max_requests is not None else cfg.max_requests
        if model_max_reqs is not None and self._mdl_reqs[mk] >= model_max_reqs:
            return False, -1
        model_max_err = mod.max_errors if mod.max_errors is not None else cfg.errors.max_errors
        if model_max_err is not None and self._mdl_errors[mk] >= model_max_err:
            return False, -1

        # ── 暂时不可用检查 ──
        # 规范 §4.2：Key 与 Model 限制取 max（保守策略），Model 只能放宽限制
        # None 表示无限制，用 float('inf') 参与比较以保持语义一致
        key_conc = cfg.errors.max_concurrency if cfg.errors.max_concurrency is not None else float('inf')
        model_conc = mod.max_concurrency if mod.max_concurrency is not None else key_conc
        effective_conc = max(key_conc, model_conc)
        if self._key_conc[ki] >= effective_conc or self._mdl_conc[mk] >= effective_conc:
            return False, -1

        # key 冷却
        if ki in self._key_cooldown:
            remaining = self._key_cooldown[ki] - now
            if remaining > 0:
                max_wait = max(max_wait, remaining)
            else:
                del self._key_cooldown[ki]

        # model 冷却
        if mk in self._mdl_cooldown:
            remaining = self._mdl_cooldown[mk] - now
            if remaining > 0:
                max_wait = max(max_wait, remaining)
            else:
                del self._mdl_cooldown[mk]

        # key 速率限制
        if cfg.rate_limits:
            ok, wait = self.limiter.check(self._rate_scope_key(ki), cfg.rate_limits)
            if not ok:
                max_wait = max(max_wait, wait)

        # model 速率限制（仅当模型明确覆盖时单独检查）
        if mod.rate_limits is not None:
            ok, wait = self.limiter.check(self._rate_scope_model(ki, mid), mod.rate_limits)
            if not ok:
                max_wait = max(max_wait, wait)

        available = (max_wait == 0)
        return available, max_wait if not available else 0.0

    def select_entry(self) -> Optional[tuple[int, str, ApiKeyConfig, ModelOverride]]:
        """选择一个可用 entry，如果没有可用则阻塞等待

        在持锁状态下完成「检查 → 选择 → 预留」原子操作，避免 TOCTOU 竞态。

        Returns:
            (key_idx, model_id, key_config, model_override)
            如果所有 entry 都永久禁用则返回 None
        """
        while True:
            with self._lock:
                candidates: list[tuple[int, str, ApiKeyConfig, ModelOverride]] = []
                any_temporary = False
                min_wait = float("inf")

                for ki, kc in enumerate(self.pool.keys):
                    for mid, mo in kc.models.items():
                        available, wait = self._entry_available(ki, mid, kc, mo)
                        if available:
                            candidates.append((ki, mid, kc, mo))
                        elif wait >= 0:
                            any_temporary = True
                            if wait < min_wait:
                                min_wait = wait

                if candidates:
                    ki, mid, kc, mo = random.choice(candidates)
                    # 原子性预留资源（持锁中，避免 TOCTOU）
                    self._key_conc[ki] += 1
                    self._mdl_conc[(ki, mid)] += 1
                    self._key_reqs[ki] += 1
                    self._mdl_reqs[(ki, mid)] += 1
                    if kc.rate_limits:
                        self.limiter.record(self._rate_scope_key(ki))
                    mod = kc.models.get(mid)
                    if mod and mod.rate_limits is not None:
                        self.limiter.record(self._rate_scope_model(ki, mid))
                    return ki, mid, kc, mo

                if not any_temporary:
                    return None

            # 锁外等待，避免阻塞其他线程的状态读写
            sleep_time = min(max(min_wait, 0.5), 5.0)
            self._log(t("router.log.all_limited", sleep_time=f"{sleep_time:.1f}"))
            time.sleep(sleep_time)

    # ── 外部接口 ──

    def report_success(self, ki: int, mid: str):
        """报告请求成功（释放并发计数，重置错误计数）"""
        with self._lock:
            self._key_conc[ki] = max(0, self._key_conc[ki] - 1)
            self._mdl_conc[(ki, mid)] = max(0, self._mdl_conc[(ki, mid)] - 1)
            self._key_errors[ki] = 0
            self._mdl_errors[(ki, mid)] = 0

    def report_error(self, ki: int, mid: str, cfg: ApiKeyConfig):
        """报告请求失败（释放并发，增加错误计数，进入冷却）"""
        with self._lock:
            self._key_conc[ki] = max(0, self._key_conc[ki] - 1)
            self._mdl_conc[(ki, mid)] = max(0, self._mdl_conc[(ki, mid)] - 1)
            self._key_errors[ki] += 1
            self._mdl_errors[(ki, mid)] += 1

            now = time.time()
            key_pause = cfg.errors.failure_pause
            key_pause_model = cfg.errors.failure_pause_model
            mod = cfg.models.get(mid)
            model_pause = mod.failure_pause if mod else None

            if model_pause is not None:
                self._mdl_cooldown[(ki, mid)] = now + model_pause
                scope = t("router.log.scope_model")
                pause = model_pause
            elif key_pause_model is not None:
                self._mdl_cooldown[(ki, mid)] = now + key_pause_model
                scope = t("router.log.scope_model")
                pause = key_pause_model
            elif key_pause is not None:
                self._key_cooldown[ki] = now + key_pause
                scope = t("router.log.scope_key")
                pause = key_pause
            else:
                self._key_cooldown[ki] = now + 40
                scope = t("router.log.scope_key")
                pause = 40

            model_label = mid
            if mid in cfg.models:
                model_label = cfg.models[mid].model_id
            self._log(t("router.log.request_failed",
                       label=model_label, scope=scope, pause=pause,
                       errors=self._mdl_errors[(ki, mid)], max_errors=cfg.errors.max_errors))

    def get_status_text(self) -> str:
        """返回所有 entry 的状态文本"""
        now = time.time()
        lines = []
        for ki, kc in enumerate(self.pool.keys):
            for mid, mo in kc.models.items():
                available, wait = self._entry_available(ki, mid, kc, mo)
                label = kc.label or kc.base_url
                mk = (ki, mid)

                parts = [f"[{mid}]"]
                if available:
                    parts.append(t("router.status.available"))
                elif wait == -2:
                    _, missing = self._group_pass(kc, mo)
                    parts.append(t("router.status.group_filtered", missing=",".join(missing)))
                elif wait == -1:
                    reasons = []
                    if kc.max_requests is not None and self._key_reqs[ki] >= kc.max_requests:
                        reasons.append(f"Key请求超限({self._key_reqs[ki]}/{kc.max_requests})")
                    if kc.errors.max_errors is not None and self._key_errors[ki] >= kc.errors.max_errors:
                        reasons.append(f"Key错误超限({self._key_errors[ki]}/{kc.errors.max_errors})")
                    # max_errors_model：apikey 级别，仅禁用该模型
                    if kc.errors.max_errors_model is not None and self._mdl_errors[mk] >= kc.errors.max_errors_model:
                        reasons.append(f"模型错误上限({self._mdl_errors[mk]}/{kc.errors.max_errors_model})")
                    model_max_reqs = mo.max_requests if mo.max_requests is not None else kc.max_requests
                    if model_max_reqs is not None and self._mdl_reqs[mk] >= model_max_reqs:
                        reasons.append(f"请求超限({self._mdl_reqs[mk]}/{model_max_reqs})")
                    model_max_err = mo.max_errors if mo.max_errors is not None else kc.errors.max_errors
                    if model_max_err is not None and self._mdl_errors[mk] >= model_max_err:
                        reasons.append(f"错误超限({self._mdl_errors[mk]}/{model_max_err})")
                    # None 表示无限制
                    key_conc = kc.errors.max_concurrency if kc.errors.max_concurrency is not None else float('inf')
                    model_conc = mo.max_concurrency if mo.max_concurrency is not None else key_conc
                    effective_conc = max(key_conc, model_conc)
                    if effective_conc != float('inf'):
                        if self._key_conc[ki] >= effective_conc:
                            reasons.append(f"Key并发({self._key_conc[ki]}/{effective_conc})")
                        if self._mdl_conc[mk] >= effective_conc:
                            reasons.append(f"并发({self._mdl_conc[mk]}/{effective_conc})")
                    parts.append(t("router.status.disabled") + " " + " ".join(reasons) if reasons else t("router.status.disabled"))
                else:
                    parts.append(t("router.status.waiting", wait=f"{wait:.0f}"))

                info = []
                if self._key_errors[ki] > 0:
                    info.append(f"KeyErr={self._key_errors[ki]}")
                if self._mdl_errors[mk] > 0:
                    info.append(f"Err={self._mdl_errors[mk]}")
                if self._key_reqs[ki] > 0:
                    info.append(f"KeyReq={self._key_reqs[ki]}")
                if self._mdl_reqs[mk] > 0:
                    info.append(f"Req={self._mdl_reqs[mk]}")
                if self._key_conc[ki] > 0:
                    info.append(f"KeyConc={self._key_conc[ki]}")
                if self._mdl_conc[mk] > 0:
                    info.append(f"Conc={self._mdl_conc[mk]}")
                if ki in self._key_cooldown:
                    rem = self._key_cooldown[ki] - now
                    if rem > 0:
                        info.append(f"Key冷却={rem:.0f}s")
                if mk in self._mdl_cooldown:
                    rem = self._mdl_cooldown[mk] - now
                    if rem > 0:
                        info.append(f"冷却={rem:.0f}s")
                if info:
                    parts.append("(" + " ".join(info) + ")")

                lines.append(f"        {label} | {' '.join(parts)}")
        return "\n".join(lines)

    def is_permanently_disabled(self, ki: int, mid: str, cfg: ApiKeyConfig) -> bool:
        """检查 entry 是否在本会话永久禁用"""
        mk = (ki, mid)
        model_max_err = cfg.errors.max_errors
        mod = cfg.models.get(mid)
        if mod and mod.max_errors is not None:
            model_max_err = mod.max_errors
        if model_max_err is not None and self._mdl_errors[mk] >= model_max_err:
            return True
        if cfg.errors.max_errors is not None and self._key_errors[ki] >= cfg.errors.max_errors:
            return True

        model_max_reqs = cfg.max_requests
        if mod and mod.max_requests is not None:
            model_max_reqs = mod.max_requests
        if model_max_reqs is not None and self._mdl_reqs[mk] >= model_max_reqs:
            return True
        if cfg.max_requests is not None and self._key_reqs[ki] >= cfg.max_requests:
            return True

        return False