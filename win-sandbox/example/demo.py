"""win-sandbox 示例脚本

用法:
    python example/demo.py        # 默认：弹出可见 cmd 窗口（Low IL + Job 内）
    python example/demo.py --pipe # 管道模式：headless，输出通过管道捕获

自动加载 pyd 的优先级:
    1. example/ 目录（与脚本同目录，方便独立部署）
    2. ../build/bin/（开发构建产物）
"""

from __future__ import annotations

import os
import sys
import time

# 强制 UTF-8 输出（Windows 控制台可能按 ANSI 代码页检测，中文会乱码）
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── 1. 找 pyd ──────────────────────────────────────────────────────────────────
_script_dir = os.path.dirname(os.path.abspath(__file__))
_pyd_dirs = []

# 优先级 1：当前目录（example/）
_pyd_dirs.append(_script_dir)

# 优先级 2：回退 ../build/bin/
_build_bin = os.path.join(_script_dir, "..", "build", "bin")
_build_bin = os.path.abspath(_build_bin)
if os.path.isdir(_build_bin):
    _pyd_dirs.append(_build_bin)

# 把 pyd 目录加到 sys.path（import 时 Python 会自动匹配带 ABI tag 的 .pyd）
# 注意：insert(0) 会让后插入的排更前，必须逆序遍历，最高优先级最后插入
for d in reversed(_pyd_dirs):
    if d not in sys.path:
        sys.path.insert(0, d)

# 把 python/ 包目录加到 sys.path（让 import win_sandbox 能找到包）
_pkg_dir = os.path.join(_script_dir, "..", "python")
_pkg_dir = os.path.abspath(_pkg_dir)
if os.path.isdir(_pkg_dir) and _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

# ── 2. 导入 ─────────────────────────────────────────────────────────────────────
import win_sandbox


# ── 3. 辅助 ─────────────────────────────────────────────────────────────────────
def drain_stdout(proc, timeout_ms: int = 8000) -> bytes:
    """排空 stdout 管道，超时返回已读到的数据"""
    chunks: list[bytes] = []
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        try:
            data = win_sandbox.read_pipe(proc.stdout_handle, 4096)
            if not data:
                break
            chunks.append(data)
        except Exception:
            break
        time.sleep(0.01)
    return b"".join(chunks)


# ── 4. 主流程 ───────────────────────────────────────────────────────────────────
def main():
    # 默认弹窗模式；--pipe 切回管道模式（headless）
    pipe_mode = "--pipe" in sys.argv

    print("=" * 55)
    print("  win-sandbox 示例")
    print("=" * 55)

    # 4a. 创建沙箱实例
    sb = win_sandbox.SandboxInstance(log_level="warn")
    print(f"\n  ├ 沙箱实例已创建")
    print(f"  ├ 权限能力: {sb.capabilities['mode']}")
    for cap in sb.capabilities["capabilities"]:
        ok = "[OK]" if cap["available"] else "[--]"
        print(f"  │   {ok} {cap['module']}")

    # 4b. 启动进程
    if pipe_mode:
        # ── 管道模式（--pipe，headless）──
        # 输出通过管道捕获，不弹窗
        print(f"\n  ├ 正在启动沙箱进程…")
        proc = sb.start_process(
            command_line="cmd.exe /c echo Hello from win-sandbox! & echo. & whoami /groups",
            interactive=True,
        )
        print(f"  ├ PID = {proc.pid}")

        # 排空 stdout
        stdout = drain_stdout(proc, timeout_ms=5000)
        if stdout:
            text = stdout.decode("utf-8", "replace")
            print(f"  │")
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                if "Mandatory" in line or "完整性" in line:
                    print(f"  │   ⚑  {line}")
                elif "S-1-16" in line:
                    print(f"  │   ⚑  {line.strip()}")
                else:
                    print(f"  │   {line}")

    else:
        # ── 弹窗模式（默认）──
        # cmd /c start cmd /k 技巧：弹出真实可见的 cmd 窗口
        # 新窗口中的进程是 Low IL + 在 Job 内，隔离完整
        # 注意：窗口的 stdin/stdout 不经过沙箱管道
        print(f"\n  ├ 正在弹出可见 cmd 窗口…")
        proc = sb.start_process(
            command_line="cmd.exe /c start cmd /k",
            interactive=True,
        )
        print(f"  ├ 窗口进程 PID = {proc.pid}")
        print(f"  ├ 窗口显示在桌面上，请在里面试试 whoami /groups")
        print(f"  ├ 这窗口里的进程是 Low IL + 全盘只读的")
        print(f"  ├ 在窗口里输入 exit 或直接点 × 关闭，脚本才会结束")
        print(f"  │")

        # 父 cmd 执行 start 后立即退出；真正弹窗的 cmd 还挂在 Job 内。
        # 轮询 Job 内进程列表，直到用户关闭窗口（Job 内进程清空）。
        while True:
            time.sleep(1)
            try:
                pids = proc.query_process_list()
            except Exception:
                pids = []
            if not pids:
                break
        print(f"  ├ 窗口已关闭")

    # 4c. 等待退出
    print(f"  │")
    ec, reason, usage = proc.wait(timeout_ms=15000)
    print(f"  ├ 退出码: {ec}   原因: {reason}")
    if usage:
        mem = usage.get("memory", {}).get("peak_process_bytes", 0)
        cpu = usage.get("cpu", {})
        print(f"  ├ 峰值内存: {mem:,} bytes")
        print(f"  ├ CPU 时间: user={cpu.get('total_user_ms',0)}ms kernel={cpu.get('total_kernel_ms',0)}ms")

    # 4d. 关闭沙箱
    sb.shutdown()
    print(f"  └ 沙箱已关闭")
    print(f"\n{'=' * 55}")
    print(f"  完成")
    print(f"{'=' * 55}")


if __name__ == "__main__":
    main()