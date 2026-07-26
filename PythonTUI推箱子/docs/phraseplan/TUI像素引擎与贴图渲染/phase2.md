# Phase 2: 贴图系统与半块渲染器

## 状态: ✅ 完成

## 实现内容

### sprite.py
- `Sprite` 类：不可变贴图，name + PixelData，支持get_pixel、to_buffer、debug_dump
- `SpriteSheet` 类：贴图表，名字→Sprite映射，add/get/contains

### renderer.py
- `ColorMode` 枚举：TRUECOLOR / ANSI256
- `HalfBlockRenderer` 类：PixelBuffer → ANSI字符串行列表
  - `_compute_cell()`: 核心半块逻辑（▀/▄/█/空格）
  - `_render_row_pair()`: 渲染一对像素行，含ANSI码优化（相邻同色合并）
  - `render()`: 完整渲染
  - `render_plain()`: 纯文本debug渲染
  - `render_debug()`: 显示半块字符选择逻辑

### 半块渲染逻辑
| 上像素 | 下像素 | 字符 | 说明 |
|--------|--------|------|------|
| None | None | 空格 | 都透明 |
| Color | None | ▀ | 上色下透明，fg=上色 |
| None | Color | ▄ | 上透明下色，fg=下色 |
| Color | Color(同) | █ | 同色全块，fg=色 |
| Color | Color(异) | ▀ | 异色，fg=上色，bg=下色 |

## 测试: 85个全部通过（Phase1: 53 + Phase2: 32）

## 经验教训
1. render_plain中，某列上下都透明时输出空格，不是█——测试期望值需匹配实际逻辑
2. ANSI码优化：相邻同fg/bg不重复输出ANSI码，但█和▀切换时需要reset
