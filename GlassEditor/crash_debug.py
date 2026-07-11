# -*- coding: utf-8 -*-
"""
@file        crash_debug.py
@brief       崩溃调试启动器
@details     包装 src/main.py 启动主程序，捕获所有崩溃类型：
             - Python未捕获异常 (sys.excepthook)
             - C层致命信号 SIGSEGV/SIGABRT/SIGBUS (faulthandler)
             - 主线程卡死未响应 (看门狗线程)
             - 子线程静默崩溃

             崩溃后弹窗提示而非直接退出，崩溃信息写入crash_YYYY-MM-DD.log

使用方法：
    python crash_debug.py          # 启动程序（带崩溃调试）
    python crash_debug.py --watch  # 启动程序 + 实时监控crash日志
    python crash_debug.py --monitor # 进程监控模式（崩溃自动重启）
"""

import sys
import os
import time
import signal
import threading
import traceback
import faulthandler
import atexit
import subprocess
import datetime

_current_dir = os.path.dirname(os.path.abspath(__file__))
_logs_dir = os.path.join(_current_dir, 'logs')
_watchdog_timeout = 30

_crash_info = None
_crash_lock = threading.Lock()


def _get_crash_log_path():
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    return os.path.join(_logs_dir, f'crash_{today}.log')


def _write_crash_log(title, content):
    """立刻写入崩溃日志到crash_YYYY-MM-DD.log（不用logger，防止循环依赖）"""
    os.makedirs(_logs_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    crash_log_path = _get_crash_log_path()
    try:
        with open(crash_log_path, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"[{timestamp}] CRASH [{title}]\n")
            f.write(f"{'='*60}\n")
            f.write(content)
            f.write(f"\n{'='*60}\n\n")
    except Exception:
        pass

    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        log_path = os.path.join(_logs_dir, f'{today}.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] [ERROR] [CrashDebug] {title}\n")
            for line in content.strip().split('\n')[:20]:
                f.write(f"[{timestamp}] [ERROR] [CrashDebug]   {line}\n")
    except Exception:
        pass


def _record_crash(title, detail):
    """记录崩溃信息供弹窗使用"""
    global _crash_info
    with _crash_lock:
        _crash_info = (title, detail)


def _show_crash_dialog(title, detail):
    """使用Win32 API弹窗（不依赖Qt，因为Qt可能已崩溃）"""
    try:
        import ctypes
        MB_ICONERROR = 0x10
        MB_TASKMODAL = 0x2000
        MB_SETFOREGROUND = 0x10000
        msg = f"GlassEditor 发生崩溃！\n\n类型: {title}\n\n详情:\n{detail[:500]}"
        if len(detail) > 500:
            msg += f"\n... (共{len(detail)}字符，详见crash日志)"
        msg += f"\n\n崩溃日志: {_get_crash_log_path()}"
        ctypes.windll.user32.MessageBoxW(
            0, msg, "GlassEditor 崩溃报告",
            MB_ICONERROR | MB_TASKMODAL | MB_SETFOREGROUND
        )
    except Exception:
        print(f"\n{'='*60}")
        print(f"  GlassEditor 崩溃: {title}")
        print(f"  详情: {detail[:300]}")
        print(f"  崩溃日志: {_get_crash_log_path()}")
        print(f"{'='*60}")


def _collect_thread_info():
    """收集所有线程的详细信息"""
    lines = []
    lines.append(f"活跃线程: {threading.active_count()}")
    lines.append("线程列表:")
    for t in threading.enumerate():
        frame = sys._current_frames().get(t.ident)
        if frame:
            stack = ''.join(traceback.format_stack(frame))
            short_stack = stack.strip().split('\n')[-2].strip() if stack.strip() else '?'
        else:
            short_stack = '(no frame)'
        lines.append(f"  - {t.name} (daemon={t.daemon}, alive={t.is_alive()}) => {short_stack}")
    return '\n'.join(lines)


def _setup_crash_handlers():
    """注册所有崩溃捕获处理器"""

    try:
        os.makedirs(_logs_dir, exist_ok=True)
        crash_fd = os.open(
            _get_crash_log_path(),
            os.O_WRONLY | os.O_CREAT | os.O_APPEND
        )
        faulthandler.enable(file=crash_fd, all_threads=True)
        atexit.register(os.close, crash_fd)
    except Exception:
        faulthandler.enable()

    _original_excepthook = sys.excepthook

    def crash_handler(exc_type, exc_value, exc_tb):
        if exc_type is SystemExit:
            _original_excepthook(exc_type, exc_value, exc_tb)
            return

        tb_text = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        thread_info = _collect_thread_info()
        full_content = f"{tb_text}\n{thread_info}"

        title = f'Python异常: {exc_type.__name__}: {str(exc_value)[:100]}'
        _write_crash_log(title, full_content)
        _record_crash(title, tb_text)
        _original_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = crash_handler

    def threading_exception_hook(args):
        tb_text = ''.join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        thread_info = _collect_thread_info()
        full_content = f"线程: {args.thread.name}\n{tb_text}\n{thread_info}"

        title = f'子线程异常 [{args.thread.name}]: {args.exc_type.__name__}'
        _write_crash_log(title, full_content)
        _record_crash(title, f"线程 {args.thread.name}: {tb_text}")

    if hasattr(threading, 'excepthook'):
        threading.excepthook = threading_exception_hook

    try:
        def sig_handler(sig, frame):
            sig_name = signal.Signals(sig).name if hasattr(signal, 'Signals') else str(sig)
            stack = ''.join(traceback.format_stack(frame))
            thread_info = _collect_thread_info()
            full_content = f"信号: {sig_name}\n主线程堆栈:\n{stack}\n{thread_info}"

            title = f'致命信号: {sig_name}'
            _write_crash_log(title, full_content)
            _record_crash(title, stack)

        for sig in (signal.SIGSEGV, signal.SIGABRT, signal.SIGBUS, signal.SIGFPE, signal.SIGILL):
            try:
                signal.signal(sig, sig_handler)
            except (OSError, ValueError):
                pass
    except Exception:
        pass

    def on_exit():
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        try:
            with open(_get_crash_log_path(), 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] Process exited normally\n")
        except Exception:
            pass

    atexit.register(on_exit)


class WatchdogThread(threading.Thread):
    """
    @class  WatchdogThread
    @brief  看门狗线程，检测主线程卡死
    @details 识别Qt事件循环正常等待，仅对真正的卡死报警
    """

    _KNOWN_IDLE_PATTERNS = [
        'app.exec_', 'QApplication.exec', 'QEventLoop',
        'QCoreApplication.exec', 'exec_',
        'WaitForSingleObject', 'WaitForMultipleObjects',
        'NtWaitForSingleObject', 'MsgWaitForMultipleObjects',
        'QEventDispatcherWin::processEvents',
    ]

    def __init__(self, main_thread_id, timeout=30):
        super().__init__(daemon=True)
        self._main_thread_id = main_thread_id
        self._timeout = timeout
        self._stop_event = threading.Event()
        self._tick = 0
        self._last_responsive_tick = 0
        self._hang_reported = False

    def _is_idle_stack(self, stack):
        """判断堆栈是否是正常的Qt事件循环等待"""
        for pattern in self._KNOWN_IDLE_PATTERNS:
            if pattern in stack:
                return True
        return False

    def run(self):
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._timeout)
            if self._stop_event.is_set():
                break

            self._tick += 1

            try:
                frame = sys._current_frames().get(self._main_thread_id)
                if frame:
                    stack = ''.join(traceback.format_stack(frame))

                    if self._is_idle_stack(stack):
                        self._last_responsive_tick = self._tick
                        self._hang_reported = False
                        continue

                    unresponsive_time = (self._tick - self._last_responsive_tick) * self._timeout

                    if unresponsive_time >= self._timeout * 2 and not self._hang_reported:
                        thread_info = _collect_thread_info()
                        self._hang_reported = True
                        _write_crash_log(
                            f'主线程可能卡死 (无响应>{unresponsive_time}s)',
                            f"主线程堆栈:\n{stack}\n{thread_info}"
                        )
                else:
                    self._last_responsive_tick = self._tick
            except Exception:
                self._last_responsive_tick = self._tick

    def notify_alive(self):
        """主线程调用此方法重置看门狗计时"""
        self._last_responsive_tick = self._tick

    def stop(self):
        self._stop_event.set()


def _try_qt_message_box(title, detail):
    """尝试用Qt弹窗（更美观），失败则回退到Win32"""
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        if app is None:
            return False

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("GlassEditor 崩溃报告")
        msg_box.setText("GlassEditor 发生崩溃！")

        info = f"类型: {title}\n\n详情:\n{detail[:800]}"
        if len(detail) > 800:
            info += f"\n... (共{len(detail)}字符)"
        msg_box.setInformativeText(info)

        msg_box.setDetailedText(detail)
        msg_box.exec_()
        return True
    except Exception:
        return False


def run_with_debug():
    """以调试模式启动主程序"""
    print("=" * 60)
    print("  崩溃调试模式启动")
    print(f"  崩溃日志: {_get_crash_log_path()}")
    print(f"  看门狗超时: {_watchdog_timeout}s")
    print("=" * 60)

    _setup_crash_handlers()

    env_info = (
        f"PID={os.getpid()}\n"
        f"Python={sys.version}\n"
        f"CWD={os.getcwd()}\n"
        f"Args={sys.argv}\n"
        f"Platform={sys.platform}\n"
        f"Time={datetime.datetime.now().isoformat()}"
    )
    _write_crash_log('调试启动', env_info)

    main_thread_id = threading.current_thread().ident
    watchdog = WatchdogThread(main_thread_id, timeout=_watchdog_timeout)
    watchdog.start()

    crash_title = None
    crash_detail = None

    try:
        sys.path.insert(0, _current_dir)
        sys.path.insert(0, os.path.join(_current_dir, 'src'))
        from src.main import main
        main()
    except SystemExit as e:
        if e.code not in (0, None):
            crash_title = f'SystemExit({e.code})'
            crash_detail = f'Exit code: {e.code}\n非零退出码可能表示异常退出'
            _write_crash_log(crash_title, crash_detail)
            _record_crash(crash_title, crash_detail)
        else:
            _write_crash_log('正常退出', f'Exit code: {e.code}')
    except KeyboardInterrupt:
        crash_title = 'KeyboardInterrupt'
        crash_detail = '用户按Ctrl+C中断'
        _write_crash_log(crash_title, crash_detail)
        _record_crash(crash_title, crash_detail)
    except Exception as e:
        tb_text = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        thread_info = _collect_thread_info()
        crash_title = f'{type(e).__name__}: {str(e)[:100]}'
        crash_detail = f"{tb_text}\n{thread_info}"
        _write_crash_log(f'启动异常: {crash_title}', crash_detail)
        _record_crash(crash_title, crash_detail)
    finally:
        watchdog.stop()
        watchdog.join(timeout=5)

        with _crash_lock:
            if _crash_info is not None:
                crash_title, crash_detail = _crash_info

    if crash_title is not None:
        if not _try_qt_message_box(crash_title, crash_detail):
            _show_crash_dialog(crash_title, crash_detail)


def run_as_launcher():
    """作为子进程启动器运行，监控子进程崩溃并自动重启"""
    print("=" * 60)
    print("  进程监控模式启动")
    print(f"  崩溃日志: {_get_crash_log_path()}")
    print("  子程序崩溃将自动重启（最多3次）")
    print("=" * 60)

    _setup_crash_handlers()

    max_restarts = 3
    restart_count = 0

    while restart_count <= max_restarts:
        if restart_count > 0:
            print(f"\n  等待3秒后重启 ({restart_count}/{max_restarts})...")
            time.sleep(3)

        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"\n  [{timestamp}] 启动子进程...")

        try:
            proc = subprocess.run(
                [sys.executable, os.path.join(_current_dir, 'crash_debug.py')],
                cwd=_current_dir,
                timeout=None
            )

            if proc.returncode == 0:
                print("  子进程正常退出")
                break
            else:
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                _write_crash_log(
                    f'子进程异常退出 (code={proc.returncode})',
                    f'PID: unknown\nReturn code: {proc.returncode}\nRestart: {restart_count + 1}/{max_restarts}'
                )
                print(f"  [{timestamp}] 子进程异常退出 (code={proc.returncode})")
                restart_count += 1

        except subprocess.TimeoutExpired:
            _write_crash_log('子进程超时', f'子进程运行超时被终止')
            print("  子进程超时被终止")
            restart_count += 1
        except KeyboardInterrupt:
            print("\n  用户中断，停止监控")
            break

    if restart_count > max_restarts:
        print(f"\n  已达最大重启次数({max_restarts})，停止")
        _write_crash_log('达到最大重启次数', f'max_restarts={max_restarts}')


def tail_crash_log():
    """实时监控crash_YYYY-MM-DD.log输出"""
    crash_log_path = _get_crash_log_path()
    print(f"实时监控: {crash_log_path}")
    print("按Ctrl+C停止\n")

    if not os.path.exists(crash_log_path):
        open(crash_log_path, 'w').close()

    with open(crash_log_path, 'r', encoding='utf-8') as f:
        f.seek(0, 2)
        while True:
            line = f.readline()
            if line:
                print(line.rstrip())
            else:
                time.sleep(0.5)


if __name__ == "__main__":
    if '--watch' in sys.argv:
        watch_thread = threading.Thread(target=tail_crash_log, daemon=True)
        watch_thread.start()

    if '--monitor' in sys.argv:
        run_as_launcher()
    else:
        run_with_debug()
