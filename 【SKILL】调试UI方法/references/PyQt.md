# PyQt / PySide 调试参考

> 配合 [调试UI方法.md](../调试UI方法.md) 使用，本文只包含 PyQt/PySide 特定 API 和代码。

---

## 一、调试脚本模板

### 1. 最小化复现脚本

```python
"""复现脚本：<问题描述>"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt5.QtWidgets import QApplication, QWidget
from PyQt5.QtCore import QTimer

app = QApplication(sys.argv)
parent = QWidget()
parent.resize(1400, 900)
parent.show()

from src.ui.dialogs.package.new_package_dialog import NewPackageDialog
dlg = NewPackageDialog(
    paths=[Path('test.exe')],
    storage_root=Path('.'),
    config_dir='.',
    parent=parent,
)
dlg.show()

QTimer.singleShot(300, lambda: (
    print(f'widget: {dlg.widget.width()}x{dlg.widget.height()}'),
    dlg.close(),
    app.quit(),
))

app.exec_()
```

**要点**：
- 用 `QWidget` 做最小父窗口，不需要启动 `MainWindow`
- `QTimer.singleShot` 延迟检查，等待 layout 稳定
- 用 `dlg.show()` + `app.exec_()` 而非 `dlg.exec()`，方便定时器控制

### 2. 交互式调试窗口

```python
from PyQt5.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget, QTextEdit
from PyQt5.QtCore import QTimer

class DebugWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("调试窗口")
        self.resize(1400, 900)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        btn_frame = QWidget()
        btn_layout = QVBoxLayout(btn_frame)
        btn_layout.addWidget(QPushButton("打开对话框", clicked=self._open_dialog))
        btn_layout.addWidget(QPushButton("模拟resize", clicked=self._simulate_resize))
        layout.addWidget(btn_frame)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        layout.addWidget(self._log)

        self._dlg = None

    def _open_dialog(self):
        dlg = SomeDialog(..., parent=self)
        self._dlg = dlg
        self._dump("创建后")
        dlg.show()
        QTimer.singleShot(100, lambda: self._dump("show后100ms"))

    def _simulate_resize(self):
        self.resize(self.width() - 200, self.height() - 100)
        QTimer.singleShot(200, lambda: self._dump("resize后"))

    def _dump(self, label):
        dlg = self._dlg
        if dlg is None:
            return
        wg = dlg.widget.geometry()
        self._log.append(f'[{label}] widget={wg.width()}x{wg.height()} pos=({wg.x()},{wg.y()})')
```

### 3. 全应用启动脚本

```python
from src.ui.main_window import MainWindow
window = MainWindow()
window.show()
app.processEvents()
window.switchTo(window.package_page)
app.processEvents()
```

---

## 二、调试方法 API

### 2.1 几何数据 Dump

```python
def geom(w, name):
    g = w.geometry()
    print(f'  {name}: pos=({g.x()},{g.y()}) size={g.width()}x{g.height()} '
          f'visible={w.isVisible()} '
          f'min={w.minimumWidth()}x{w.minimumHeight()} '
          f'max={w.maximumWidth()}x{w.maximumHeight()} '
          f'hint={w.sizeHint().width()}x{w.sizeHint().height()}')

geom(dlg.widget, 'widget')
geom(dlg._info_panel, 'info_panel')
geom(dlg._sep, 'separator')
```

### 2.2 时序分析

```python
dlg.show()
QTimer.singleShot(0, lambda: dump("singleShot(0)"))   # 事件循环空闲后
QTimer.singleShot(100, lambda: dump("100ms"))          # layout 稳定后
QTimer.singleShot(500, lambda: dump("500ms"))          # 动画完成后
```

**经验值**：
- `singleShot(0)` — 在当前事件循环迭代完成后执行，layout 通常已 activate
- 100ms — 足够等待大部分 layout 计算
- 500ms — 等待 `MaskDialogBase.showEvent` 的 200ms 淡入动画

### 2.3 事件流追踪

```python
orig_resize = SomeClass.resizeEvent
def traced_resize(self, e):
    print(f'  [resizeEvent] widget: {self.widget.width()}x{self.widget.height()}')
    orig_resize(self, e)
    print(f'  [resizeEvent after] widget: {self.widget.width()}x{self.widget.height()}')
SomeClass.resizeEvent = traced_resize
```

同理可追踪 `eventFilter`、`showEvent`、`hideEvent`、`paintEvent`、`layoutRequest` 等。

**追踪 eventFilter**：

```python
orig_event_filter = SomeClass.eventFilter
def traced_event_filter(self, obj, event):
    print(f'  [eventFilter] obj={obj.__class__.__name__} event={event.type()}')
    return orig_event_filter(self, obj, event)
SomeClass.eventFilter = traced_event_filter
```

### 2.4 截屏保存

```python
pix = dlg.grab()
pix.save('debug_screenshot.png')
```

### 2.5 强制 Layout 重算

```python
def force_layout(widget):
    widget.layout().invalidate()
    widget.layout().activate()
    for child in widget.findChildren(QWidget):
        if child.layout():
            child.layout().invalidate()
            child.layout().activate()
    app.processEvents()
    app.sendPostedEvents()
```

### 2.6 样式与主题调试

```python
# 查看实际 stylesheet
print(widget.styleSheet())

# 查看生效的调色板颜色
print(widget.palette().color(widget.backgroundRole()).name())

# 临时设置背景色定位组件边界
widget.setStyleSheet("background-color: rgba(255,0,0,0.3);")
```

### 2.7 辅助色块定位法

```python
widget.setStyleSheet("background-color: rgba(255,0,0,0.3);")   # 红色半透明
widget.setStyleSheet("background-color: rgba(0,255,0,0.3);")   # 绿色半透明
```

### 2.8 组件树 Dump

```python
def dump_tree(widget, indent=0):
    g = widget.geometry()
    print(f'{"  "*indent}{widget.__class__.__name__}: '
          f'{g.width()}x{g.height()} at ({g.x()},{g.y()}) '
          f'visible={widget.isVisible()}')
    for child in widget.findChildren(QWidget):
        if child.parent() == widget:
            dump_tree(child, indent + 1)
```

### 2.9 焦点与输入调试

```python
# 查看当前焦点组件
print(f'focusWidget: {app.focusWidget()}')
print(f'focusPolicy: {widget.focusPolicy()}')

# 追踪焦点变化
app.focusChanged.connect(lambda old, new: print(f'focus: {old} -> {new}'))
```

### 2.10 信号/回调追踪

```python
orig_handler = SomeClass._on_value_changed
def traced_handler(self, *args, **kwargs):
    print(f'  [_on_value_changed] args={args} kwargs={kwargs}')
    import traceback
    traceback.print_stack(limit=5)
    result = orig_handler(self, *args, **kwargs)
    print(f'  [_on_value_changed] returned')
    return result
SomeClass._on_value_changed = traced_handler
```

### 2.11 性能分析

```python
# 渲染性能：检查重绘频率
orig_paint = SomeWidget.paintEvent
def traced_paint(self, e):
    import time
    t = time.perf_counter()
    orig_paint(self, e)
    dt = (time.perf_counter() - t) * 1000
    if dt > 16:  # 超过一帧(60fps)
        print(f'  [paintEvent SLOW] {dt:.1f}ms')
SomeWidget.paintEvent = traced_paint
```

---

## 三、PyQt/PySide 特有陷阱

### 1. MaskDialogBase 的 _hBoxLayout 会覆盖手动 resize

`MaskDialogBase` 使用 `_hBoxLayout(AlignCenter)` 管理 widget，layout activate 时会将 widget 收缩至 sizeHint。

**解决方案**：从 `_hBoxLayout` 中移除 widget，用 `setGeometry()` 手动控制位置和尺寸。

### 2. maximumSize 阻止 dialog 扩大

`self.setMaximumSize(pw, ph)` 会阻止 dialog 在父窗口变大时跟随扩大。

**解决方案**：只限制 widget 的 maximumSize，不限制 dialog 本身。

### 3. resizeEvent 中使用旧的目标尺寸

`MaskDialogBase.eventFilter` 在父窗口 resize 时同步调用 `self.resize()`，触发 `resizeEvent`。此时如果 `_target_widget_size` 还是旧值，widget 会被放到错误位置。

**解决方案**：在 `resizeEvent` 中同步更新目标尺寸。

### 4. minimumWidth 过大导致布局重叠

QHBoxLayout 在空间不足时会重叠子组件，而不是截断。

**解决方案**：确保所有子组件的 minimumWidth 之和不超过可用空间。

### 5. QTimer.singleShot(0) 时序问题

- 不够早：layout 还没 activate，拿到的尺寸是旧的
- 不够晚：后续事件（如 MaskDialogBase.eventFilter 的 resize）会覆盖你的设置

**解决方案**：在 `resizeEvent` 中同步处理，不依赖延迟回调。

### 6. DPI 缩放

```python
app.setAttribute(Qt.AA_EnableHighDpiScaling)
# 调试时确认缩放
print(f'devicePixelRatio: {app.devicePixelRatio()}')
```
