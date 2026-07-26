# Phrase 1: 终端尺寸检测与全屏缓冲区

## 状态: ✅ 已完成

## 目标

实现终端尺寸检测、全屏虚拟缓冲区、双缓冲差异更新。

## 设计

### ScreenBuffer

- 维护一个二维字符缓冲区 (rows x cols)，每个单元格包含字符+颜色
- 支持在任意位置写入字符/字符串
- 支持写入带ANSI颜色的文本
- diff输出：对比前后缓冲区，只输出变化部分

### TerminalInfo

- 获取终端尺寸（Windows: `os.get_terminal_size()` 或 `ctypes` 调用）
- 监听终端尺寸变化（WINCH信号 / 定期轮询）
- 提供安全的最小尺寸

### 文件结构

```
src/engine/
  screen_buffer.py   # ScreenBuffer, CellData
  terminal_info.py   # TerminalInfo
```

## 验收标准

- [ ] 能正确获取终端尺寸
- [ ] ScreenBuffer支持写入和读取
- [ ] 双缓冲差异更新正常工作
- [ ] 单元测试通过
