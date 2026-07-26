# 大Phase: TUI像素引擎与贴图渲染

## 目标

构建独立的TUI像素渲染引擎，基于半块方格（▀）技术实现终端像素级绘制，支持贴图系统。
然后用该引擎替换sokoban当前的字符渲染，将墙、小人、箱子、目标点等全部替换为8×8像素贴图。

## 核心原理：半块方格像素渲染

终端每个字符单元约为 1:2（宽:高）比例。利用 Unicode 半块字符 `▀`（U+2580 UPPER HALF BLOCK）：
- **前景色** = 上半像素颜色
- **背景色** = 下半像素颜色

这样一个终端字符单元 = 2个垂直像素。8×8像素贴图在终端上占 8列 × 4行。

## 架构设计

引擎独立于sokoban，放在 `src/tui_pixel/` 包下，与 `src/engine/` 平级。sokoban通过适配层调用。

```
src/
├── engine/          # sokoban游戏引擎（已有）
├── tui_pixel/       # TUI像素引擎（新增，独立）
│   ├── __init__.py
│   ├── color.py         # 颜色系统：RGB、ANSI256、TrueColor转换
│   ├── pixel_buffer.py  # 像素缓冲区：2D像素数组，支持贴图blit
│   ├── sprite.py        # 贴图定义：Sprite数据类、SpriteSheet
│   ├── renderer.py      # 半块渲染器：PixelBuffer → 终端ANSI输出
│   └── sprites/         # 内置贴图数据（纯Python字典定义）
│       ├── __init__.py
│       └── sokoban.py   # 推箱子贴图：墙、地板、玩家、箱子、目标、箱子到位、玩家在目标
└── main.py
```

### 低耦合设计

- `tui_pixel` 零依赖 `engine`，完全独立
- `tui_pixel` 只提供像素缓冲区+贴图blit+渲染到stdout的能力
- sokoban的 `LayoutEngine` 改为：构建PixelBuffer → blit贴图 → 调用renderer输出
- sokoban的 `TileRenderer` 被替换为贴图查找+blit逻辑
- ScreenBuffer保留（负责差异更新和终端控制），但内容来源从"字符行"变为"像素渲染后的ANSI行"

### 颜色系统

支持两种模式：
1. **TrueColor（24bit RGB）**：`\033[38;2;R;G;Bm` / `\033[48;2;R;G;Bm`，最精确
2. **ANSI 256色**：RGB→256色映射，兼容性更好

默认TrueColor，可通过参数回退256色。

### 像素缓冲区

- `PixelBuffer(width, height)`：width×height像素，每个像素存 `(r, g, b)` 或 `None`（透明）
- `blit(sprite, x, y)`：将贴图绘制到缓冲区指定位置，透明像素跳过
- `fill(color)`：整体填充
- `get_pixel(x, y)` / `set_pixel(x, y, color)`

### 贴图系统

- `Sprite`：宽×高的像素数据，用 tuple[tuple[tuple[int,int,int]|None,...],...] 定义
  - 外层tuple=行，内层tuple=列，每个元素=(R,G,B)或None(透明)
- `SpriteSheet`：名字→Sprite的映射，方便按名查找
- 贴图数据用纯Python定义（不用外部图片文件），8×8大小

### 半块渲染器

- `HalfBlockRenderer`：将PixelBuffer渲染为ANSI字符串行列表
- 每两行像素合并为一个终端行：遍历每对(上像素, 下像素)
  - 上下同色：用 `█` 全块字符 + fg色
  - 上下不同色：用 `▀` + fg=上色 + bg=下色
  - 上透明下有颜色：用 `▄` 下半块 + fg=下色
  - 上有颜色下透明：用 `▀` + fg=上色
  - 都透明：空格
- 奇数高度：最后一行只有上像素，下像素视为透明

### Debug接口

- `PixelBuffer.debug_dump()`：返回ASCII艺术预览
- `HalfBlockRenderer.debug_render_plain()`：无ANSI纯文本渲染
- `PixelBuffer.debug_pixel_at(x, y)`：返回指定像素颜色

## 小Phase划分

### Phase 1: 颜色系统与像素缓冲区 ✅

**内容**：
- `color.py`：Color命名元组、RGB→ANSI256转换、ANSI转义码生成
- `pixel_buffer.py`：PixelBuffer类，像素读写、fill、blit、clear、debug接口

**完成标准**：Color和PixelBuffer单元测试全部通过，blit操作正确处理透明像素和边界裁剪。

---

### Phase 2: 贴图系统与半块渲染器 ✅

**内容**：
- `sprite.py`：Sprite数据类、SpriteSheet
- `renderer.py`：HalfBlockRenderer，PixelBuffer→ANSI行列表
- 渲染优化：相邻同色像素合并ANSI码、行尾重置

**完成标准**：Sprite定义和查找测试通过，HalfBlockRenderer渲染测试通过（验证▀/▄/█/空格选择逻辑、ANSI码正确性）。

---

### Phase 3: 推箱子8×8贴图定义与验证 ✅

**内容**：
- `sprites/sokoban.py`：定义7种贴图（WALL, FLOOR, TARGET, BOX, BOX_ON_TARGET, PLAYER, PLAYER_ON_TARGET）
- 每张贴图8×8像素，精心设计像素画
- 贴图预览工具：命令行直接输出贴图效果，方便调色和调整

**完成标准**：7张贴图全部定义，debug预览输出可辨认，贴图数据结构测试通过。

---

### Phase 4: sokoban集成——LayoutEngine改用像素引擎 ✅

**内容**：
- 修改 `LayoutEngine._draw_map_area()`：用PixelBuffer替代字符拼接
  - 创建地图大小的PixelBuffer
  - 遍历每个格子，blit对应贴图
  - 用HalfBlockRenderer渲染PixelBuffer为ANSI行
  - 写入ScreenBuffer
- 修改 `TileRenderer` 或移除（贴图替代）
- 标题栏、状态栏、边框保持字符渲染（只有地图区域用像素引擎）
- ScreenBuffer不变，只是内容来源变了

**完成标准**：游戏全屏TUI可玩，地图显示为8×8像素贴图，3关全部通关，110+单元测试通过，pty-agent端到端测试通过。

---

## 非目标（本Phase不做）

- 动画/帧率控制（后续Phase）
- 窗口缩放自适应贴图缩放
- 外部图片文件加载（只用Python定义的贴图）
- 差异更新优化（ScreenBuffer已有，本Phase聚焦像素引擎本身）

## 风险与注意事项

1. **TrueColor兼容性**：部分终端不支持24bit色，需提供256色回退
2. **性能**：每帧渲染PixelBuffer→ANSI字符串，8×8贴图×地图格子数，需关注大地图性能
3. **pty-agent测试**：pty-agent可能不支持TrueColor，测试时可能需要--no-color或256色模式
4. **半块字符宽度**：▀和▄在部分终端可能显示异常，需在多终端验证
5. **ScreenBuffer差异更新**：像素渲染后每行都是长ANSI字符串，差异比较可能变慢，先观察再优化
