import sys
import os

# 将项目根目录加入 sys.path，确保模块可导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from qfluentwidgets import setThemeColor
from core.logger import setup_logger
from app import LuckyCallWindow


def main():
    # 初始化日志
    logger = setup_logger()
    logger.info("LuckyCall 启动")

    # 高 DPI 支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    app.setApplicationName("LuckyCall")

    # 设置主题色
    setThemeColor("#0078D4")

    window = LuckyCallWindow()
    window.show()

    logger.info("LuckyCall 窗口已显示")
    ret = app.exec_()
    logger.info("LuckyCall 退出，返回码: %d", ret)
    return ret


if __name__ == "__main__":
    sys.exit(main())
