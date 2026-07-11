"""!
@file core/log_qt_bridge.py
@brief PyQt5日志桥接

捕获qDebug/qWarning/qCritical消息并纳入统一日志管理，
同时提供Qt信号供UI组件订阅。PyQt5不可用时自动跳过。
"""

import logging
import sys

try:
    from PyQt5 import QtCore
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

_QT_LEVEL_MAP = {}

if _QT_AVAILABLE:
    _QT_LEVEL_MAP = {
        QtCore.QtDebugMsg: logging.DEBUG,
        QtCore.QtWarningMsg: logging.WARNING,
        QtCore.QtCriticalMsg: logging.ERROR,
        QtCore.QtFatalMsg: logging.CRITICAL,
    }

    class _LogSignalEmitter(QtCore.QObject):
        """!@brief 日志Qt信号发射器"""

        log_message = QtCore.pyqtSignal(str, str)


class QtLogBridge:
    """!@brief PyQt5日志桥接

    捕获qDebug/qWarning/qCritical消息并纳入统一日志管理，
    同时提供Qt信号供UI组件订阅。
    """

    def __init__(self, logger: logging.Logger):
        """!@brief 构造Qt日志桥接

        @param logger 目标日志器
        """
        self._logger = logger
        self._available: bool = False
        self._signal_emitter = None
        self._old_handler = None

    def install(self) -> bool:
        """!@brief 安装Qt消息处理器

        @return True表示安装成功
        """
        if not _QT_AVAILABLE:
            return False
        try:
            self._signal_emitter = _LogSignalEmitter()
            self._old_handler = QtCore.qInstallMessageHandler(
                self._qt_message_handler)
            self._available = True
            return True
        except Exception as e:
            sys.stderr.write('Qt日志桥接安装失败: %s\n' % e)
            return False

    def _qt_message_handler(self, msg_type, context, message):
        """!@brief Qt消息处理器回调"""
        level = _QT_LEVEL_MAP.get(msg_type, logging.INFO)
        msg = message or ''
        if context and context.file:
            msg = '%s (%s:%d)' % (msg, context.file, context.line)
        self._logger.log(level, '[Qt] %s', msg)
        if self._signal_emitter is not None:
            level_name = logging.getLevelName(level)
            try:
                self._signal_emitter.log_message.emit(level_name, msg)
            except RuntimeError:
                pass

    def uninstall(self) -> None:
        """!@brief 卸载Qt消息处理器，恢复默认"""
        if not self._available:
            return
        try:
            QtCore.qInstallMessageHandler(self._old_handler)
        except Exception:
            pass
        self._available = False
        self._signal_emitter = None

    @property
    def available(self) -> bool:
        """!@brief Qt桥接是否可用"""
        return self._available

    @property
    def signal_emitter(self):
        """!@brief 获取Qt信号发射器"""
        return self._signal_emitter