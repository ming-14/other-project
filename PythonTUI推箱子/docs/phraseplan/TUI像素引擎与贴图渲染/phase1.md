# Phase 1: 颜色系统与像素缓冲区

## 状态: ✅ 完成

## 实现内容

### color.py
- `Color` 类：RGB颜色，不可变，slots优化
- TrueColor ANSI码生成：`fg_truecolor()`, `bg_truecolor()`
- ANSI 256色转换：`to_256()`, `fg_256()`, `bg_256()`
- 工厂方法：`from_hex()`, `from_256()`
- `_scale_256()` / `_unscale_256()`：6级色彩立方体映射

### pixel_buffer.py
- `PixelBuffer` 类：2D像素数组，支持Color|None(透明)
- 像素读写：`get_pixel()`, `set_pixel()`
- 填充：`fill()`, `clear()`
- 贴图blit：`blit(sprite_data, x, y)`，透明像素跳过，边界裁剪
- 缓冲区blit：`blit_buffer()`
- 裁剪：`crop()`
- 数据导入导出：`to_data()`, `from_data()`
- Debug接口：`debug_dump()`, `debug_pixel_at()`, `debug_row()`

## 测试: 53个全部通过
- test_color.py: 29个
- test_pixel_buffer.py: 24个

## 经验教训
1. `_scale_256()` 必须clamp到0-5，`round((255-35)/40)=6`会越界
2. 灰度阶梯索引也需clamp到0-23，否则可能产生>255的色号
