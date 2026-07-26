# Phrase 3: 胜利判定引擎

## 状态: ✅ 已完成

## 目标

实现胜利条件判定：所有目标点上都有箱子时游戏胜利。

## 设计

### WinEngine

- 检查当前地图是否满足胜利条件
- 胜利条件：所有目标点位置上都有箱子（即目标点集合是箱子位置集合的子集）
- 返回WinCheckResult

### WinCheckResult

- won: bool
- total_targets: int
- covered_targets: int

### 文件结构

```
src/engine/
  win_engine.py     # WinEngine, WinCheckResult
```

## 验收标准

- [ ] 所有箱子在目标点上时判定胜利
- [ ] 部分箱子在目标点上时不判定胜利
- [ ] 无箱子在目标点上时不判定胜利
- [ ] WinCheckResult返回正确的统计信息
- [ ] 单元测试全部通过
