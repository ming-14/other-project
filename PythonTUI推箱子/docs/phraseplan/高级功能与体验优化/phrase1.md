# Phrase 1: ScreenBuffer差异更新修复与技术债清理

## 状态: 待执行

## 目标
修复ScreenBuffer差异更新在pty-agent condrv模式下的显示bug，消除全量输出导致的性能问题；清理旧版渲染引擎残留文件。

## 背景
当前ScreenBuffer的swap_and_flush采用全量输出（每帧ANSI_CLEAR+全部行），是因为之前差异更新在pty-agent condrv模式下出现显示混乱（重玩关卡时屏幕残留旧内容）。全量输出虽然功能正确，但每帧输出量极大（20KB+），outputOffset增长过快。

## 具体任务

### 1. 分析差异更新bug根因
- 旧差异更新逻辑：对比front/back缓冲区，仅输出变化的行（ANSI光标定位+行内容）
- 可能的bug原因：
  a. 重玩/切关时front缓冲区未正确重置
  b. ANSI光标定位序列在condrv模式下行为不一致
  c. 行内容比较时ANSI码干扰

### 2. 修复差异更新
- 确保resize/restart/init_screen时front缓冲区正确重置
- 差异更新逻辑：遍历行，front[i]!=back[i]时用ANSI_MOVE_TO定位到行首再输出
- 保留全量输出作为fallback（init_screen后首次渲染用全量）

### 3. 清理旧版文件
- 删除 src/engine/render_engine.py（V1渲染引擎，已弃用）
- 删除 src/engine/tile_renderer.py（V1渲染器，已弃用）
- 删除对应测试文件 tests/engine/test_render_engine.py
- 确认GameLoop无任何引用

## 验证标准
- [ ] swap_and_flush在无变化时返回0，有变化时返回变化行数
- [ ] pty-agent端到端测试：游戏正常运行，无显示混乱
- [ ] 重玩关卡（R键）后屏幕正确刷新
- [ ] 切换关卡后屏幕正确刷新
- [ ] 旧版文件已删除，无引用残留
- [ ] 110个单元测试全部通过
