# Phrase 5: 输入处理引擎

## 状态: ✅ 已完成

## 目标

实现键盘输入处理引擎，支持方向键、WASD、功能键（R重玩、Q退出等），非阻塞读取。

## 设计

### InputEngine

- 使用 `msvcrt` (Windows) 读取键盘输入
- 非阻塞读取（kbhit + getch）
- 按键映射：将原始输入映射为游戏动作
- 支持方向键（ESC序列）和WASD
- 输入缓冲区管理

### InputAction

- 枚举：MOVE_UP, MOVE_DOWN, MOVE_LEFT, MOVE_RIGHT
- RESTART, QUIT, UNDO, HELP
- NONE（无效输入）

### 文件结构

```
src/engine/
  input_engine.py   # InputEngine, InputAction
```

### 按键映射

| 按键 | 动作 |
|------|------|
| ↑/W | MOVE_UP |
| ↓/S | MOVE_DOWN |
| ←/A | MOVE_LEFT |
| →/D | MOVE_RIGHT |
| R   | RESTART |
| Q/ESC | QUIT |
| Z   | UNDO |
| H   | HELP |

### Debug接口

- 记录最近N次输入
- 显示按键原始值与映射结果

## 验收标准

- [ ] 方向键和WASD正确映射
- [ ] 功能键（R/Q/Z/H）正确映射
- [ ] 非阻塞读取正常工作
- [ ] 无效输入返回NONE
- [ ] Debug接口可用
- [ ] 单元测试全部通过
