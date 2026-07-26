# Phrase 4: 终端渲染引擎

## 状态: ✅ 已完成

## 目标

实现终端屏幕渲染引擎，将GameMap渲染为终端输出，支持ANSI转义序列、双缓冲、屏幕差异更新。

## 设计

### RenderEngine

- 将GameMap渲染为屏幕字符串
- 支持ANSI颜色/样式（墙壁灰色、箱子棕色、目标点红色、玩家绿色等）
- 双缓冲：维护前后缓冲区，仅输出差异部分，减少闪烁
- 支持纯文本模式（无ANSI）用于调试
- 屏幕尺寸适配

### TileRenderer

- 每种TileType对应的渲染字符和颜色
- 可配置的渲染方案（方便后续换肤）

### 文件结构

```
src/engine/
  render_engine.py  # RenderEngine
  tile_renderer.py  # TileRenderer, 渲染配置
```

### 渲染字符方案

| TileType | 字符 | ANSI颜色 |
|----------|------|----------|
| WALL     | █    | 灰色 |
| FLOOR    | ·    | 暗灰 |
| TARGET   | ○    | 红色 |
| BOX      | ■    | 棕色 |
| BOX_ON_TARGET | ★ | 绿色 |
| PLAYER   | ♦    | 蓝色 |
| PLAYER_ON_TARGET | ♦ | 蓝色 |

### Debug接口

- 导出当前缓冲区内容
- 显示渲染统计（帧数、差异行数）

## 验收标准

- [ ] GameMap正确渲染为终端输出
- [ ] ANSI颜色正确应用
- [ ] 双缓冲差异更新正常工作
- [ ] 纯文本模式可用
- [ ] Debug接口可用
- [ ] 单元测试全部通过
