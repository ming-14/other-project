# Phase 4: sokoban集成——LayoutEngine改用像素引擎

## 状态: ✅ 完成

## 实现内容

### LayoutEngine改动
- 移除 `TileRenderer` 依赖，改用 `HalfBlockRenderer` + `SpriteSheet`
- `_draw_map_area()` 重写：
  1. 创建 `PixelBuffer(map_w * 8, map_h * 8)`
  2. 遍历每个地图格子，blit对应8×8贴图
  3. `HalfBlockRenderer.render()` 渲染PixelBuffer为ANSI行列表
  4. 居中写入ScreenBuffer
- 标题栏、状态栏、边框保持字符渲染（不变）
- `_TILE_SPRITES` 字典：TileType → Sprite 映射
- `SPRITE_SIZE = 8`：贴图尺寸常量

### 导入方式
- `layout_engine.py` 使用绝对导入 `from src.tui_pixel.xxx`
- 相对导入 `...tui_pixel` 会超出顶层包，不可用

### use_color参数
- True → ColorMode.TRUECOLOR (24bit RGB)
- False → ColorMode.ANSI256 (256色回退)

## 测试: 116个全部通过
- tui_pixel引擎: 109个
- 集成测试: 7个（3关渲染、无颜色、won/all_clear状态、小终端）

## 验证
- 3关全部渲染成功
- LayoutEngine import OK
- PixelBuffer → HalfBlockRenderer → ScreenBuffer 管线完整
