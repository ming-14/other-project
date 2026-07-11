"""!
@file core/log_async.py
@brief 异步日志写入器

基于QueueHandler + QueueListener实现非阻塞日志写入。
主线程仅将记录入队，独立线程负责实际IO。
"""

import logging
import logging.handlers
import queue
import sys
import threading


class _OverflowQueueHandler(logging.handlers.QueueHandler):
    """!@brief 支持溢出丢弃的QueueHandler

    队列满时丢弃最早记录并入队新记录。
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.queue.put_nowait(record)
            except queue.Full:
                self.handleError(record)


class AsyncLogWriter:
    """!@brief 异步日志写入器

    使用QueueHandler + QueueListener实现非阻塞日志写入。
    """

    def __init__(self, handlers: list[logging.Handler],
                 queue_size: int = 1000):
        """!@brief 构造异步写入器

        @param handlers   实际输出Handler列表
        @param queue_size 队列最大容量
        """
        self._queue: queue.Queue = queue.Queue(maxsize=queue_size)
        self._queue_handler = _OverflowQueueHandler(self._queue)
        self._listener = logging.handlers.QueueListener(
            self._queue, *handlers, respect_handler_level=True)
        self._fallback_mode: bool = False
        self._direct_handlers: list[logging.Handler] = list(handlers)
        self._started: bool = False
        self._lock = threading.Lock()

    def start(self) -> None:
        """!@brief 启动异步写入线程"""
        with self._lock:
            if self._started:
                return
            self._listener.start()
            self._started = True

    def get_handler(self) -> logging.Handler:
        """!@brief 获取QueueHandler，用于绑定到日志器

        @return QueueHandler 实例
        """
        return self._queue_handler

    def stop(self, timeout: float = 5.0) -> None:
        """!@brief 停止异步写入，等待队列排空

        @param timeout 等待超时时间（秒）
        """
        with self._lock:
            if not self._started:
                return
            self._started = False
        try:
            self._listener.stop()
        except Exception as e:
            sys.stderr.write('异步写入器停止异常: %s\n' % e)
            self._fallback_mode = True

    @property
    def is_fallback(self) -> bool:
        """!@brief 是否已回退到同步写入"""
        return self._fallback_mode

    @property
    def queue_size(self) -> int:
        """!@brief 当前队列积压数量"""
        return self._queue.qsize()

    def get_direct_handlers(self) -> list[logging.Handler]:
        """!@brief 获取直接写入的Handler列表（同步回退时使用）

        @return Handler列表
        """
        return list(self._direct_handlers)