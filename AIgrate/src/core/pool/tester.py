"""AI 池一键测试 - 逐个测试所有 key×model 组合

遵守 max_concurrency 和 rate_limits，不触碰限速规则。
超时时间: 模型 timeout > key timeout > 默认 120s
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable

from core.models.entities import AIPool
from core.models.apikey import ApiKeyConfig
from core.models.overrides import ModelOverride
from core.pool.limiter import RateLimiter
from core.client.chat import stream_chat
from core.i18n import t

DEFAULT_TEST_TIMEOUT = 120


@dataclass
class TestResult:
    key_idx: int
    key_label: str
    model_id: str
    ok: bool
    elapsed: float = 0.0
    message: str = ""


@dataclass
class TestProgress:
    total: int = 0
    done: int = 0
    passed: int = 0
    failed: int = 0
    results: list[TestResult] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, r: TestResult):
        with self._lock:
            self.done += 1
            if r.ok:
                self.passed += 1
            else:
                self.failed += 1
            self.results.append(r)


def _resolve_timeout(kc: ApiKeyConfig, mo: ModelOverride) -> int:
    """模型 timeout > key timeout > 120"""
    if mo.timeout is not None:
        return mo.timeout
    if kc.errors.timeout is not None:
        return kc.errors.timeout
    return DEFAULT_TEST_TIMEOUT


def _resolve_concurrency(kc: ApiKeyConfig, mo: ModelOverride) -> int:
    """有效并发: 取 key 与 model 中较小的（保守策略），None 视为不限制"""
    key_conc = kc.errors.max_concurrency
    mdl_conc = mo.max_concurrency
    if key_conc is not None and mdl_conc is not None:
        return min(key_conc, mdl_conc)
    return key_conc or mdl_conc or 1


def _wait_rate_limit(
    limiter: RateLimiter,
    scope: str,
    rules: list,
    stop_check: Optional[Callable[[], bool]],
    log: Optional[Callable[[str], None]],
    display_name: str = "",
) -> bool:
    """等待直到限速允许，返回 False 表示被中断

    Args:
        display_name: 日志中显示的名称（为空时使用 scope）
    """
    name = display_name or scope
    while True:
        if stop_check and stop_check():
            return False
        ok, wait = limiter.check(scope, rules)
        if ok:
            return True
        if log:
            log(f"  {t('tester.log.rate_limit_wait', name=name, wait=f'{wait:.1f}')}")
        # 分段 sleep 以便响应 stop_check
        remaining = wait
        while remaining > 0:
            if stop_check and stop_check():
                return False
            time.sleep(min(remaining, 0.5))
            remaining -= 0.5


def _test_single(
    kc: ApiKeyConfig,
    mid: str,
    mo: ModelOverride,
    timeout: int,
    stop_check: Optional[Callable[[], bool]],
) -> tuple[bool, float, str]:
    """测试单个 key×model，返回 (ok, elapsed, message)"""
    messages = [{"role": "user", "content": "Hi"}]
    params = {"max_tokens": 5, "temperature": 0}
    t0 = time.time()
    received = ""
    try:
        for chunk in stream_chat(
            base_url=kc.base_url,
            api_key=kc.api_key,
            model=mid,
            messages=messages,
            params=params,
            timeout=timeout,
            api_type=kc.type,
            stop_check=stop_check,
        ):
            received += chunk
            if stop_check and stop_check():
                return False, time.time() - t0, t("tester.status.interrupted")
        elapsed = time.time() - t0
        if received:
            return True, elapsed, f"{len(received)} chars"
        return False, elapsed, t("tester.status.empty_reply")
    except Exception as e:
        elapsed = time.time() - t0
        msg = str(e).split("\n")[0][:80]
        return False, elapsed, msg


def test_pool(pool_name: str, kc: ApiKeyConfig, mid: str) -> tuple[bool, str]:
    """简易单次测试（兼容 CLI 调用）

    Args:
        pool_name: 池名称（仅用于日志）
        kc:        API Key 配置
        mid:       模型 ID

    Returns:
        (ok, message)
    """
    mo = kc.models.get(mid, ModelOverride(model_id=mid))
    timeout = _resolve_timeout(kc, mo)
    ok, elapsed, msg = _test_single(kc, mid, mo, timeout, stop_check=None)
    if ok:
        return True, f"{msg} ({elapsed:.1f}s)"
    return False, f"{msg} ({elapsed:.1f}s)"


def run_pool_test(
    pool: AIPool,
    stop_check: Optional[Callable[[], bool]] = None,
    on_progress: Optional[Callable[[TestProgress, TestResult], None]] = None,
    log: Optional[Callable[[str], None]] = None,
) -> TestProgress:
    """一键测试池内所有 key×model

    - 每个 key 使用独立线程，按 max_concurrency 串行/并行测试其下的 model
    - 使用 RateLimiter 遵守 rate_limits
    - stop_check 返回 True 时中断

    Args:
        pool:       待测试的 AI 池
        stop_check: 中断检查回调
        on_progress: 每完成一个测试项的回调 (progress, result)
        log:        日志回调

    Returns:
        TestProgress 包含所有测试结果
    """
    # 收集所有待测试项
    items: list[tuple[int, ApiKeyConfig, str, ModelOverride]] = []
    for ki, kc in enumerate(pool.keys):
        for mid, mo in kc.models.items():
            items.append((ki, kc, mid, mo))

    progress = TestProgress(total=len(items))

    if not items:
        return progress

    limiter = RateLimiter()

    # 按 key 分组
    key_groups: dict[int, list[tuple[int, ApiKeyConfig, str, ModelOverride]]] = {}
    for item in items:
        ki = item[0]
        key_groups.setdefault(ki, []).append(item)

    def _test_key_group(ki: int, group: list[tuple[int, ApiKeyConfig, str, ModelOverride]]):
        kc = group[0][1]
        # 确定该 key 的并发数（取所有 model 中最小的有效并发）
        min_conc = 1
        for _, _, _, mo in group:
            c = _resolve_concurrency(kc, mo)
            min_conc = max(min_conc, c)  # 至少为 1
        # 实际上测试时每个 key 串行跑 model 最安全（不会触碰并发限制）
        # 因为大部分 key 的 max_concurrency 都是 1

        for _, _, mid, mo in group:
            if stop_check and stop_check():
                break

            timeout = _resolve_timeout(kc, mo)
            label = kc.label or kc.base_url

            # 等待 key 级限速
            if kc.rate_limits:
                scope = f"test:key:{ki}"
                if not _wait_rate_limit(limiter, scope, kc.rate_limits, stop_check, log, display_name=label):
                    break

            # 等待 model 级限速
            if mo.rate_limits:
                scope = f"test:model:{ki}:{mid}"
                if not _wait_rate_limit(limiter, scope, mo.rate_limits, stop_check, log, display_name=f"{label}/{mid}"):
                    break

            if log:
                log(f"  {t('tester.log.testing', label=label, mid=mid, timeout=timeout)}")

            ok, elapsed, msg = _test_single(kc, mid, mo, timeout, stop_check)

            # 记录限速
            if kc.rate_limits:
                limiter.record(f"test:key:{ki}")
            if mo.rate_limits:
                limiter.record(f"test:model:{ki}:{mid}")

            result = TestResult(
                key_idx=ki,
                key_label=label,
                model_id=mid,
                ok=ok,
                elapsed=elapsed,
                message=msg,
            )
            progress.add(result)
            if on_progress:
                on_progress(progress, result)

    # 每个 key 一个线程
    threads: list[threading.Thread] = []
    for ki, group in key_groups.items():
        t = threading.Thread(target=_test_key_group, args=(ki, group), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    return progress