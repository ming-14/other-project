# wxPython 调试参考

> 配合 [调试UI方法.md](../调试UI方法.md) 使用，本文只包含 wxPython 特定 API 和代码。

---

## 一、调试脚本模板

### 1. 最小化复现脚本

```python
"""复现脚本：<问题描述>"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import wx

app = wx.App()
frame = wx.Frame(None, size=(1400, 900))

from src.ui.my_panel import MyPanel
panel = MyPanel(frame)
frame.Show()

wx.CallLater(300, lambda: (
    print(f'Size={panel.GetSize()}'),
    frame.Close(),
    app.ExitMainLoop(),
))

app.MainLoop()
```

**要点**：
- `wx.Frame(None, size=(W, H))` 创建无父窗口的顶层窗口
- `wx.CallLater(ms, callback)` 延迟检查
- `app.MainLoop()` 启动事件循环

### 2. 交互式调试窗口

```python
import wx

class DebugFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, size=(1400, 900), title="调试窗口")
        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_open = wx.Button(panel, label="打开对话框")
        btn_open.Bind(wx.EVT_BUTTON, self._open_dialog)
        btn_resize = wx.Button(panel, label="模拟resize")
        btn_resize.Bind(wx.EVT_BUTTON, self._simulate_resize)
        btn_sizer.Add(btn_open, 0, wx.ALL, 5)
        btn_sizer.Add(btn_resize, 0, wx.ALL, 5)
        sizer.Add(btn_sizer, 0, wx.EXPAND)

        self._log = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        sizer.Add(self._log, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        self._dlg = None

    def _open_dialog(self, event=None):
        self._dlg = SomeDialog(self)
        self._dump("创建后")
        self._dlg.Show()
        wx.CallLater(100, lambda: self._dump("show后100ms"))

    def _simulate_resize(self, event=None):
        s = self.GetSize()
        self.SetSize(s.width - 200, s.height - 100)
        wx.CallLater(200, lambda: self._dump("resize后"))

    def _dump(self, label):
        dlg = self._dlg
        if dlg is None:
            return
        s = dlg.GetSize()
        p = dlg.GetPosition()
        self._log.AppendText(f'[{label}] size={s.width}x{s.height} pos=({p.x},{p.y})\n')
```

### 3. 全应用启动脚本

```python
from src.ui.main_window import MainWindow
app = wx.App()
window = MainWindow()
window.Show()
wx.Yield()
window.switch_to("package_page")
app.MainLoop()
```

---

## 二、调试方法 API

### 2.1 几何数据 Dump

```python
def geom(w, name):
    s = w.GetSize()
    p = w.GetPosition()
    print(f'  {name}: pos=({p.x},{p.y}) size={s.width}x{s.height} '
          f'shown={w.IsShown()} '
          f'min={w.GetMinSize()} max={w.GetMaxSize()} '
          f'best={w.GetBestSize()}')

geom(panel, 'panel')
geom(sizer_item.GetWindow(), 'sizer_child')
```

### 2.2 时序分析

```python
frame.Show()
wx.CallAfter(lambda: dump("CallAfter"))                # 事件循环下一轮
wx.CallLater(100, lambda: dump("100ms"))
wx.CallLater(500, lambda: dump("500ms"))
```

### 2.3 事件流追踪

```python
orig_size = SomePanel.OnSize
def traced_size(self, event):
    print(f'  [OnSize] size={self.GetSize()}')
    orig_size(self, event)
    print(f'  [OnSize after] size={self.GetSize()}')
SomePanel.OnSize = traced_size
```

同理可追踪 `OnPaint`、`OnEraseBackground`、`OnShow`、`OnIdle` 等。

**绑定事件追踪**：

```python
def traced_bind(self, event, handler, *args, **kwargs):
    def wrapper(evt):
        print(f'  [Event] {event.__name__} from {evt.GetEventObject()}')
        handler(evt)
    return orig_bind(event, wrapper, *args, **kwargs)
```

### 2.4 截屏保存

```python
bmp = wx.Bitmap(panel.GetSize().width, panel.GetSize().height)
dc = wx.ClientDC(panel)
dc.Blit(0, 0, bmp.GetWidth(), bmp.GetHeight(), dc, 0, 0)
bmp.SaveFile('debug_screenshot.png', wx.BITMAP_TYPE_PNG)
```

### 2.5 强制 Layout 重算

```python
def force_layout(window):
    window.Layout()
    window.Fit()
    window.Refresh()
    window.Update()
```

### 2.6 样式与主题调试

```python
# 查看颜色
print(widget.GetBackgroundColour().GetAsString())
print(widget.GetForegroundColour().GetAsString())
print(widget.GetFont().GetFaceName())

# 临时设置背景色
widget.SetBackgroundColour(wx.Colour(255, 0, 0))
widget.Refresh()
```

### 2.7 辅助色块定位法

```python
widget.SetBackgroundColour(wx.Colour(255, 200, 200))  # 浅红
widget.SetBackgroundColour(wx.Colour(200, 255, 200))  # 浅绿
widget.Refresh()
```

### 2.8 组件树 Dump

```python
def dump_tree(window, indent=0):
    s = window.GetSize()
    p = window.GetPosition()
    print(f'{"  "*indent}{window.__class__.__name__}: '
          f'{s.width}x{s.height} at ({p.x},{p.y}) shown={window.IsShown()}')
    for child in window.GetChildren():
        dump_tree(child, indent + 1)
```

### 2.9 焦点与输入调试

```python
# 查看焦点
print(f'focus: {wx.Window.FindFocus()}')

# 追踪焦点
self.Bind(wx.EVT_SET_FOCUS, lambda e: print(f'FocusIn: {e.GetWindow()}'))
self.Bind(wx.EVT_KILL_FOCUS, lambda e: print(f'FocusOut: {e.GetWindow()}'))

# 追踪键盘
self.Bind(wx.EVT_KEY_DOWN, lambda e: print(f'Key: {e.GetKeyCode()}'))
```

### 2.10 信号/回调追踪

```python
# 追踪事件绑定
orig_bind = window.Bind
def traced_bind(event, handler, *args, **kwargs):
    def wrapper(evt):
        print(f'  [Event] {event.__name__}')
        handler(evt)
    return orig_bind(event, wrapper, *args, **kwargs)
window.Bind = traced_bind
```

### 2.11 性能分析

```python
# 渲染性能
orig_paint = SomeWindow.OnPaint
def traced_paint(self, event):
    import time
    t = time.perf_counter()
    orig_paint(self, event)
    dt = (time.perf_counter() - t) * 1000
    if dt > 16:
        print(f'  [OnPaint SLOW] {dt:.1f}ms')
SomeWindow.OnPaint = traced_paint
```

---

## 三、wxPython 特有陷阱

### 1. Sizer 会覆盖手动 SetSize()

`Sizer` 在 layout 时会重新计算子组件的位置和大小，覆盖手动 `SetSize()` 的结果。

**解决方案**：从 Sizer 中 `Detach` 组件，或使用 `wx.FIXED_MINSIZE` / `wx.RESERVE_SPACE_EVEN_IF_HIDDEN` 标志。

### 2. Freeze/Thaw 闪烁

批量更新 UI 时频繁重绘导致闪烁。

**解决方案**：用 `Freeze()` / `Thaw()` 包裹批量操作。

```python
window.Freeze()
# ... 批量更新 ...
window.Thaw()
```

### 3. CallAfter 时序

`wx.CallAfter` 在当前事件处理完成后执行，但 layout 可能还没完成。

**解决方案**：在 `OnSize` / `OnIdle` 中同步处理，或用 `CallLater` 加足够延迟。

### 4. DPI 缩放

```python
wx.EnableDPIAware()
# 调试时确认缩放
print(f'DPI: {wx.ScreenDC().GetPPI()}')
print(f'ScaleFactor: {window.GetDPIScaleFactor()}')
```

### 5. Sizer 的 proportion 和 flag 理解错误

- `proportion=0` — 固定尺寸，不随父容器伸缩
- `proportion>0` — 按比例分配剩余空间
- `wx.EXPAND` — 填充垂直于 Sizer 方向的空间

**常见错误**：设了 `proportion>0` 但没加 `wx.EXPAND`，组件只在一个方向伸缩。
