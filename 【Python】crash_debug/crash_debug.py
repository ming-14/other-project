# -*- coding: utf-8 -*-
"""
@file        crash_debug.py
@brief       General-purpose crash debugger (decoupled)
@details     Captures all crash types:
             - Uncaught Python exceptions (sys.excepthook)
             - C-level fatal signals SIGSEGV/SIGABRT/SIGBUS (faulthandler)
             - Windows SEH structured exceptions: AV, div-by-zero, stack overflow, etc. (UEF)
             - Main thread hang (watchdog thread)
             - Silent subthread crashes

             Shows crash dialog on crash, writes crash info to crash.log

Usage:
    python crash_debug.py <module>              # Run specified module
    python crash_debug.py <module>:<function>   # Run specified function in module
    python crash_debug.py <module> [args...]    # Pass extra arguments

    Examples:
    python crash_debug.py run                   # Run run.py
    python crash_debug.py run:main              # Run main() in run.py
    python crash_debug.py app --port 8080       # Run app.py with --port 8080
"""

import sys
import os
import time
import signal
import threading
import traceback
import faulthandler
import atexit
import datetime

_current_dir = os.path.dirname(os.path.abspath(__file__))
_logs_dir = os.path.join(_current_dir, 'logs')
_watchdog_timeout = 30

_crash_info = None
_crash_lock = threading.Lock()

_original_excepthook = None
_original_threading_excepthook = None
_original_sig_handlers = {}
_watchdog = None
_installed = False


def _get_crash_log_path():
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    return os.path.join(_logs_dir, f'crash_{today}.log')


def _write_crash_log(title, content):
    timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    crash_log_path = _get_crash_log_path()
    try:
        os.makedirs(_logs_dir, exist_ok=True)
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
    global _crash_info
    with _crash_lock:
        _crash_info = (title, detail)


def _show_crash_dialog(title, detail):
    try:
        import ctypes
        MB_ICONERROR = 0x10
        MB_TASKMODAL = 0x2000
        MB_SETFOREGROUND = 0x10000
        msg = f"Program crashed!\n\nType: {title}\n\nDetails:\n{detail[:500]}"
        if len(detail) > 500:
            msg += f"\n... ({len(detail)} chars total, see crash log)"
        msg += f"\n\nCrash log: {_get_crash_log_path()}"
        ctypes.windll.user32.MessageBoxW(
            0, msg, "Crash Report",
            MB_ICONERROR | MB_TASKMODAL | MB_SETFOREGROUND
        )
    except BaseException:
        try:
            print(f"\n{'='*60}")
            print(f"  CRASH: {title}")
            print(f"  Details: {detail[:300]}")
            print(f"  Crash log: {_get_crash_log_path()}")
            print(f"{'='*60}")
        except BaseException:
            pass


def _collect_thread_info():
    try:
        lines = []
        lines.append(f"Active threads: {threading.active_count()}")
        lines.append("Thread list:")
        for t in threading.enumerate():
            try:
                frame = sys._current_frames().get(t.ident)
                if frame:
                    stack = ''.join(traceback.format_stack(frame))
                    short_stack = stack.strip().split('\n')[-2].strip() if stack.strip() else '?'
                else:
                    short_stack = '(no frame)'
            except Exception:
                short_stack = '(failed to collect)'
            lines.append(f"  - {t.name} (daemon={t.daemon}, alive={t.is_alive()}) => {short_stack}")
        return '\n'.join(lines)
    except BaseException:
        return '(failed to collect thread info)'


def _setup_windows_uef():
    if sys.platform != 'win32':
        return

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32

    _SEH_NAMES = {
        0xC0000005: 'ACCESS_VIOLATION',
        0xC000001D: 'ILLEGAL_INSTRUCTION',
        0xC0000025: 'NONCONTINUABLE_EXCEPTION',
        0xC0000026: 'INVALID_DISPOSITION',
        0xC000008C: 'ARRAY_BOUNDS_EXCEEDED',
        0xC000008D: 'FLT_DENORMAL_OPERAND',
        0xC000008E: 'FLT_DIVIDE_BY_ZERO',
        0xC000008F: 'FLT_INEXACT_RESULT',
        0xC0000090: 'FLT_INVALID_OPERATION',
        0xC0000091: 'FLT_OVERFLOW',
        0xC0000092: 'FLT_STACK_CHECK',
        0xC0000093: 'FLT_UNDERFLOW',
        0xC0000094: 'INT_DIVIDE_BY_ZERO',
        0xC0000095: 'INT_OVERFLOW',
        0xC0000096: 'PRIV_INSTRUCTION',
        0xC00000FD: 'STACK_OVERFLOW',
        0xC0000006: 'IN_PAGE_ERROR',
        0xC0000008: 'INVALID_HANDLE',
        0x80000003: 'BREAKPOINT',
        0x80000001: 'GUARD_PAGE',
    }

    _MessageBoxW = user32.MessageBoxW

    @ctypes.CFUNCTYPE(wintypes.LONG, ctypes.c_void_p)
    def uef_filter(exception_pointers):
        try:
            er_ptr = ctypes.c_void_p()
            ctypes.memmove(ctypes.byref(er_ptr), exception_pointers, ctypes.sizeof(ctypes.c_void_p))
            code_val = 0
            addr_val = 0
            if er_ptr.value:
                code = wintypes.DWORD()
                ctypes.memmove(ctypes.byref(code), er_ptr.value, 4)
                code_val = code.value
                addr = ctypes.c_void_p()
                ctypes.memmove(ctypes.byref(addr), er_ptr.value + 16, ctypes.sizeof(ctypes.c_void_p))
                addr_val = addr.value
            name = _SEH_NAMES.get(code_val, f'UNKNOWN(0x{code_val:08X})')

            detail = (
                f"Exception code: 0x{code_val:08X} ({name})\n"
                f"Exception address: 0x{addr_val:016X}\n"
            )
            _write_crash_log(f'Unhandled SEH exception: {name}', detail)
            _record_crash(f'Unhandled SEH exception: {name}', detail)

            msg = f"Unhandled C-level exception ({name}), process will exit.\nSee crash log for details."
            _MessageBoxW(0, msg, "Crash Report", 0x10 | 0x2000 | 0x10000)
        except BaseException:
            pass
        return 1

    SetUnhandledExceptionFilter = kernel32.SetUnhandledExceptionFilter
    SetUnhandledExceptionFilter.restype = ctypes.c_void_p
    SetUnhandledExceptionFilter.argtypes = [ctypes.c_void_p]

    try:
        SetUnhandledExceptionFilter(uef_filter)
    except BaseException:
        pass


class WatchdogThread(threading.Thread):
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
                            f'Main thread may be stuck (no response for {unresponsive_time}s)',
                            f"Main thread stack:\n{stack}\n{thread_info}"
                        )
                else:
                    self._last_responsive_tick = self._tick
            except BaseException:
                self._last_responsive_tick = self._tick

    def stop(self):
        self._stop_event.set()


def install(app_name=None, watchdog_timeout=30):
    """
    Install the crash debugger. Call at program entry point.

    Args:
        app_name: Application name for dialog title. Default "Crash Report".
        watchdog_timeout: Watchdog timeout in seconds. 0 = disable watchdog.
    """
    global _original_excepthook, _original_threading_excepthook, _watchdog, _installed

    if _installed:
        return
    _installed = True

    _setup_windows_uef()

    try:
        crash_fd = open(_get_crash_log_path(), 'a', encoding='utf-8')
        faulthandler.enable(file=crash_fd, all_threads=True)
        atexit.register(crash_fd.close)
    except Exception:
        faulthandler.enable()

    _original_excepthook = sys.excepthook

    def crash_handler(exc_type, exc_value, exc_tb):
        try:
            if exc_type is SystemExit:
                _original_excepthook(exc_type, exc_value, exc_tb)
                return

            tb_text = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
            thread_info = _collect_thread_info()
            full_content = f"{tb_text}\n{thread_info}"

            title = f'Python exception: {exc_type.__name__}: {str(exc_value)[:100]}'
            _write_crash_log(title, full_content)
            _record_crash(title, tb_text)
        except Exception:
            pass
        _original_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = crash_handler

    if hasattr(threading, 'excepthook'):
        _original_threading_excepthook = threading.excepthook

        def threading_exception_hook(args):
            try:
                tb_text = ''.join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
                thread_info = _collect_thread_info()
                full_content = f"Thread: {args.thread.name}\n{tb_text}\n{thread_info}"

                title = f'Subthread exception [{args.thread.name}]: {args.exc_type.__name__}'
                _write_crash_log(title, full_content)
                _record_crash(title, f"Thread {args.thread.name}: {tb_text}")
            except Exception:
                pass

        threading.excepthook = threading_exception_hook

    try:
        def sig_handler(sig, frame):
            try:
                sig_name = signal.Signals(sig).name if hasattr(signal, 'Signals') else str(sig)
                stack = ''.join(traceback.format_stack(frame))
                thread_info = _collect_thread_info()
                full_content = f"Signal: {sig_name}\nMain thread stack:\n{stack}\n{thread_info}"

                title = f'Fatal signal: {sig_name}'
                _write_crash_log(title, full_content)
                _record_crash(title, stack)
            except Exception:
                pass

        for sig in (signal.SIGSEGV, signal.SIGABRT, signal.SIGBUS, signal.SIGFPE, signal.SIGILL):
            try:
                _original_sig_handlers[sig] = signal.getsignal(sig)
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
        except BaseException:
            pass

    atexit.register(on_exit)

    if watchdog_timeout > 0:
        _watchdog = WatchdogThread(threading.current_thread().ident, timeout=watchdog_timeout)
        _watchdog.start()

    env_info = (
        f"PID={os.getpid()}\n"
        f"Python={sys.version}\n"
        f"CWD={os.getcwd()}\n"
        f"Args={sys.argv}\n"
        f"Platform={sys.platform}\n"
        f"Time={datetime.datetime.now().isoformat()}"
    )
    _write_crash_log('Debugger started', env_info)


def uninstall():
    """Uninstall crash debugger, restore original handlers."""
    global _original_excepthook, _original_threading_excepthook, _watchdog, _installed

    if not _installed:
        return

    if _original_excepthook is not None:
        sys.excepthook = _original_excepthook
        _original_excepthook = None

    if _original_threading_excepthook is not None and hasattr(threading, 'excepthook'):
        threading.excepthook = _original_threading_excepthook
        _original_threading_excepthook = None

    for sig, handler in _original_sig_handlers.items():
        try:
            signal.signal(sig, handler)
        except (OSError, ValueError):
            pass
    _original_sig_handlers.clear()

    if _watchdog is not None:
        _watchdog.stop()
        _watchdog.join(timeout=5)
        _watchdog = None

    _installed = False


def show_last_crash():
    """Show the last recorded crash, if any."""
    with _crash_lock:
        if _crash_info is None:
            print("No crashes recorded.")
            return
        title, detail = _crash_info
    if not _try_qt_message_box(title, detail):
        _show_crash_dialog(title, detail)


def _try_qt_message_box(title, detail):
    try:
        from PyQt5.QtWidgets import QApplication, QMessageBox

        app = QApplication.instance()
        if app is None:
            return False

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Crash Report")
        msg_box.setText("Program crashed!")

        info = f"Type: {title}\n\nDetails:\n{detail[:800]}"
        if len(detail) > 800:
            info += f"\n... ({len(detail)} chars total)"
        msg_box.setInformativeText(info)

        msg_box.setDetailedText(detail)
        msg_box.exec_()
        return True
    except BaseException:
        return False


if __name__ == "__main__":
    import importlib
    import importlib.util

    target = sys.argv[1] if len(sys.argv) > 1 else None

    if not target:
        print("Usage: python crash_debug.py <module>[:<function>] [args...]")
        print()
        print("Examples:")
        print("  python crash_debug.py run           # Run run.py")
        print("  python crash_debug.py run:main      # Run main() in run.py")
        print("  python crash_debug.py app --port 8080")
        sys.exit(1)

    install()

    if ':' in target:
        module_name, func_name = target.rsplit(':', 1)
    else:
        module_name, func_name = target, None

    if module_name.endswith('.py'):
        module_path = os.path.join(_current_dir, module_name)
        if not os.path.isfile(module_path):
            print(f"File not found: {module_name}")
            sys.exit(1)
    else:
        module_path = os.path.join(_current_dir, module_name + '.py')
        if not os.path.isfile(module_path):
            module_path = os.path.join(_current_dir, module_name, '__init__.py')
            if not os.path.isfile(module_path):
                print(f"Module not found: {module_name}")
                sys.exit(1)

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(os.path.abspath(module_path)))
    spec.loader.exec_module(mod)

    try:
        if func_name:
            func = getattr(mod, func_name)
            func()
        else:
            if hasattr(mod, 'main'):
                mod.main()
            elif hasattr(mod, 'app'):
                app = mod.app
                if hasattr(app, 'exec_'):
                    app.exec_()
                elif callable(app):
                    app()
            else:
                print(f"Module '{module_name}' has no main() or app()")
                sys.exit(1)
    except SystemExit as e:
        sys.exit(e.code)
    except KeyboardInterrupt:
        pass
