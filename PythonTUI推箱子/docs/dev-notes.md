# 开发记忆

## 2026-07-25: 大Phrase1 实现基本游戏引擎

### 完成状态
全部6个小Phrase已完成，80个单元测试通过，pty-agent端到端测试通过。

### 经验教训
1. **Sokoban地图格式**: `*` 表示箱子在目标点上，`+` 表示玩家在目标点上。解析时需要同时记录到 boxes 和 targets 集合。
2. **地图数据结构设计**: grid 只存储底层地块（FLOOR/TARGET/WALL），玩家和箱子位置用独立集合管理，避免复合状态。
3. **Python模块导入**: `from __future__ import annotations` 会导致模块级字典中 dataclass 构造函数在类定义完成前不可用，不要在 tile_renderer.py 中使用。
4. **dataclass vs enum 命名冲突**: `TileStyle("+", "")` 可能被误解析为 `TileType("+", "")`，注意类名区分。
5. **python -m 运行**: `python -m src.main` 时需要在 main.py 中添加 `sys.path`，且相对导入 `..data` 会超出顶层包，应将 data 放在 engine 包内。
6. **undo 系统**: 需要同时保存 steps 和 pushes，不能只减 steps。
7. **关卡设计**: 测试用的关卡要注意玩家周围的实际地块，不要假设方向可通行。

## 2026-07-25: 大Phrase2 全屏TUI游戏体验

### 完成状态
全部4个小Phrase已完成，110个单元测试通过，pty-agent端到端测试通过。

### 经验教训
1. **ScreenBuffer设计**: 基于Cell的缓冲区（存char+fg+bg）在处理ANSI颜色时非常麻烦，因为ANSI码是多字符的。改为基于行的缓冲区（每行存完整带ANSI码的字符串），简单可靠。
2. **双宽渲染**: 每个地图格子用2个终端列宽（`██`、`♦♦`等），地图视觉上方正清晰。
3. **布局引擎**: 直接构建完整行字符串比逐Cell写入更高效，也避免了ANSI码被拆散的问题。
4. **终端尺寸检测**: `os.get_terminal_size()` 在Windows上可靠，但pty-agent环境下可能返回默认值。
5. **差异更新**: 基于行的差异更新（对比前后行字符串）比基于Cell的更简单，性能也足够。当前临时改为全量输出（每帧ANSI_CLEAR+全部行），差异更新在pty-agent condrv模式下有显示bug需修复。

## 2026-07-25: 关卡3修复与全关卡通关测试

### 完成状态
关卡3数据bug已修复，3个关卡全部通关测试通过。

### 修复内容
1. **关卡3数据bug**: 原关卡3使用`.$.`格式，每行产生2个目标+1个箱子，两行共4目标2箱子，无法通关。重新设计为交叉布局（`# .$ #` / `# $@.#`），2箱子2目标。

### 通关记录
- 关卡1: Steps:1, Pushes:1（向下推箱子到目标）
- 关卡2: Steps:7, Pushes:2（解法：右→上→左(推)→右→下→下→左(推)）
- 关卡3: Steps:10, Pushes:3（解法：d→w→a(推Box1左)→w→a→a→s→s→d(推Box2右)→d(推Box2右到目标)）

### 测试修复
1. **test_wall_does_not_increment_steps**: 原测试加载关卡1按左键，但关卡1玩家左侧不是墙。改为加载关卡0按上键（上方是墙）。
2. **test_swap_and_flush / test_swap_and_flush_no_diff**: ScreenBuffer已改为全量输出，swap_and_flush始终返回rows数。更新测试期望值。

### 经验教训
1. **关卡设计**: `.$.`格式会导致目标数>箱子数，设计关卡时必须确保boxes==targets。MapEngine已有验证（boxes<targets抛异常），但boxes>targets也应在设计时避免。
2. **推箱子解法验证**: 设计时必须手动验证解法可行性，特别是注意不要把已到位的箱子推离目标。
3. **ScreenBuffer性能**: 全量输出导致outputOffset增长极快（3关测试累计20MB+），差异更新修复是优先事项。

## 2026-07-27: 大Phase4 TUI像素引擎与贴图渲染

### 完成状态
全部4个小Phase已完成，116个单元测试通过，3关全部渲染成功。

### 实现内容
1. **tui_pixel引擎**（独立包 `src/tui_pixel/`）：
   - `color.py`: Color类，TrueColor/ANSI256双模式，RGB↔256色转换
   - `pixel_buffer.py`: PixelBuffer，2D像素数组，blit/裁剪/debug接口
   - `sprite.py`: Sprite/SpriteSheet，贴图定义与管理
   - `renderer.py`: HalfBlockRenderer，▀/▄/█半块渲染，PixelBuffer→ANSI行
   - `sprites/sokoban.py`: 7种8×8贴图（墙/地板/目标/箱子/箱子到位/玩家/玩家在目标）
2. **sokoban集成**：LayoutEngine._draw_map_area()改用PixelBuffer+blit+渲染管线

### 经验教训
1. **_scale_256越界**: `round((255-35)/40)=6`超出0-5范围，必须clamp。灰度阶梯索引也需clamp到0-23。
2. **相对导入限制**: `layout_engine.py`在`src/engine/render/`下，`...tui_pixel`超出顶层包，必须用绝对导入`from src.tui_pixel.xxx`。
3. **半块渲染ANSI优化**: 相邻同fg/bg不重复输出ANSI码，但█和▀切换时需要reset。
4. **贴图透明像素**: TARGET和PLAYER贴图有透明像素，blit时透明不覆盖目标，这是正确行为。
5. **8×8贴图在终端占位**: 8列宽×4行高（每2像素行=1终端行），地图居中计算需用像素宽度而非终端列数。

## 2026-07-27: 引擎升级 - alpha透明通道

### 完成状态
Color/PixelBuffer/Sprite/Renderer全部升级支持RGBA，127个单元测试通过。

### 改动内容
1. **Color加alpha通道**: `Color(r, g, b, a=255)`，`is_opaque`/`is_transparent`属性，`alpha_blend(bg)`方法
2. **TRANSPARENT常量**: `Color(0,0,0,0)`，替代None表示全透明
3. **PixelBuffer**: 像素类型从`Color|None`变为`Color`，blit支持alpha混合（0<a<255时与目标混合）
4. **HalfBlockRenderer**: 新增`bg_color`参数（默认黑色），`_flatten_pixel()`将半透明像素与bg_color混合后输出
5. **贴图升级**:
   - TARGET: 菱形周围加半透明红色发光晕(`TARGET_GLOW`, a=80)
   - BOX: 底部加半透明阴影(`BOX_SHADOW`, a=60)
   - BOX_ON_TARGET: 角落加半透明绿色发光(`BOX_OK_GLOW`, a=50)
   - PLAYER: 轮廓加半透明青色光(`PLAYER_GLOW`, a=40)
6. **LayoutEngine**: 传`bg_color=FLOOR_COLOR`给renderer，半透明像素与地板色混合

### 经验教训
1. **alpha混合公式**: `out = src * a + bg * (255-a)`，整数运算用`(src*sa + bg*da + 127) // 255`避免偏移
2. **向后兼容**: PixelBuffer.blit仍接受TRANSPARENT(alpha=0)作为跳过，opaque(alpha=255)直接覆盖
3. **渲染flatten**: 半透明像素在渲染时必须与背景色混合成不透明色，终端不支持半透明
4. **debug_dump三态**: 不透明→█，半透明→≈，全透明→·
