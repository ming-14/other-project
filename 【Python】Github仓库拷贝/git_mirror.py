#!/usr/bin/env python3
"""
Git Mirror —— 增量式 Git 仓库镜像工具

架构:
  - GitBackend: 底层 git 命令封装
  - RefSet:     ref 比较引擎，算出源和目标之间的差异
  - Remote:     源/目标仓库抽象（支持 RemoteGit / LocalRepo）
  - MirrorPipeline: 主编排器，驱动 clone → diff → push → validate 流程
  - Hook:       扩展点协议，可注册自定义 hook

工作流程:
  1. 从源仓库 clone --mirror 到本地缓存目录
  2. 增量upd: 再次运行时仅 git fetch --prune
  3. 对比本地缓存与目标仓库的 ref，仅Pushing差异部分
  4. 支持验证、重试、dry-run
"""

from __future__ import annotations

import abc
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Sequence, Tuple, Type

# ===================================================================
# Log
# ===================================================================

logger = logging.getLogger("git_mirror")


def setup_logging(level: int = logging.INFO) -> None:
    """初始化Log处理器，输出到 stderr"""
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(h)
    logger.setLevel(level)


# ===================================================================
# 枚举 / 数据类型
# ===================================================================

class RefType(Enum):
    """Ref 类型：branches / tags / 其他"""
    BRANCH = "branch"
    TAG = "tag"
    OTHER = "other"


@dataclass(frozen=True)
class Ref:
    """单个 git ref 的不可变描述"""
    full: str            # 完整名称，如 refs/heads/main
    target: str          # 指向的 commit SHA
    rtype: RefType = RefType.OTHER

    @property
    def short(self) -> str:
        """返回简短名称（如 main, v1.0）"""
        _, _, name = self.full.partition("/refs/heads/")
        if name != self.full:
            return name
        _, _, name = self.full.partition("/refs/tags/")
        return name

    @classmethod
    def parse(cls, line: str) -> "Ref":
        """从 `git show-ref` / `git ls-remote` 的输出行解析"""
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            raise ValueError(f"无法解析 ref 行: {line!r}")
        sha, full = parts
        if full.startswith("refs/heads/"):
            rtype = RefType.BRANCH
        elif full.startswith("refs/tags/"):
            rtype = RefType.TAG
        else:
            rtype = RefType.OTHER
        return cls(full=full, target=sha, rtype=rtype)


# ===================================================================
# 异常
# ===================================================================

class GitError(Exception):
    """git 命令执行FAILED"""
    def __init__(self, msg: str, cmd: str = "", retcode: int = -1) -> None:
        self.cmd = cmd
        self.retcode = retcode
        detail = f" (命令: {cmd})" if cmd else ""
        detail += f" (返回码: {retcode})" if retcode != -1 else ""
        super().__init__(f"{msg}{detail}")


class RetryExhausted(GitError):
    """重试耗尽"""
    pass


class AuthError(GitError):
    """认证FAILED"""
    pass


# ===================================================================
# Hook 扩展协议
# ===================================================================

class Hook(abc.ABC):
    """所有 hook 的基类。子类覆写感兴趣stage即可。"""

    def before_clone(self, source_url: str, dest_url: str, cache_dir: str) -> None:
        ...

    def after_clone(self, source_url: str, dest_url: str, cache_dir: str) -> None:
        ...

    def before_push(self, refs: List[Ref], dest_url: str) -> None:
        ...

    def after_push(self, refs: List[Ref], dest_url: str, elapsed: float) -> None:
        ...

    def on_error(self, exc: Exception, stage: str) -> None:
        ...


@dataclass
class HookChain:
    """批量执行多个 hook 的链式容器"""
    hooks: List[Hook] = field(default_factory=list)

    def register(self, hook: Hook) -> None:
        self.hooks.append(hook)

    def __getattr__(self, name: str) -> Callable:
        """自动将所有 hook 的同名方法串联调用"""
        def _call(*args: Any, **kwargs: Any) -> None:
            for h in self.hooks:
                getattr(h, name)(*args, **kwargs)
        return _call


# ===================================================================
# 重试工具
# ===================================================================

def retry(
    fn: Callable[..., Any],
    max_attempts: int = 3,
    base_delay: float = 2.0,
    backoff: float = 2.0,
    predicate: Callable[[Exception], bool] = lambda e: True,
) -> Any:
    """指数退避重试装饰器

    - predicate: 只有满足此条件的异常才重试
    - 达到 max_attempts 后抛 RetryExhausted
    """
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt == max_attempts or not predicate(e):
                raise
            delay = base_delay * (backoff ** (attempt - 1))
            logger.warning("attempt %d/%d 次FAILED (%s)，%.1fs retrying…", attempt, max_attempts, e, delay)
            time.sleep(delay)
    raise RetryExhausted(str(last_exc))


# ===================================================================
# Git 后端（封装 subprocess）
# ===================================================================

class GitBackend:
    """系统 git 命令的轻量封装"""

    def __init__(self, git_bin: str = "git") -> None:
        self._git = git_bin
        self._env = os.environ.copy()

    # ── 内部辅助 ───────────────────────────────────────────────────

    def _run(
        self,
        args: Sequence[str],
        cwd: Optional[str] = None,
        timeout: int = 600,
        check: bool = True,
        capture: bool = True,
        input_data: Optional[bytes] = None,
    ) -> subprocess.CompletedProcess:
        """执行 git 命令，超时/返回码检查"""
        cmd = [self._git] + list(args)
        cmd_str = " ".join(cmd)
        logger.debug("执行: %s (cwd=%s)", cmd_str, cwd or ".")
        t0 = time.monotonic()
        try:
            r = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=capture,
                input=input_data,
                timeout=timeout,
                env=self._env,
            )
        except subprocess.TimeoutExpired:
            raise GitError(f"命令超时 ({timeout}s)", cmd=cmd_str)
        elapsed = time.monotonic() - t0
        if check and r.returncode != 0:
            msg = (r.stderr or b"").decode("utf-8", errors="replace").strip()
            if "Authentication failed" in msg or "Permission denied" in msg:
                raise AuthError(msg)
            raise GitError(msg or "未知Error", cmd=cmd_str, retcode=r.returncode)
        logger.debug("完成 (%.1fs, 返回 %d): %s", elapsed, r.returncode, cmd_str)
        return r

    def _lines(self, args: Sequence[str], cwd: Optional[str] = None, **kw: Any) -> List[str]:
        """执行命令并返回 stdout 的非空行列表"""
        r = self._run(args, cwd=cwd, **kw)
        return [l for l in r.stdout.decode("utf-8", errors="replace").splitlines() if l]

    # ── git 操作 ───────────────────────────────────────────────────

    def list_refs(self, repo_dir: str) -> List[Ref]:
        """列出本地仓库的所有 ref"""
        lines = self._lines(["show-ref", "--head"], cwd=repo_dir)
        return [Ref.parse(l) for l in lines]

    def list_remote_refs(self, url: str, timeout: int = 30) -> List[Ref]:
        """列出远程仓库的所有branches和tags"""
        lines = self._lines(["ls-remote", "--heads", "--tags", url], timeout=timeout)
        return [Ref.parse(l) for l in lines]

    def clone_mirror(self, url: str, target_dir: str, timeout: int = 600) -> None:
        """克隆 bare mirror 仓库"""
        self._run(["clone", "--mirror", url, target_dir], timeout=timeout)

    def fetch(self, repo_dir: str, remote: str = "origin", prune: bool = True, timeout: int = 300) -> bool:
        """增量拉取，可裁剪已del的远程branches。返回 True 表示有新数据。"""
        args = ["fetch", "--prune", "--verbose", remote] if prune else ["fetch", "--verbose", remote]
        r = self._run(args, cwd=repo_dir, timeout=timeout, check=False)
        if r.returncode != 0:
            err = (r.stderr or b"").decode("utf-8", errors="replace")
            if "couldn't find remote ref" in err:
                return False
            raise GitError(err)
        out = ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", errors="replace").strip()
        has_new = bool(out) and "FETCH_HEAD" not in out
        if has_new:
            # 提取有意义的行
            for line in out.splitlines():
                line = line.strip()
                if line and not line.startswith("From ") and "=" not in line:
                    logger.info("  fetch: %s", line)
        return has_new

    def push_refs(
        self,
        repo_dir: str,
        dest_url: str,
        refs: Sequence[Ref],
        mirror: bool = False,
        timeout: int = 300,
    ) -> None:
        """Pushing ref 到目标仓库"""
        if mirror:
            # --mirror 模式直接Pushing全部（注意 Gitee 不支持 refs/pull 等）
            self._run(["push", "--mirror", dest_url], cwd=repo_dir, timeout=timeout)
            return
        # 仅Pushingbranches和tags
        refspecs = [r.full for r in refs if r.rtype in (RefType.BRANCH, RefType.TAG)]
        if not refspecs:
            logger.info("nothing to push ref")
            return
        self._run(["push", dest_url] + refspecs, cwd=repo_dir, timeout=timeout)

    def delete_refs(self, repo_dir: str, refs: Sequence[Ref]) -> None:
        """del本地缓存中的指定 ref"""
        for r in refs:
            self._run(["update-ref", "-d", r.full], cwd=repo_dir, check=False)

    def remote_add(self, repo_dir: str, name: str, url: str) -> None:
        self._run(["remote", "add", name, url], cwd=repo_dir)

    def remote_set_url(self, repo_dir: str, name: str, url: str) -> None:
        """修改已有 remote 的 URL"""
        self._run(["remote", "set-url", name, url], cwd=repo_dir)

    def init_bare(self, path: str) -> None:
        self._run(["init", "--bare", path])

    def is_valid_repo(self, path: str) -> bool:
        """判断目录是否为有效的 git 仓库"""
        if not os.path.isdir(path):
            return False
        try:
            self._run(["rev-parse", "--git-dir"], cwd=path, capture=True)
            return True
        except GitError:
            return False


# ===================================================================
# RefSet — 差异比较引擎
# ===================================================================

class RefSet:
    """不可变的 ref 集合，支持与另一个 RefSet 做差异比较"""

    def __init__(self, refs: List[Ref]) -> None:
        self._by_name: Dict[str, Ref] = {r.full: r for r in refs}

    def __contains__(self, name: str) -> bool:
        return name in self._by_name

    def __len__(self) -> int:
        return len(self._by_name)

    def get(self, name: str) -> Optional[Ref]:
        return self._by_name.get(name)

    @property
    def all(self) -> List[Ref]:
        return list(self._by_name.values())

    def branches(self) -> List[Ref]:
        return [r for r in self.all if r.rtype == RefType.BRANCH]

    def tags(self) -> List[Ref]:
        return [r for r in self.all if r.rtype == RefType.TAG]

    def diff(self, other: "RefSet") -> "DiffResult":
        """与目标 RefSet 比较，返回需要同步的差异

        - to_add:    源有但目标没有的branches/tags
        - to_update: 源和目标都有但指向不同 commit
        - to_delete: 目标有但源已del的branches（仅当 delete_extra_branches=True）
        """
        ours = self._by_name
        theirs = other._by_name
        to_add: Dict[str, Ref] = {}
        to_update: Dict[str, Tuple[Ref, Ref]] = {}
        to_delete: List[str] = []
        for name, ref in ours.items():
            if name not in theirs and ref.rtype != RefType.OTHER:
                to_add[name] = ref
            elif name in theirs and theirs[name].target != ref.target:
                to_update[name] = (theirs[name], ref)
        for name in theirs:
            if name not in ours and name.startswith("refs/heads/"):
                to_delete.append(name)
        return DiffResult(
            to_add=list(to_add.values()),
            to_update=list(to_update.values()),
            to_delete=to_delete,
        )

    @classmethod
    def from_repo(cls, repo_dir: str, backend: GitBackend) -> "RefSet":
        return cls(backend.list_refs(repo_dir))

    @classmethod
    def from_remote(cls, url: str, backend: GitBackend, timeout: int = 30) -> "RefSet":
        return cls(backend.list_remote_refs(url, timeout=timeout))


@dataclass
class DiffResult:
    """差异比较结果"""
    to_add: List[Ref] = field(default_factory=list)                     # 需要new的 ref
    to_update: List[Tuple[Ref, Ref]] = field(default_factory=list)      # 需要upd的 ref (旧, 新)
    to_delete: List[str] = field(default_factory=list)                  # 需要del的branches名

    @property
    def total(self) -> int:
        return len(self.to_add) + len(self.to_update) + len(self.to_delete)

    @property
    def changed(self) -> List[Ref]:
        """所有changes过的 ref（new + upd后的新值）"""
        return self.to_add + [new for _, new in self.to_update]

    @property
    def all_pushable(self) -> List[Ref]:
        """可Pushing的 ref（排除 refs/other 类型）"""
        return [r for r in self.changed if r.rtype in (RefType.BRANCH, RefType.TAG)]


# ===================================================================
# 凭据工具
# ===================================================================

@dataclass
class Credential:
    """Git 远程认证凭据，可嵌入 URL"""
    username: str = ""
    password: str = ""
    token: str = ""

    def inject_url(self, raw_url: str) -> str:
        """将 token / 密码嵌入 URL 的 userinfo 部分"""
        if self.token:
            parts = raw_url.split("://", 1)
            if len(parts) == 2:
                return f"{parts[0]}://{self.token}@{parts[1]}"
        if self.username and self.password:
            from urllib.parse import quote
            parts = raw_url.split("://", 1)
            if len(parts) == 2:
                return f"{parts[0]}://{quote(self.username)}:{quote(self.password)}@{parts[1]}"
        return raw_url

    @classmethod
    def from_token(cls, token: str) -> "Credential":
        return cls(token=token)

    @classmethod
    def from_user_pass(cls, user: str, password: str) -> "Credential":
        return cls(username=user, password=password)


# ===================================================================
# 远程/本地仓库抽象
# ===================================================================

class Remote(abc.ABC):
    """仓库抽象基类（源或目标）"""

    def __init__(self, url: str) -> None:
        # URL 应已包含凭据（如 https://token@host/path）
        self._url = url

    @property
    def url(self) -> str:
        return self._url

    @abc.abstractmethod
    def list_refs(self, backend: GitBackend, timeout: int = 30) -> RefSet:
        ...

    def safe_repr(self) -> str:
        """输出时隐藏 URL 中的凭据"""
        return re.sub(r"(://)[^@]+@", r"\1***@", self._url)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.safe_repr()})"


class RemoteGit(Remote):
    """远程 Git 仓库（https/ssh/git 协议）"""

    def list_refs(self, backend: GitBackend, timeout: int = 30) -> RefSet:
        return RefSet.from_remote(self._url, backend, timeout=timeout)


class LocalRepo(Remote):
    """本地 bare 仓库"""

    def __init__(self, path: str) -> None:
        super().__init__(path)
        self._path = os.path.abspath(path)

    def list_refs(self, backend: GitBackend, timeout: int = 30) -> RefSet:
        return RefSet.from_repo(self._path, backend)

    @property
    def path(self) -> str:
        return self._path

    @property
    def url(self) -> str:
        return self._path


# ===================================================================
# 缓存管理
# ===================================================================

class CacheManager:
    """管理本地 bare mirror 缓存，实现增量同步"""

    def __init__(self, cache_root: str, backend: GitBackend) -> None:
        self._root = Path(cache_root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._backend = backend

    @staticmethod
    def _url_hash(url: str) -> str:
        """URL 的简短哈希，用于区分不同仓库的缓存"""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

    def cache_dir(self, url: str) -> str:
        """根据 URL 生成缓存目录名（可读部分 + 哈希）"""
        # 去掉协议前缀和凭据，取路径部分
        safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", url.split("://", 1)[-1].split("@")[-1])
        if len(safe) > 100:
            safe = safe[:100]
        h = self._url_hash(url)
        return str(self._root / f"{safe}_{h}")

    def ensure_mirror(self, source: Remote, timeout: int = 600) -> str:
        """保证本地有源的 bare mirror，必要时创建或增量upd

        返回值: 缓存目录路径
        """
        cache_path = self.cache_dir(source.url)
        if self._backend.is_valid_repo(cache_path):
            logger.info("增量updcache: %s", cache_path)
            self._backend.fetch(cache_path, timeout=timeout)
        else:
            logger.info("Creating cache mirror: %s → %s", source, cache_path)
            if os.path.exists(cache_path):
                shutil.rmtree(cache_path)
            self._backend.clone_mirror(source.url, cache_path, timeout=timeout)
            # 确保 origin remote 指向源仓库（--mirror 默认设置为 origin）
            self._backend.remote_set_url(cache_path, "origin", source.url)
        return cache_path

    def cleanup(self, path: str) -> None:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)


# ===================================================================
# Pipeline — 主编排器
# ===================================================================

@dataclass
class MirrorConfig:
    """镜像配置"""
    source_url: str                                         # 源仓库 URL（已含凭据）
    dest_url: str                                           # 目标仓库 URL（已含凭据）
    cache_root: str = ""                                    # 缓存目录；空则使用系统临时目录
    git_bin: str = "git"                                    # git 可执行文件路径
    timeout_clone: int = 600                                # 克隆超时（秒）
    timeout_fetch: int = 300                                # 增量拉取超时
    timeout_push: int = 300                                 # Pushing超时
    timeout_ls_remote: int = 30                             # 列举远程 ref 超时
    max_retries: int = 3                                    # 每个stage最大Retries
    delete_extra_branches: bool = False                     # 是否del目标已不存在的branches
    hooks: HookChain = field(default_factory=HookChain)    # hook 链
    dry_run: bool = False                                   # 只算差异，不gotPushing
    validate_after: bool = False                            # Pushing后校验


class MirrorPipeline:
    """镜像流程编排器"""

    def __init__(self, config: MirrorConfig) -> None:
        self.cfg = config
        self._backend = GitBackend(config.git_bin)
        self._source: Remote = RemoteGit(config.source_url)
        self._dest: Remote = RemoteGit(config.dest_url)
        cache_root = config.cache_root or os.path.join(tempfile.gettempdir(), "git_mirror_cache")
        self._cache = CacheManager(cache_root, self._backend)

    # ── 公开入口 ───────────────────────────────────────────────────

    def run(self) -> MirrorReport:
        """执行镜像流程，返回报告"""
        t_start = time.monotonic()
        report = MirrorReport(source=self.cfg.source_url, dest=self.cfg.dest_url)
        stage = "clone"
        try:
            # 1) 克隆/upd缓存
            self.cfg.hooks.before_clone(self.cfg.source_url, self.cfg.dest_url,
                                        self._cache.cache_dir(self.cfg.source_url))
            t_clone = time.monotonic()
            cache_dir = retry(
                lambda: self._cache.ensure_mirror(self._source, timeout=self.cfg.timeout_clone),
                max_attempts=self.cfg.max_retries,
                predicate=lambda e: isinstance(e, (GitError, subprocess.TimeoutExpired)),
            )
            report.clone_elapsed = time.monotonic() - t_clone
            report.cache_dir = cache_dir
            # 判断是首次还是增量
            report.is_new_cache = not self._backend.is_valid_repo(cache_dir)
            self.cfg.hooks.after_clone(self.cfg.source_url, self.cfg.dest_url, cache_dir)

            # 2) 比较 ref 差异
            stage = "diff"
            diff = self._compute_diff(cache_dir)
            report.diff = diff
            logger.info("  diff: +%d new, +%d upd, -%d del, 共 %d 个changes",
                        len(diff.to_add), len(diff.to_update), len(diff.to_delete), diff.total)

            if diff.total == 0:
                logger.info("  [OK] up-to-date，skipPushing")
                report.total_elapsed = time.monotonic() - t_start
                report.success = True
                return report

            # 3) 可选清理stale branches
            stage = "cleanup"
            if self.cfg.delete_extra_branches and diff.to_delete:
                stale_refs = [Ref(full=n, target="") for n in diff.to_delete]
                self._backend.delete_refs(cache_dir, stale_refs)
                logger.info("  [OK] 已del %d 个stale branches", len(stale_refs))

            # 4) Pushing
            stage = "push"
            pushable = diff.all_pushable
            if not pushable:
                logger.info("  [OK] 没有需Pushing的branches/tags")
                report.total_elapsed = time.monotonic() - t_start
                report.success = True
                return report

            self.cfg.hooks.before_push(pushable, self.cfg.dest_url)
            t_push = time.monotonic()

            if not self.cfg.dry_run:
                retry(
                    lambda: self._backend.push_refs(cache_dir, self._dest.url, pushable,
                                                    timeout=self.cfg.timeout_push),
                    max_attempts=self.cfg.max_retries,
                    predicate=lambda e: isinstance(e, (GitError, subprocess.TimeoutExpired)),
                )

            report.push_elapsed = time.monotonic() - t_push
            report.pushed = len(pushable)
            self.cfg.hooks.after_push(pushable, self.cfg.dest_url, report.push_elapsed)
            report.success = True

            # 5) 可选验证
            if self.cfg.validate_after:
                stage = "validate"
                self._validate(cache_dir)

        except Exception as exc:
            report.error = str(exc)
            report.stage_failed = stage
            self.cfg.hooks.on_error(exc, stage)
            logger.error("  Mirror FAILED (stage: '%s'): %s", stage, exc)

        report.total_elapsed = time.monotonic() - t_start
        return report

    # ── 内部方法 ────────────────────────────────────────────────────

    def _compute_diff(self, cache_dir: str) -> DiffResult:
        """计算本地缓存与目标仓库的 ref 差异"""
        try:
            dest_refs = retry(
                lambda: RefSet.from_remote(self._dest.url, self._backend,
                                           timeout=self.cfg.timeout_ls_remote),
                max_attempts=self.cfg.max_retries,
            )
        except AuthError:
            logger.warning("cannot list dest refs (auth?), assuming empty")
            dest_refs = RefSet([])
        except GitError as e:
            logger.warning("cannot list dest refs (%s)，assuming empty", e)
            dest_refs = RefSet([])

        source_refs = RefSet.from_repo(cache_dir, self._backend)
        return source_refs.diff(dest_refs)

    def _validate(self, cache_dir: str) -> None:
        """校验：对比本地缓存和目标仓库的每个 ref"""
        logger.info("Validating…")
        src = RefSet.from_repo(cache_dir, self._backend)
        try:
            dst = RefSet.from_remote(self._dest.url, self._backend,
                                     timeout=self.cfg.timeout_ls_remote)
        except GitError:
            logger.warning("校验skip —— cannot query dest")
            return
        for ref in src.all:
            d = dst.get(ref.full)
            if d is None:
                logger.warning("MISSING on dest: %s", ref.full)
            elif d.target != ref.target:
                logger.warning("MISMATCH on dest: %s (expected %s, got %s)",
                               ref.full, ref.target[:12], d.target[:12])
        logger.info("Validation complete")


# ===================================================================
# 报告
# ===================================================================

@dataclass
class MirrorReport:
    """镜像操作报告"""
    source: str = ""
    dest: str = ""
    success: bool = False
    cache_dir: str = ""
    diff: Optional[DiffResult] = None
    pushed: int = 0
    push_elapsed: float = 0.0
    error: str = ""
    stage_failed: str = ""
    total_elapsed: float = 0.0
    clone_elapsed: float = 0.0
    is_new_cache: bool = False

    def summary(self) -> str:
        """人类可读的单行摘要（纯 ASCII）"""
        if not self.success:
            return f"[FAIL] stage='{self.stage_failed}': {self.error}"
        parts = []
        if self.pushed > 0:
            parts.append(f"pushed {self.pushed} refs ({self.push_elapsed:.1f}s)")
        else:
            parts.append("up-to-date")
        if self.diff and self.diff.total > 0:
            parts.append(f"+{len(self.diff.to_add)}/-{len(self.diff.to_delete)} diff")
        parts.append(f"total {self.total_elapsed:.1f}s")
        return "[OK] " + ", ".join(parts)

    def block(self) -> str:
        """多行格式，适合Log（纯 ASCII，兼容 GBK 终端）"""
        if not self.success:
            return f"  [FAIL] {self.error}"
        name = self.source.split("/")[-1]
        lines = [f"  [OK]   {name}"]
        if self.diff and self.diff.total > 0:
            a, u, d = len(self.diff.to_add), len(self.diff.to_update), len(self.diff.to_delete)
            lines.append(f"         diff: +{a} new +{u} upd -{d} del")
        if self.pushed > 0:
            lines.append(f"         push: {self.pushed} refs, {self.push_elapsed:.1f}s")
        else:
            lines.append(f"         sync: up-to-date (skip)")
        feat = "full-clone" if self.is_new_cache else "incr-fetch"
        lines.append(f"         cache: {feat}, {self.clone_elapsed:.1f}s")
        lines.append(f"         total: {self.total_elapsed:.1f}s")
        return "\n".join(lines)


# ===================================================================
# 内置 Hook 实现
# ===================================================================

class LoggingHook(Hook):
    """详细的Log记录 hook"""
    def __init__(self) -> None:
        self._t0 = 0.0

    def before_clone(self, source_url: str, dest_url: str, cache_dir: str) -> None:
        self._t0 = time.monotonic()
        safe_src = re.sub(r"(://)[^@]+@", r"\1***@", source_url)
        safe_dst = re.sub(r"(://)[^@]+@", r"\1***@", dest_url)
        logger.info("")
        logger.info(">>> Mirror: %s", safe_src)
        logger.info("    -> %s", safe_dst)
        logger.info("    cache: %s", cache_dir)

    def after_clone(self, source_url: str, dest_url: str, cache_dir: str) -> None:
        elapsed = time.monotonic() - self._t0
        logger.info("  [OK] Source ready (%.1fs)", elapsed)

    def before_push(self, refs: List[Ref], dest_url: str) -> None:
        self._t_push = time.monotonic()
        branches = [r.short for r in refs if r.rtype == RefType.BRANCH]
        tags = [r.short for r in refs if r.rtype == RefType.TAG]
        parts = []
        if branches:
            parts.append(f"{len(branches)} branches")
        if tags:
            parts.append(f"{len(tags)} tags")
        logger.info("  >  Pushing %s: %s", ", ".join(parts), ", ".join(branches[:8] + tags[:8]))
        if len(branches) > 8 or len(tags) > 8:
            logger.info("    ... 共 %d 个 ref", len(refs))

    def after_push(self, refs: List[Ref], dest_url: str, elapsed: float) -> None:
        rate = f"{len(refs)/elapsed:.1f} refs/s" if elapsed > 0 else "N/A"
        logger.info("  [OK] Pushing完成 (%.1fs, %s)", elapsed, rate)

    def on_error(self, exc: Exception, stage: str) -> None:
        logger.error("  [X] stage '%s' FAILED: %s", stage, exc)


class StatsHook(Hook):
    """统计 hook（对象计数等）"""
    def after_push(self, refs: List[Ref], dest_url: str, elapsed: float) -> None:
        if elapsed > 0:
            logger.debug("吞吐量: ~%.2f refs/s", len(refs) / elapsed)


class NotifierHook(Hook):
    """回调通知 hook"""
    def __init__(self, on_done: Callable[[MirrorReport], None]) -> None:
        self._cb = on_done
    def on_error(self, exc: Exception, stage: str) -> None:
        pass


# ===================================================================
# 平台 API — 列举 / 创建仓库
# ===================================================================

def list_github_repos(username: str, token: str = "") -> List[Dict[str, Any]]:
    """通过 GitHub API 列举用户的所有仓库（含private）"""
    import requests
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    repos: List[Dict[str, Any]] = []
    page = 1
    while True:
        r = requests.get(
            f"https://api.github.com/users/{username}/repos",
            params={"per_page": 100, "page": page, "type": "all"},
            headers=headers,
            timeout=30,
        )
        if r.status_code == 403:
            logger.warning("GitHub API 限流，等待重试…")
            time.sleep(60)
            continue
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos


def list_gitee_repos(username: str, token: str) -> List[Dict[str, Any]]:
    """通过 Gitee API 列举用户的所有仓库（用 token 所属用户身份查询）"""
    import requests
    repos: List[Dict[str, Any]] = []
    page = 1
    while True:
        r = requests.get(
            "https://gitee.com/api/v5/user/repos",
            params={"access_token": token, "per_page": 100, "page": page},
            timeout=30,
        )
        if r.status_code == 403:
            logger.warning("Gitee API 限流，等待重试…")
            time.sleep(60)
            continue
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        repos.extend(data)
        page += 1
    return repos


def ensure_gitee_repo(name: str, token: str, owner: str, private: bool = True) -> bool:
    """在 Gitee 上创建仓库（如果不存在），返回是否已存在"""
    import requests
    # 先检查是否已存在
    r = requests.get(
        f"https://gitee.com/api/v5/repos/{owner}/{name}",
        params={"access_token": token},
        timeout=15,
    )
    if r.status_code == 200:
        return True  # 已存在
    # 创建
    r = requests.post(
        "https://gitee.com/api/v5/user/repos",
        data={
            "access_token": token,
            "name": name,
            "private": "true" if private else "false",
        },
        timeout=15,
    )
    if r.status_code == 201:
        logger.info("Gitee repo created: %s", name)
        return False
    elif r.status_code == 422:
        # 可能已存在（竞态）
        logger.warning("Gitee repo create returned 422, may exist already: %s", name)
        return True
    else:
        logger.error("Gitee repo create FAILED %s: %s", name, r.text)
        r.raise_for_status()
        return False


# ===================================================================
# 批量镜像编排器
# ===================================================================

class BatchMirror:
    """批量镜像：将 GitHub user的所有仓库镜像到 Gitee"""

    def __init__(
        self,
        github_username: str,
        gitee_username: str,
        github_token: str = "",
        gitee_token: str = "",
        cache_root: str = "",
        git_bin: str = "git",
        hooks: Optional[HookChain] = None,
        dry_run: bool = False,
        delete_extra: bool = False,
        max_retries: int = 3,
        timeout_clone: int = 600,
        timeout_fetch: int = 300,
        timeout_push: int = 300,
        timeout_ls: int = 30,
        skip_existing_on_gitee: bool = True,
    ) -> None:
        self._gh_user = github_username
        self._gl_user = gitee_username
        self._gh_token = github_token
        self._gl_token = gitee_token
        self._cache_root = cache_root or os.path.join(tempfile.gettempdir(), "git_mirror_cache")
        self._git_bin = git_bin
        self._hooks = hooks or HookChain()
        self._dry_run = dry_run
        self._delete_extra = delete_extra
        self._max_retries = max_retries
        self._timeout_clone = timeout_clone
        self._timeout_fetch = timeout_fetch
        self._timeout_push = timeout_push
        self._timeout_ls = timeout_ls
        self._skip_existing = skip_existing_on_gitee
        self._on_repo_start: Optional[Callable[[int, str], None]] = None

    def run(self) -> List[MirrorReport]:
        """执行批量镜像，返回每repos的报告列表"""
        t_batch = time.monotonic()
        sep = "=" * 60
        logger.info("")
        logger.info(sep)
        logger.info("  批量Mirror: GitHub/%s → Gitee/%s", self._gh_user, self._gl_user)
        logger.info(sep)

        # 1) 列举 GitHub 仓库
        logger.info(">  列举 GitHub 仓库…")
        gh_repos = list_github_repos(self._gh_user, self._gh_token)
        gh_size = sum(r.get("size", 0) for r in gh_repos)
        logger.info("  [OK] GitHub user %s: %d repos (总计 ~%d MB)",
                    self._gh_user, len(gh_repos), gh_size)

        if not gh_repos:
            logger.warning("  No repos found")
            return []

        # 2) 列举 Gitee 已有仓库
        logger.info(">  列举 Gitee 仓库…")
        gl_repos = list_gitee_repos(self._gl_user, self._gl_token)
        gl_names = {r["name"] for r in gl_repos}
        need_create = [r["name"] for r in gh_repos if r["name"] not in gl_names]
        already_have = len(gh_repos) - len(need_create)
        logger.info("  [OK] Gitee user %s: %d repos", self._gl_user, len(gl_repos))
        logger.info("  >  need create: %d  |  exists: %d  |  总计: %d",
                    len(need_create), already_have, len(gh_repos))

        if need_create:
            logger.info("  to create: %s", ", ".join(need_create))

        logger.info(sep)
        logger.info("Mirroring repos one by one:")
        logger.info(sep)

        # 3) 逐个镜像
        reports: List[MirrorReport] = []
        gh_repos.sort(key=lambda r: r["name"])
        t_repo_start = time.monotonic()
        ok_count = 0
        fail_count = 0

        for i, repo in enumerate(gh_repos, 1):
            name = repo["name"]
            is_private = repo.get("private", False)
            size_mb = repo.get("size", 0)
            lang = repo.get("language") or ""
            exists_mark = "[EXISTS]" if name in gl_names else "[NEW]"

            # 回调通知 GUI
            if self._on_repo_start:
                self._on_repo_start(i, name)

            # 进度头
            logger.info("")
            logger.info("  [%d/%d] %s %s  (%d MB%s%s)",
                        i, len(gh_repos), exists_mark, name, size_mb,
                        f", {lang}" if lang else "",
                        ", private" if is_private else "")

            # 在 Gitee 创建（如果需要）
            if name not in gl_names:
                logger.info("  → Not on Gitee, creating…")
                if not self._dry_run:
                    ensure_gitee_repo(name, self._gl_token, self._gl_user, private=is_private)
                gl_names.add(name)
            else:
                logger.info("  → Already on Gitee")

            # 运行单仓库镜像
            gh_url = f"https://github.com/{self._gh_user}/{name}.git"
            gl_url = f"https://gitee.com/{self._gl_user}/{name}.git"
            if self._gh_token:
                gh_url = Credential.from_token(self._gh_token).inject_url(gh_url)
            if self._gl_token:
                gl_url = Credential.from_token(self._gl_token).inject_url(gl_url)

            config = MirrorConfig(
                source_url=gh_url,
                dest_url=gl_url,
                cache_root=self._cache_root,
                git_bin=self._git_bin,
                timeout_clone=self._timeout_clone,
                timeout_fetch=self._timeout_fetch,
                timeout_push=self._timeout_push,
                timeout_ls_remote=self._timeout_ls,
                max_retries=self._max_retries,
                delete_extra_branches=self._delete_extra,
                hooks=self._hooks,
                dry_run=self._dry_run,
            )
            pipeline = MirrorPipeline(config)
            report = pipeline.run()
            report.source = f"{self._gh_user}/{name}"
            report.dest = f"{self._gl_user}/{name}"
            reports.append(report)

            # 单仓库结果
            for line in report.block().splitlines():
                logger.info("  %s", line)

            if report.success:
                ok_count += 1
            else:
                fail_count += 1
                logger.error("  [X] FAILED: %s", report.error)

            # ETA时间
            elapsed = time.monotonic() - t_repo_start
            avg = elapsed / i
            remaining = avg * (len(gh_repos) - i)
            logger.info("  progress: %d/%d  |  elapsed %s  |  ETA %s",
                        i, len(gh_repos), _fmt_duration(elapsed), _fmt_duration(remaining))

        # 统计
        t_total = time.monotonic() - t_batch
        logger.info("")
        logger.info(sep)
        logger.info("  批量Mirror complete")
        logger.info(sep)
        logger.info("  仓库:  %d 总  |  %d [OK] OK  |  %d [X] FAILED",
                    len(reports), ok_count, fail_count)
        total_pushed = sum(r.pushed for r in reports)
        total_fetched = sum(1 for r in reports if r.diff and r.diff.total == 0)
        logger.info("  Pushing:  %d refs  |  %d 个up-to-date (skip)", total_pushed, total_fetched)
        logger.info("  耗时:  %s", _fmt_duration(t_total))
        rate = len(reports) / t_total if t_total > 0 else 0
        logger.info("  速率:  ~%.1f 仓库/分钟", rate * 60)
        logger.info(sep)

        return reports


def _fmt_duration(seconds: float) -> str:
    """格式化持续时间为 时:分:秒"""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    return f"{m}m{s:02d}s"


# ===================================================================
# CLI
# ===================================================================

def build_cli_parser() -> Any:
    import argparse
    p = argparse.ArgumentParser(description="增量式 Git 仓库镜像 (源 → 目标)")
    p.add_argument("source", nargs="?", help="源仓库 URL（单仓库模式），或 GitHub user名（配合 --batch）")
    p.add_argument("destination", nargs="?", help="目标仓库 URL（单仓库模式），或 Gitee user名（配合 --batch）")
    p.add_argument("--token", "-t", help="访问令牌")
    p.add_argument("--src-token", help="源仓库令牌（默认同 --token）")
    p.add_argument("--dst-token", help="目标仓库令牌（默认同 --token）")
    p.add_argument("--batch", "-b", action="store_true", help="批量模式: 将 GitHub user所有仓库镜像到 Gitee")
    p.add_argument("--gh-user", help="GitHub user名（批量模式）")
    p.add_argument("--gl-user", help="Gitee user名（批量模式）")
    p.add_argument("--gh-token", help="GitHub 令牌（批量模式）")
    p.add_argument("--gl-token", help="Gitee 令牌（批量模式）")
    p.add_argument("--cache", default="", help="本地 bare mirror 缓存目录")
    p.add_argument("--git", default="git", help="git 可执行文件路径")
    p.add_argument("--dry-run", action="store_true", help="仅计算差异，不Pushing")
    p.add_argument("--validate", action="store_true", help="Pushing后校验一致性（单仓库模式）")
    p.add_argument("--delete", action="store_true", help="del目标上已不存在的branches")
    p.add_argument("--verbose", "-v", action="store_true", help="调试Log")
    p.add_argument("--retries", type=int, default=3, help="每stage最大Retries (默认 3)")
    p.add_argument("--timeout-clone", type=int, default=600, help="克隆超时 (秒)")
    p.add_argument("--timeout-fetch", type=int, default=300, help="增量拉取超时")
    p.add_argument("--timeout-push", type=int, default=300, help="Pushing超时")
    p.add_argument("--timeout-ls", type=int, default=30, help="远程 ref 列举超时")
    p.add_argument("--json", action="store_true", help="以 JSON 格式输出报告")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    setup_logging(logging.DEBUG if args.verbose else logging.INFO)

    hooks = HookChain()
    hooks.register(LoggingHook())
    hooks.register(StatsHook())

    # ── 批量模式 ──
    if args.batch or args.gh_user:
        gh_user = args.gh_user or args.source
        gl_user = args.gl_user or args.destination
        if not gh_user or not gl_user:
            parser.error("批量模式需要 --gh-user 和 --gl-user（或 source/destination 参数）")

        gh_token = args.gh_token or args.src_token or args.token or os.environ.get("GITHUB_TOKEN", "")
        gl_token = args.gl_token or args.dst_token or args.token or os.environ.get("GITEE_TOKEN", "")

        batcher = BatchMirror(
            github_username=gh_user,
            gitee_username=gl_user,
            github_token=gh_token,
            gitee_token=gl_token,
            cache_root=args.cache,
            git_bin=args.git,
            hooks=hooks,
            dry_run=args.dry_run,
            delete_extra=args.delete,
            max_retries=args.retries,
            timeout_clone=args.timeout_clone,
            timeout_fetch=args.timeout_fetch,
            timeout_push=args.timeout_push,
            timeout_ls=args.timeout_ls,
        )
        reports = batcher.run()

        ok = sum(1 for r in reports if r.success)
        fail = sum(1 for r in reports if not r.success)

        if args.json:
            print(json.dumps({
                "total": len(reports),
                "success": ok,
                "failed": fail,
                "reports": [
                    {
                        "name": r.source,
                        "success": r.success,
                        "pushed": r.pushed,
                        "error": r.error,
                        "stage": r.stage_failed,
                    }
                    for r in reports
                ],
            }, indent=2))
        else:
            print()
            print("=" * 60)
            print(f"  批量镜像结果: {ok} OK, {fail} FAILED, 共 {len(reports)} 仓库")
            print("=" * 60)
            for r in reports:
                icon = "[OK]" if r.success else "[X]"
                print(f"  {icon} {r.source}: {r.summary()}")
            print()

        return 0 if fail == 0 else 1

    # ── 单仓库模式 ──
    if not args.source or not args.destination:
        parser.error("单仓库模式需要 source 和 destination 参数")

    token = args.token or os.environ.get("GIT_MIRROR_TOKEN", "")
    src_token = args.src_token or token
    dst_token = args.dst_token or token

    source_url = Credential.from_token(src_token).inject_url(args.source) if src_token else args.source
    dest_url = Credential.from_token(dst_token).inject_url(args.destination) if dst_token else args.destination

    config = MirrorConfig(
        source_url=source_url,
        dest_url=dest_url,
        cache_root=args.cache,
        git_bin=args.git,
        timeout_clone=args.timeout_clone,
        timeout_fetch=args.timeout_fetch,
        timeout_push=args.timeout_push,
        timeout_ls_remote=args.timeout_ls,
        max_retries=args.retries,
        delete_extra_branches=args.delete,
        hooks=hooks,
        dry_run=args.dry_run,
        validate_after=args.validate,
    )

    pipeline = MirrorPipeline(config)
    report = pipeline.run()

    if args.json:
        d = {
            "success": report.success,
            "source": report.source,
            "dest": report.dest,
            "pushed": report.pushed,
            "push_elapsed_s": round(report.push_elapsed, 2),
            "error": report.error,
            "stage": report.stage_failed,
        }
        if report.diff:
            d["diff"] = {
                "added": len(report.diff.to_add),
                "updated": len(report.diff.to_update),
                "deleted": len(report.diff.to_delete),
            }
        print(json.dumps(d, indent=2))
    else:
        print(report.summary())

    return 0 if report.success else 1


if __name__ == "__main__":
    sys.exit(main())
