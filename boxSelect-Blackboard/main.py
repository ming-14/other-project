# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-
# main.py
# 许可证：The MIT License
# That means you can use it freely but not call me.
# However, you should remove my name in the project.
# time: 2024/11
# version: 2.0
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-
import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QComboBox, QLineEdit, QMessageBox
import rikka
import log

# +-+-+-+-+-+-+-+-+-+-+-
# function: 弹窗帮助信息
# +-+-+-+-+-+-+-+-+-+-+-
def helpInformation():
    QMessageBox.information(w, "帮助", \
                            """
一定要耐心读完噢~~

若文本框没有输入文字，则为摄像头模式。当您选择了摄像头并且点击“执行操作”是，程序会打开摄像头处理
若文本框有输入文字，则为图片模式。当您点击“执行操作”是，程序会打开图片处理，请确保路径下有文件

---
Tip：Windows 10 及以上的系统会默认禁用程序的摄像头权限，请前往安全中心开启
                            """
                            , QMessageBox.Ok)

# +-+-+-+-+-+-+-+-+-+-+-
# function: 弹窗关于信息
# +-+-+-+-+-+-+-+-+-+-+-
def aboutInformation():
    QMessageBox.information(w, "关于", \
                            """
本项目为开源项目
作者：github/ming-14
许可证：The MIT License
项目代号：Rikka

本程序可对图片进行处理：框出图片上的黑板并且识别上面的粉笔字
---
Todo：
1. 屏蔽电脑界面
2. 屏蔽人及异物
3. 采集密集点
4. 小车位置及寻址算法
---
Tips：黑板必须是绿的
                            """
                            , QMessageBox.Ok)

# +-+-+-+-+-+-+-+-+-+-+-
# function: 执行操作的onClick，执行模块
# +-+-+-+-+-+-+-+-+-+-+-
def on_button_click():
    log.print("开始处理")
    input_text = text_box.text()
    if input_text:
        log.print("处理文件图片")
        try:
            rikka.imgExample(input_text)
        except FileNotFoundError as e:
            QMessageBox.critical(w, "Error", "My dear, 我找不到文件在哪，呜呜呜", QMessageBox.Ok)
            log.print(e)
    else:
        log.print("处理摄像头")
        rikka.capExample(cameras[camera_selector.currentIndex()], "chick q to quit")

if __name__ == '__main__':
   # 初始化窗口
    app = QApplication(sys.argv)
    w = QWidget()
    w.resize(540, 360)
    w.setWindowTitle('六花世界 - Easy to use')
    layout = QVBoxLayout() # 控件

    # 文本框
    text_box = QLineEdit()
    text_box.setPlaceholderText("图片路径") 

    # 按钮
    buttonRun = QPushButton('执行操作')
    buttonRun.setFixedSize(100, 40)
    buttonRun.clicked.connect(on_button_click)

    buttonHelp = QPushButton('帮助')
    buttonHelp.setFixedSize(100, 40)
    buttonHelp.clicked.connect(helpInformation)

    buttonAbout = QPushButton('关于')
    buttonAbout.setFixedSize(100, 40)
    buttonAbout.clicked.connect(aboutInformation)

    # 摄像头列表
    cameras = rikka.list_cameras()
    camera_selector = QComboBox()
    if cameras:
        # 添加摄像头索引到选择列表
        camera_selector.addItems([f'摄像头 {index}' for index in cameras])
    else:
        camera_selector.addItem("未检测到任何摄像头")

    layout.addWidget(camera_selector)
    layout.addWidget(buttonRun)
    layout.addWidget(buttonHelp)
    layout.addWidget(buttonAbout)
    layout.addWidget(text_box) 
    w.setLayout(layout)
    w.show()
    helpInformation()
    sys.exit(app.exec_())
