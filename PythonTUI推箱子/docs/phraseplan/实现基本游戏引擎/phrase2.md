# Phrase 2: 移动与碰撞引擎

## 状态: ✅ 已完成

## 目标

实现玩家移动、推箱子、碰撞检测逻辑。这是推箱子游戏的核心玩法引擎。

## 设计

### MoveEngine

- 玩家移动方向：上下左右
- 移动规则：
  1. 玩家前方是空地/目标点 → 直接移动
  2. 玩家前方是箱子，箱子前方是空地/目标点 → 推箱子并移动
  3. 其他情况（墙、箱子前方有墙/箱子）→ 移动失败
- 返回移动结果（成功/失败，以及移动类型：普通移动/推箱子）
- 移动后更新GameMap状态（玩家位置、箱子位置、地块类型）
- 不关心渲染和输入，纯逻辑层

### MoveResult

- success: bool
- move_type: 'move' | 'push' | None
- direction: Direction
- box_position: Position | None（推箱子时箱子的新位置）

### Direction

- 枚举：UP, DOWN, LEFT, RIGHT
- 与Position偏移量的映射

### 文件结构

```
src/engine/
  direction.py      # Direction
  move_engine.py    # MoveEngine, MoveResult
```

## 验收标准

- [ ] Direction枚举与偏移映射正确
- [ ] 玩家可以正常移动到空地/目标点
- [ ] 推箱子逻辑正确（箱子前方无阻挡时推动）
- [ ] 碰撞检测正确（墙壁、箱子堆叠阻挡）
- [ ] 移动后GameMap状态正确更新
- [ ] MoveResult返回正确的移动信息
- [ ] 单元测试全部通过
