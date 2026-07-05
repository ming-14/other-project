# Tkinter 调试参考

> 配合 [调试UI方法.md](../调试UI方法.md) 使用，本文只包含 Tkinter 特定 API 和代码。

---

## 一、调试脚本模板

### 1. 最小化复现脚本

```python
"""复现脚本：<问题描述>"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tkinter as tk

root = tk.Tk()
root.geometry("1400x900")

from src.ui.my_widget import MyWidget
w = MyWidget(root)
w.pack(fill="both", expand=True)

root.after(300, lambda: (
    print(f'winfo_width={w.winfo_width()}, winfo_height={w.winfo_height()}'),
    root.destroy(),
))

root.mainloop()
```

**要点**：
- `root.geometry("WxH")` 设置初始尺寸
- `root.after(ms, callback)` 延迟检查，等待 layout 稳定
- `w.pack(fill="both", expand=True)` 让组件填充父容器

### 2. 交互式调试窗口

```python
import tkinter as tk

class DebugWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.geometry("1400x900")

        btn_frame = tk.Frame(self)
        btn_frame.pack(side="top", fill="x")
        tk.Button(btn_frame, text="打开对话框", command=self._open_dialog).pack(side="left")
        tk.Button(btn_frame, text="模拟resize", command=self._simulate_resize).pack(side="left")

        self._log = tk.Text(self, height=10)
        self._log.pack(side="bottom", fill="x")

        self._dlg = None

    def _open_dialog(self):
        self._dlg = SomeDialog(self)
        self._dump("创建后")
        self._dlg.show()
        self.after(100, lambda: self._dump("show后100ms"))

    def _simulate_resize(self):
        self.geometry(f"{self.winfo_width()-200}x{self.winfo_height()-100}")
        self.after(200, lambda: self._dump("resize后"))

    def _dump(self, label):
        dlg = self._dlg
        if dlg is None:
            return
        self._log.insert("end", f"[{label}] winfo_width={dlg.winfo_width()} winfo_height={dlg.winfo_height()}\n")
```

### 3. 全应用启动脚本

```python
from src.ui.main_window import MainWindow
root = tk.Tk()
window = MainWindow(root)
root.update_idletasks()
window.switch_to("package_page")
root.mainloop()
```

---

## 二、调试方法 API

### 2.1 几何数据 Dump

```python
def geom(w, name):
    w.update_idletasks()
    print(f'  {name}: winfo_geometry={w.winfo_geometry()} '
          f'winfo_width={w.winfo_width()} winfo_height={w.winfo_height()} '
          f'winfo_x={w.winfo_x()} winfo_y={w.winfo_y()} '
          f'winfo_viewable={w.winfo_viewable()}')
```

**注意**：必须先调用 `update_idletasks()`，否则 `winfo_*` 返回的可能是旧值（1 或 0）。

### 2.2 时序分析

```python
dlg.show()
root.after_idle(lambda: dump("after_idle"))     # 空闲后
root.after(100, lambda: dump("100ms"))           # layout 稳定后
root.after(500, lambda: dump("500ms"))           # 动画完成后
```

### 2.3 事件流追踪

**绑定事件**：

```python
widget.bind("<Configure>", lambda e: print(f'[Configure] {e.widget} width={e.width} height={e.height}'))
widget.bind("<Map>", lambda e: print(f'[Map] {e.widget}'))
widget.bind("<Unmap>", lambda e: print(f'[Unmap] {e.widget}'))
widget.bind("<Expose>", lambda e: print(f'[Expose] {e.widget}'))
widget.bind("<Destroy>", lambda e: print(f'[Destroy] {e.widget}'))
```

**Monkey-patch 方法**：

```python
orig_configure = SomeWidget.configure
def traced_configure(self, **kwargs):
    print(f'  [configure] kwargs={kwargs}')
    return orig_configure(self, **kwargs)
SomeWidget.configure = traced_configure
```

### 2.4 截屏保存

```python
from PIL import ImageGrab
x, y = dlg.winfo_rootx(), dlg.winfo_rooty()
w, h = dlg.winfo_width(), dlg.winfo_height()
ImageGrab.grab(bbox=(x, y, x + w, y + h)).save('debug_screenshot.png')
```

### 2.5 强制 Layout 重算

```python
def force_layout(widget):
    widget.update_idletasks()
    # 或对顶层窗口：
    # root.update_idletasks()
```

### 2.6 样式与主题调试

```python
# 查看 configure 值
print(widget.cget("background"))
print(widget.cget("font"))
print(widget.cget("foreground"))
print(widget.cget("borderwidth"))
print(widget.cget("relief"))

# 查看所有配置项
print(widget.keys())  # 返回所有可配置选项名

# 临时设置背景色定位
widget.configure(bg="red")
```

### 2.7 辅助色块定位法

```python
# 方式1：直接设背景色
widget.configure(bg="pink")

# 方式2：用高亮边框
widget.configure(highlightthickness=2, highlightbackground="red")

# 方式3：Frame 容器加边框
frame.configure(bg="red", bd=2, relief="solid")
```

### 2.8 组件树 Dump

```python
def dump_tree(widget, indent=0):
    info = widget.winfo_geometry()
    print(f'{"  "*indent}{widget.winfo_class()}: {info} viewable={widget.winfo_viewable()}')
    for child in widget.winfo_children():
        dump_tree(child, indent + 1)
```

### 2.9 焦点与输入调试

```python
# 查看当前焦点
print(f'focus: {root.focus_get()}')

# 追踪焦点
widget.bind("<FocusIn>", lambda e: print(f'FocusIn: {e.widget}'))
widget.bind("<FocusOut>", lambda e: print(f'FocusOut: {e.widget}'))

# 检查键盘绑定
widget.bind("<Key>", lambda e: print(f'Key: {e.keysym} char={e.char}'))
widget.bind("<Return>", lambda e: print(f'Return pressed'))
```

### 2.10 信号/回调追踪

```python
# 追踪变量变化
var = tk.StringVar()
var.trace_add("write", lambda *args: print(f'var changed: {var.get()}'))
var.trace_add("read", lambda *args: print(f'var read'))
var.trace_add("unset", lambda *args: print(f'var unset'))

# 追踪 command 回调
orig_command = SomeWidget.__init__
# 或直接替换 command 参数
```

### 2.11 性能分析

```python
# 事件风暴检测
import time
_event_times = []

orig_bind = widget.bind
def rate_limited_bind(sequence, func, add=None):
    def wrapper(*args):
        _event_times.append(time.perf_counter())
        recent = [t for t in _event_times if time.perf_counter() - t < 1.0]
        if len(recent) > 100:
            print(f'  [EVENT STORM] {sequence}: {len(recent)} events/sec')
        return func(*args)
    return orig_bind(sequence, wrapper, add)
widget.bind = rate_limited_bind
```

---

## 三、Tkinter 特有陷阱

### 1. geometry() 与 winfo_width() 不同步

`geometry()` 设置后，`winfo_width()` 不会立即更新。

**解决方案**：调用 `update_idletasks()` 后再读取。

```python
root.geometry("800x600")
print(root.winfo_width())   # 可能还是旧值
root.update_idletasks()
print(root.winfo_width())   # 现在是 800
```

### 2. pack/grid/place 混用冲突

同一父容器内不能混用 `pack`、`grid`、`place`（会报错或布局错乱）。

**解决方案**：同一父容器内统一使用一种布局管理器。需要手动控制时用 `place()`。

### 3. grid 的 row/column 必须连续

`grid` 布局中如果有跳过的行号/列号，会留下空白。

**解决方案**：确保行号列号连续，或用 `rowconfigure` / `columnconfigure` 设置 weight=0。

### 4. StringVar/IntVar 的 trace 回调时序

`trace_add` 的回调在变量变化时触发，但此时其他绑定的回调可能还没执行。

**解决方案**：在 trace 回调中用 `after_idle` 延迟处理。

### 5. after_idle vs after(0)

- `after_idle` — 在空闲时执行（所有待处理事件之后）
- `after(0)` — 尽快执行，但仍在当前事件处理完成后

两者行为相似但有微妙差异，`after_idle` 更晚。

### 6. DPI 缩放

```python
# 设置缩放
root.tk.call('tk', 'scaling', dpi / 72.0)

# 查看当前缩放
print(root.tk.call('tk', 'scaling'))
```
