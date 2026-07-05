# Kivy 调试参考

> 配合 [调试UI方法.md](../调试UI方法.md) 使用，本文只包含 Kivy 特定 API 和代码。

---

## 一、调试脚本模板

### 1. 最小化复现脚本

```python
"""复现脚本：<问题描述>"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kivy.app import App
from kivy.clock import Clock
from kivy.uix.widget import Widget

from src.ui.my_widget import MyWidget

class DebugApp(App):
    def build(self):
        self.w = MyWidget()
        Clock.schedule_once(lambda dt: print(f'size={self.w.size}'), 0.3)
        return self.w

DebugApp().run()
```

**要点**：
- 继承 `App`，在 `build()` 中返回根组件
- `Clock.schedule_once(callback, delay)` 延迟检查
- delay 单位为秒（0.3 = 300ms）

### 2. 交互式调试窗口

```python
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock

class DebugLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)

        btn_layout = BoxLayout(orientation='horizontal', size_hint_y=0.1)
        btn_open = Button(text='打开对话框')
        btn_open.bind(on_press=self._open_dialog)
        btn_resize = Button(text='模拟resize')
        btn_resize.bind(on_press=self._simulate_resize)
        btn_layout.add_widget(btn_open)
        btn_layout.add_widget(btn_resize)
        self.add_widget(btn_layout)

        self._log = Label(size_hint_y=0.2, halign='left', valign='top')
        self.add_widget(self._log)

        self._content = BoxLayout(size_hint_y=0.7)
        self.add_widget(self._content)

        self._dlg = None

    def _open_dialog(self, instance):
        self._dlg = SomeWidget()
        self._content.add_widget(self._dlg)
        self._dump("创建后")
        Clock.schedule_once(lambda dt: self._dump("show后100ms"), 0.1)

    def _simulate_resize(self, instance):
        self.width -= 200
        self.height -= 100
        Clock.schedule_once(lambda dt: self._dump("resize后"), 0.2)

    def _dump(self, label):
        dlg = self._dlg
        if dlg is None:
            return
        self._log.text += f'[{label}] size={dlg.size} pos={dlg.pos}\n'
```

### 3. 全应用启动脚本

```python
from src.ui.main_app import MainApp
app = MainApp()
app.run()
```

---

## 二、调试方法 API

### 2.1 几何数据 Dump

```python
def geom(w, name):
    print(f'  {name}: pos={w.pos} size={w.size} '
          f'texture_size={getattr(w, "texture_size", None)} '
          f'opacity={w.opacity} visible={w.visible} '
          f'size_hint={w.size_hint} size_hint_min={w.size_hint_min} '
          f'size_hint_max={w.size_hint_max}')
```

### 2.2 时序分析

```python
Clock.schedule_once(lambda dt: dump("next_frame"), 0)   # 下一帧
Clock.schedule_once(lambda dt: dump("100ms"), 0.1)       # layout 稳定后
Clock.schedule_once(lambda dt: dump("500ms"), 0.5)       # 动画完成后
```

**注意**：`Clock.schedule_once(callback, 0)` 在下一帧执行，不是立即。

### 2.3 事件流追踪

```python
# 追踪 on_size / on_pos 回调
orig_on_size = SomeWidget.on_size
def traced_on_size(self, instance, value):
    print(f'  [on_size] size={value}')
    orig_on_size(self, instance, value)
SomeWidget.on_size = traced_on_size

# 追踪 on_touch_down / on_touch_move / on_touch_up
orig_touch = SomeWidget.on_touch_down
def traced_touch(self, touch):
    print(f'  [on_touch_down] pos={touch.pos}')
    return orig_touch(self, touch)
SomeWidget.on_touch_down = traced_touch
```

### 2.4 截屏保存

```python
from kivy.graphics import Fbo, Color, Rectangle

def screenshot(widget, filename='debug_screenshot.png'):
    fbo = Fbo(size=widget.size)
    with fbo:
        Color(1, 1, 1, 1)
        Rectangle(size=widget.size, texture=widget.texture_id if hasattr(widget, 'texture_id') else None)
    fbo.draw()
    fbo.texture.save(filename)
```

### 2.5 强制 Layout 重算

```python
def force_layout(widget):
    widget.do_layout()
    from kivy.clock import Clock
    Clock.tick()
```

### 2.6 样式与主题调试

```python
# 查看绘制指令
print(widget.canvas.before.children)
print(widget.canvas.children)
print(widget.canvas.after.children)

# 查看属性
print(f'color={widget.color}' if hasattr(widget, 'color') else '')
print(f'font_size={widget.font_size}' if hasattr(widget, 'font_size') else '')
```

### 2.7 辅助色块定位法

```python
from kivy.graphics import Color, Rectangle

with widget.canvas.after:
    Color(1, 0, 0, 0.3)  # 红色半透明
    rect = Rectangle(pos=widget.pos, size=widget.size)

# 需要在 pos/size 变化时更新
widget.bind(pos=lambda inst, val: setattr(rect, 'pos', val),
            size=lambda inst, val: setattr(rect, 'size', val))
```

### 2.8 组件树 Dump

```python
def dump_tree(widget, indent=0):
    print(f'{"  "*indent}{widget.__class__.__name__}: '
          f'size={widget.size} pos={widget.pos} '
          f'opacity={widget.opacity} visible={widget.visible}')
    for child in widget.children:
        dump_tree(child, indent + 1)
```

### 2.9 焦点与输入调试

```python
# 查看焦点
print(f'focus={widget.focus}' if hasattr(widget, 'focus') else 'no focus property')

# 追踪焦点
widget.bind(focus=lambda inst, val: print(f'focus: {inst} -> {val}'))

# 追踪键盘
from kivy.core.window import Window
Window.bind(on_key_down=lambda *args: print(f'key_down: {args}'))
```

### 2.10 信号/回调追踪

```python
# 追踪 Kivy Property 变化
widget.bind(some_property=lambda inst, val: print(f'some_property changed: {val}'))

# 追踪自定义事件
widget.register_event_type('on_custom_event')
widget.bind(on_custom_event=lambda inst, *args: print(f'custom_event: {args}'))
```

### 2.11 性能分析

```python
# 渲染性能
from kivy.clock import Clock
import time

_start_time = 0

def trace_start(dt):
    global _start_time
    _start_time = time.perf_counter()

def trace_end(dt):
    dt_ms = (time.perf_counter() - _start_time) * 1000
    if dt_ms > 16:
        print(f'  [Frame SLOW] {dt_ms:.1f}ms')

Clock.schedule_before(trace_start)
Clock.schedule_after(trace_end)
```

---

## 三、Kivy 特有陷阱

### 1. Clock.schedule_once(0) 不是立即执行

`Clock.schedule_once(callback, 0)` 在下一帧执行，不是立即。

**解决方案**：需要立即执行时直接调用函数。

### 2. size_hint 与 size 的优先级

当 `size_hint` 不为 None 时，`size` 会被布局管理器覆盖。

**解决方案**：需要手动控制尺寸时设 `size_hint=(None, None)` 或 `size_hint_x=None` / `size_hint_y=None`。

### 3. pos 是相对于父组件的

`widget.pos` 是相对于父组件的坐标，不是窗口坐标。

**解决方案**：需要窗口坐标时用 `widget.to_window(*widget.pos)`。

### 4. canvas 指令不会自动跟随 pos/size

在 `canvas` 中添加的绘制指令不会自动跟随组件的 pos/size 变化。

**解决方案**：绑定 pos 和 size 变化来更新绘制指令。

```python
with widget.canvas:
    rect = Rectangle(pos=widget.pos, size=widget.size)
widget.bind(pos=lambda inst, val: setattr(rect, 'pos', val),
            size=lambda inst, val: setattr(rect, 'size', val))
```

### 5. opacity=0 不等于 visible=False

`opacity=0` 组件仍然接收触摸事件，`visible=False` 不接收。

**解决方案**：需要完全隐藏时用 `visible=False`。

### 6. ScrollView 的 scroll_type 和 effect

ScrollView 默认只支持垂直滚动，需要设置 `do_scroll_x=True` 启用水平滚动。

**解决方案**：检查 `do_scroll_x` / `do_scroll_y` 和 `scroll_type` 设置。
