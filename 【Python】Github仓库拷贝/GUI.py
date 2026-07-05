#!/usr/bin/env python3
"""
Git Mirror GUI —— 图形化增量镜像工具

支持:
  - Single repo: source URL -> dest URL
  - Batch:   GitHub 用户 → Gitee 用户（auto-mirror all repos）
"""

from __future__ import annotations

import json
import logging
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, List, Optional

# 将同目录加入 path，以便导入 git_mirror
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from git_mirror import (
    BatchMirror,
    Credential,
    Hook,
    HookChain,
    LoggingHook,
    MirrorConfig,
    MirrorPipeline,
    MirrorReport,
    Ref,
    StatsHook,
    setup_logging,
)


# ===================================================================
# Log重定向到 GUI
# ===================================================================

class GUILogHandler(logging.Handler):
    """Redirects log to tkinter Text widget（带颜色）"""

    COLORS = {
        "DEBUG": ("#888888", ""),
        "INFO": ("#d4d4d4", ""),
        "WARNING": ("#ffcc00", "WARNING"),
        "ERROR": ("#ff5555", "ERROR"),
        "CRITICAL": ("#ffffff", "ERROR"),
    }

    def __init__(self, text_widget: tk.Text, level: int = logging.INFO) -> None:
        super().__init__(level)
        self._text = text_widget
        self._queue: queue.Queue = queue.Queue()
        self._poll_interval = 50

        # 初始配置标签
        for tag, (fg, bg) in self.COLORS.items():
            self._text.tag_configure(tag, foreground=fg)

    def emit(self, record: logging.LogRecord) -> None:
        self._queue.put(record)
        try:
            self._text.after(self._poll_interval, self._poll)
        except tk.TclError:
            pass

    def _poll(self) -> None:
        try:
            while True:
                record = self._queue.get_nowait()
                msg = self.format(record)
                level = record.levelname
                tag = level if level in self.COLORS else "INFO"
                self._text.configure(state="normal")
                self._text.insert(tk.END, msg + "\n", tag)
                self._text.see(tk.END)
                self._text.configure(state="disabled")
        except queue.Empty:
            pass


# ===================================================================
# 进度 Hook
# ===================================================================

class ProgressHook(Hook):
    """Updates progress bar and status"""

    def __init__(self, progress: ttk.Progressbar, status_var: tk.StringVar) -> None:
        self._progress = progress
        self._status = status_var
        self._current_repo: str = ""

    def set_repo(self, name: str) -> None:
        self._current_repo = name

    def before_clone(self, source_url: str, dest_url: str, cache_dir: str) -> None:
        name = self._current_repo or source_url.split("/")[-1].replace(".git", "")
        self._status.set(f"[down] Fetch: {name}")
        self._progress.start(15)

    def after_clone(self, source_url: str, dest_url: str, cache_dir: str) -> None:
        self._progress.stop()

    def before_push(self, refs: list, dest_url: str) -> None:
        branches = sum(1 for r in refs if r.rtype == Ref.Type.BRANCH)
        tags = sum(1 for r in refs if r.rtype == Ref.Type.TAG)
        name = self._current_repo or "?"
        self._status.set(f"[up] Pushing {name}: {branches} 分支, {tags} 标签")
        self._progress.start(10)

    def after_push(self, refs: list, dest_url: str, elapsed: float) -> None:
        self._progress.stop()

    def on_error(self, exc: Exception, stage: str) -> None:
        self._progress.stop()
        name = self._current_repo or ""
        self._status.set(f"[X] {name} FAILED (阶段: {stage})")


# ===================================================================
# 主窗口
# ===================================================================

class GitMirrorGUI:

    CONFIG_FILE = os.path.join(_script_dir, "gui_config.json")

    def __init__(self) -> None:
        self._root = tk.Tk()
        self._root.title("Git Mirror — 增量仓库镜像工具")
        self._root.geometry("820x720")
        self._root.minsize(680, 560)

        self._build_ui()
        self._running = False
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI 构建 ─────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._root.columnconfigure(0, weight=1)
        self._root.rowconfigure(1, weight=1)

        title = ttk.Label(self._root, text="Git Mirror", font=("", 14, "bold"))
        title.grid(row=0, column=0, pady=(8, 2))

        # 笔记本: Single / 批量
        self._notebook = ttk.Notebook(self._root)
        self._notebook.grid(row=1, column=0, sticky="nsew", padx=6)

        self._build_single_tab()
        self._build_batch_tab()

        # 公共: 进度 + 按钮 + Log
        self._build_common_area()

    # ── Single标签页 ────────────────────────────────────────────────

    def _build_single_tab(self) -> None:
        tab = ttk.Frame(self._notebook, padding=8)
        self._notebook.add(tab, text=" Single ")
        tab.columnconfigure(1, weight=1)

        # 源
        f_src = ttk.LabelFrame(tab, text="Source", padding=6)
        f_src.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        f_src.columnconfigure(1, weight=1)
        ttk.Label(f_src, text="URL:").grid(row=0, column=0, sticky="w")
        self._src_url = ttk.Entry(f_src)
        self._src_url.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self._src_url.insert(0, "https://github.com/ming-14/link-url.git")
        ttk.Label(f_src, text="Token:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self._src_token = ttk.Entry(f_src, show="*")
        self._src_token.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(4, 0))
        self._src_token.insert(0, os.environ.get("GITHUB_TOKEN", ""))

        # 目标
        f_dst = ttk.LabelFrame(tab, text="Destination", padding=6)
        f_dst.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        f_dst.columnconfigure(1, weight=1)
        ttk.Label(f_dst, text="URL:").grid(row=0, column=0, sticky="w")
        self._dst_url = ttk.Entry(f_dst)
        self._dst_url.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self._dst_url.insert(0, "https://gitee.com/Gitee-CHN/link-url.git")
        ttk.Label(f_dst, text="Token:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self._dst_token = ttk.Entry(f_dst, show="*")
        self._dst_token.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(4, 0))
        self._dst_token.insert(0, os.environ.get("GITEE_TOKEN", ""))

        # Options
        self._single_opts = self._build_options_frame(tab, row=2)

    # ── 批量标签页 ──────────────────────────────────────────────────

    def _build_batch_tab(self) -> None:
        tab = ttk.Frame(self._notebook, padding=8)
        self._notebook.add(tab, text=" Batch ")
        tab.columnconfigure(1, weight=1)

        # GitHub
        f_gh = ttk.LabelFrame(tab, text="GitHub (source)", padding=6)
        f_gh.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        f_gh.columnconfigure(1, weight=1)
        ttk.Label(f_gh, text="Username:").grid(row=0, column=0, sticky="w")
        self._gh_user = ttk.Entry(f_gh)
        self._gh_user.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self._gh_user.insert(0, "ming-14")
        ttk.Label(f_gh, text="Token:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self._gh_token = ttk.Entry(f_gh, show="*")
        self._gh_token.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(4, 0))
        self._gh_token.insert(0, os.environ.get("GITHUB_TOKEN", ""))

        # Gitee
        f_gl = ttk.LabelFrame(tab, text="Gitee (dest)", padding=6)
        f_gl.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        f_gl.columnconfigure(1, weight=1)
        ttk.Label(f_gl, text="Username:").grid(row=0, column=0, sticky="w")
        self._gl_user = ttk.Entry(f_gl)
        self._gl_user.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self._gl_user.insert(0, "Gitee-CHN")
        ttk.Label(f_gl, text="Token:").grid(row=1, column=0, sticky="w", pady=(4, 0))
        self._gl_token = ttk.Entry(f_gl, show="*")
        self._gl_token.grid(row=1, column=1, sticky="ew", padx=(4, 0), pady=(4, 0))
        self._gl_token.insert(0, os.environ.get("GITEE_TOKEN", ""))

        # Options
        self._batch_opts = self._build_options_frame(tab, row=2)

    # ── Options框架（共享） ────────────────────────────────────────────

    def _build_options_frame(self, parent: ttk.Frame, row: int) -> dict:
        f = ttk.LabelFrame(parent, text="Options", padding=6)
        f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        f.columnconfigure(3, weight=1)

        dry_run = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Dry-run (dry-run)", variable=dry_run).grid(row=0, column=0, sticky="w", padx=(0, 12))

        delete = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Delete extra branches", variable=delete).grid(row=0, column=1, sticky="w", padx=(0, 12))

        ttk.Label(f, text="Retries:").grid(row=0, column=2, sticky="e", padx=(12, 4))
        retries = ttk.Spinbox(f, from_=0, to=10, width=4)
        retries.insert(0, "3")
        retries.grid(row=0, column=3, sticky="w")

        return {"dry_run": dry_run, "delete": delete, "retries": retries}

    # ── 公共区域 ────────────────────────────────────────────────────

    def _build_common_area(self) -> None:
        # 进度
        f_prog = ttk.Frame(self._root, padding=(6, 0))
        f_prog.grid(row=2, column=0, sticky="ew")
        f_prog.columnconfigure(1, weight=1)
        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(f_prog, textvariable=self._status_var).grid(row=0, column=0, sticky="w")
        self._progress = ttk.Progressbar(f_prog, mode="indeterminate", length=200)
        self._progress.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        # 按钮
        f_btn = ttk.Frame(self._root, padding=(6, 4))
        f_btn.grid(row=3, column=0, sticky="ew")
        self._btn_run = ttk.Button(f_btn, text=">  Run", command=self._run)
        self._btn_run.pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(f_btn, text="Clear log", command=self._clear_log).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(f_btn, text="Save config", command=self._save_config).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(f_btn, text="Load config", command=self._load_config).pack(side=tk.LEFT)

        # Log
        f_log = ttk.LabelFrame(self._root, text="Log", padding=4)
        f_log.grid(row=4, column=0, sticky="nsew", padx=6, pady=(4, 6))
        self._root.rowconfigure(4, weight=1)
        f_log.columnconfigure(0, weight=1)
        f_log.rowconfigure(0, weight=1)
        self._log_text = tk.Text(f_log, height=15, wrap=tk.WORD, state="disabled",
                                 bg="#1e1e1e", fg="#d4d4d4", insertbackground="white",
                                 font=("Consolas", 10))
        self._log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(f_log, orient=tk.VERTICAL, command=self._log_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self._log_text.configure(yscrollcommand=scroll.set)

        # 状态栏
        self._status_bar = ttk.Label(self._root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self._status_bar.grid(row=5, column=0, sticky="ew")

        self._root.bind("<Control-Return>", lambda e: self._run())

    # ── Run ────────────────────────────────────────────────────────

    def _run(self) -> None:
        if self._running:
            messagebox.showinfo("Info", "Already running，please wait")
            return

        tab = self._notebook.index(self._notebook.select())
        if tab == 0:
            self._run_single()
        else:
            self._run_batch()

    def _run_single(self) -> None:
        src = self._src_url.get().strip()
        dst = self._dst_url.get().strip()
        if not src or not dst:
            messagebox.showerror("Error", "Enter source and dest URLs")
            return

        opts = self._single_opts
        try:
            retries = int(opts["retries"].get())
        except ValueError:
            retries = 3

        self._set_running(True)
        t = threading.Thread(
            target=self._single_thread,
            args=(src, dst, self._src_token.get(), self._dst_token.get(), retries,
                  opts["dry_run"].get(), opts["delete"].get()),
            daemon=True,
        )
        t.start()

    def _run_batch(self) -> None:
        gh_user = self._gh_user.get().strip()
        gl_user = self._gl_user.get().strip()
        if not gh_user or not gl_user:
            messagebox.showerror("Error", "Enter GitHub and Gitee usernames")
            return

        opts = self._batch_opts
        try:
            retries = int(opts["retries"].get())
        except ValueError:
            retries = 3

        self._set_running(True)
        t = threading.Thread(
            target=self._batch_thread,
            args=(gh_user, gl_user, self._gh_token.get(), self._gl_token.get(),
                  retries, opts["dry_run"].get(), opts["delete"].get()),
            daemon=True,
        )
        t.start()

    # ── 后台线程 ────────────────────────────────────────────────────

    def _single_thread(
        self, src_url: str, dst_url: str,
        src_token: str, dst_token: str,
        retries: int, dry_run: bool, delete: bool,
    ) -> None:
        try:
            source = Credential.from_token(src_token).inject_url(src_url) if src_token else src_url
            dest = Credential.from_token(dst_token).inject_url(dst_url) if dst_token else dst_url

            hooks = HookChain()
            hooks.register(ProgressHook(self._progress, self._status_var))

            config = MirrorConfig(
                source_url=source,
                dest_url=dest,
                max_retries=retries,
                delete_extra_branches=delete,
                dry_run=dry_run,
                hooks=hooks,
            )
            pipeline = MirrorPipeline(config)
            report = pipeline.run()
            self._root.after(0, self._on_single_done, report)
        except Exception as e:
            self._root.after(0, self._on_error, str(e))

    def _batch_thread(
        self, gh_user: str, gl_user: str,
        gh_token: str, gl_token: str,
        retries: int, dry_run: bool, delete: bool,
    ) -> None:
        try:
            progress_hook = ProgressHook(self._progress, self._status_var)
            hooks = HookChain()
            hooks.register(progress_hook)

            batcher = BatchMirror(
                github_username=gh_user,
                gitee_username=gl_user,
                github_token=gh_token,
                gitee_token=gl_token,
                hooks=hooks,
                dry_run=dry_run,
                delete_extra=delete,
                max_retries=retries,
            )
            # 每处理一 repos时更新 GUI 状态
            batcher._on_repo_start = lambda i, name: self._root.after(
                0, lambda i=i, name=name: self._status_var.set(f"[{i}] {name}")
            )
            reports = batcher.run()
            self._root.after(0, self._on_batch_done, reports)
        except Exception as e:
            self._root.after(0, self._on_error, str(e))

    # ── 回调 ────────────────────────────────────────────────────────

    def _set_running(self, running: bool) -> None:
        self._running = running
        if running:
            self._btn_run.configure(state="disabled", text="⏳ Run中…")
            self._status_var.set("Preparing…")
        else:
            self._btn_run.configure(state="normal", text=">  Run")
            self._status_var.set("Ready")

    def _on_single_done(self, report: MirrorReport) -> None:
        self._set_running(False)
        self._status_bar.configure(text=report.summary())
        tag = "INFO" if report.success else "ERROR"
        self._log_insert(tag, f"\n{'='*50}\n{report.summary()}\n{'='*50}\n")

    def _on_batch_done(self, reports: List[MirrorReport]) -> None:
        self._set_running(False)
        ok = sum(1 for r in reports if r.success)
        fail = sum(1 for r in reports if not r.success)
        summary = f"Batch complete: {ok} OK, {fail} FAILED, 共 {len(reports)} 仓库"
        self._status_bar.configure(text=summary)
        self._log_insert("INFO", f"\n{'='*50}\n{summary}\n{'='*50}\n")
        for r in reports:
            tag = "INFO" if r.success else "ERROR"
            self._log_insert(tag, f"  {'[OK]' if r.success else '[X]'} {r.source}: {r.summary()}\n")

    def _on_error(self, msg: str) -> None:
        self._set_running(False)
        self._status_bar.configure(text=f"[X] 异常: {msg}")
        self._log_insert("ERROR", f"\n{'='*50}\n异常: {msg}\n{'='*50}\n")
        messagebox.showerror("Error", msg)

    def _log_insert(self, tag: str, msg: str) -> None:
        try:
            self._log_text.configure(state="normal")
            self._log_text.insert(tk.END, msg, tag)
            self._log_text.see(tk.END)
            self._log_text.configure(state="disabled")
        except tk.TclError:
            pass

    def _clear_log(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", tk.END)
        self._log_text.configure(state="disabled")
        self._status_var.set("已Cleared")

    # ── 配置持久化 ───────────────────────────────────────────────────

    def _save_config(self) -> None:
        data = {
            "single": {
                "src_url": self._src_url.get(),
                "src_token": self._src_token.get(),
                "dst_url": self._dst_url.get(),
                "dst_token": self._dst_token.get(),
                "dry_run": self._single_opts["dry_run"].get(),
                "delete": self._single_opts["delete"].get(),
                "retries": self._single_opts["retries"].get(),
            },
            "batch": {
                "gh_user": self._gh_user.get(),
                "gh_token": self._gh_token.get(),
                "gl_user": self._gl_user.get(),
                "gl_token": self._gl_token.get(),
                "dry_run": self._batch_opts["dry_run"].get(),
                "delete": self._batch_opts["delete"].get(),
                "retries": self._batch_opts["retries"].get(),
            },
        }
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=2)
            self._status_bar.configure(text="[OK] Config saved")
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    def _load_config(self) -> None:
        if not os.path.isfile(self.CONFIG_FILE):
            messagebox.showinfo("Info", "No config file found")
            return
        try:
            with open(self.CONFIG_FILE) as f:
                data = json.load(f)
            s = data.get("single", {})
            self._src_url.delete(0, tk.END)
            self._src_url.insert(0, s.get("src_url", ""))
            self._src_token.delete(0, tk.END)
            self._src_token.insert(0, s.get("src_token", ""))
            self._dst_url.delete(0, tk.END)
            self._dst_url.insert(0, s.get("dst_url", ""))
            self._dst_token.delete(0, tk.END)
            self._dst_token.insert(0, s.get("dst_token", ""))
            self._single_opts["dry_run"].set(s.get("dry_run", False))
            self._single_opts["delete"].set(s.get("delete", False))
            self._single_opts["retries"].delete(0, tk.END)
            self._single_opts["retries"].insert(0, str(s.get("retries", "3")))

            b = data.get("batch", {})
            self._gh_user.delete(0, tk.END)
            self._gh_user.insert(0, b.get("gh_user", ""))
            self._gh_token.delete(0, tk.END)
            self._gh_token.insert(0, b.get("gh_token", ""))
            self._gl_user.delete(0, tk.END)
            self._gl_user.insert(0, b.get("gl_user", ""))
            self._gl_token.delete(0, tk.END)
            self._gl_token.insert(0, b.get("gl_token", ""))
            self._batch_opts["dry_run"].set(b.get("dry_run", False))
            self._batch_opts["delete"].set(b.get("delete", False))
            self._batch_opts["retries"].delete(0, tk.END)
            self._batch_opts["retries"].insert(0, str(b.get("retries", "3")))

            self._status_bar.configure(text="[OK] Config loaded")
        except Exception as e:
            messagebox.showerror("Load failed", str(e))

    # ── 窗口关闭 ─────────────────────────────────────────────────────

    def _on_close(self) -> None:
        if self._running:
            if not messagebox.askyesno("Confirm", "镜像正在Run，Exit?？"):
                return
        self._root.destroy()

    # ── 启动 ─────────────────────────────────────────────────────────

    def run(self) -> None:
        self._root.mainloop()


# ===================================================================
# 入口
# ===================================================================

def main() -> int:
    setup_logging(logging.WARNING)
    gui = GitMirrorGUI()

    handler = GUILogHandler(gui._log_text, logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                           datefmt="%H:%M:%S"))
    logging.getLogger("git_mirror").addHandler(handler)

    gui.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
