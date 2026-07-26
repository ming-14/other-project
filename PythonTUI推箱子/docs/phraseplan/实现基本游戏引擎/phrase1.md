# Phrase 1: 核心数据结构与地图引擎

## 状态: ✅ 已完成

## 目标

建立推箱子游戏最底层数据结构：位置、地块类型、地图。地图引擎负责地图的创建、解析、查询、修改。

## 设计

### 数据结构

- `Position`: 不可变值对象，表示二维坐标 (row, col)，支持加减运算
- `TileType`: 枚举，地块类型
  - WALL = '#' 墙壁
  - FLOOR = ' ' 空地
  - TARGET = '.' 目标点
  - BOX = '$' 箱子
  - BOX_ON_TARGET = '*' 箱子在目标点上
  - PLAYER = '@' 玩家
  - PLAYER_ON_TARGET = '+' 玩家在目标点上
- `GameMap`: 地图实体
  - 存储网格数据（二维列表）
  - 记录玩家位置
  - 记录所有箱子位置（set）
  - 记录所有目标点位置（set，不可变）

### 地图引擎 (MapEngine)

- 从字符串列表解析地图（标准Sokoban格式）
- 查询指定位置的TileType
- 修改指定位置的TileType
- 获取地图尺寸
- 验证地图合法性（有且仅有一个玩家，箱子数>=目标点数）
- Debug接口：导出地图为字符串、打印地图状态

### 文件结构

```
src/
  engine/
    __init__.py
    position.py      # Position
    tile.py          # TileType
    map.py           # GameMap
    map_engine.py    # MapEngine
```

## 验收标准

- [ ] Position支持基本运算
- [ ] TileType枚举完整
- [ ] GameMap能从字符串解析地图
- [ ] MapEngine能查询、修改地块
- [ ] 地图合法性校验通过
- [ ] Debug接口可用
- [ ] 单元测试全部通过
