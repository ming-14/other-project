# base
我们的工程在`src`，这是一个推箱子游戏命令行版本，采用Python 3.11.9

# 规则
## 架构
文件夹分好层，使用干净架构。不可以出现god文件，god类等
扩展性要好，低耦合，特别是引擎层一定要分离

开发流程遵循底层->高层，最底层的引擎先写，然后逐步给引擎加功能，然后写中间层，最后写高级功能
尤其是win32api部分，一定是最底层
引擎一定要留好debug接口，就和浏览器dev-tool一样，方便你调试

不要用Textual，因为这是文本框架
## 日志

写好日志规范

## 注释
代码自明，但是基本的，文件开头，类开头，关键位置（比如配置项，易混淆项）要写注释

## 可以使用第三方库
有可以使用的标准库和第三方库就去用，不要写大量代码重复造轮子

## 记忆
除了写你自己的记忆，记忆也要写在`docs/`里面防止反复犯同一个错误

# 开发流程
 -> 计划大phrase（把自己当作游戏策划，策划！不是程序员）
 -> 本phrase实现哪些方面的内容
 -> 写计划方案，分小phrase
 -> 执行小phrase方案
 -> **详细调试，必须保证该phrase完全正常才能下一步**
 -> **更新文档**
 -> git保存
 -> 执行下一个小phrase
 -> ...
 -> 小phrase全部完成，再继续一次综合调试，**程序必须可以完整可玩**
 -> git保存
 -> 计划下一个大phrase
 -> ...
 
 禁止换顺序，但是调试可以额外加在任何位置。写文档必须使用skill:doc-export
 
计划写在docs\phraseplan/{大phrase}/{小phrase}/
比如
```
docs\phraseplan\实现基本游戏引擎\phrase1.md
docs\phraseplan\实现基本游戏引擎\phrase2.md
docs\phraseplan\实现基本游戏引擎\phrase3.md
docs\phraseplan\实现基本游戏引擎\phrase....md
...
```

执行方案，详细调试结束后更新相关phrase标注状态，你也可以查看`docs\phraseplan`看看目前进度

## git

提交前检查

- [] 本phrase任务是否已经完成
- [] 单元集成e2e测是否全部成功，**实际手动测试**是否正确，符合预期

# 调试
**基本检查**：运行拼写检查，pylint，mypy（这些让cbc干） -> 写单元/集成测试，运行单元/集成（写你来写，运行让cbc运行）
**实际运行**：先预留所有检查点，调试接口 -> 让cbc实际用pty-agent手动黑盒测试，任务描述清晰一点，怎么直接跳到测试内容
 必要时你也可以自己实际运行测试
**发现运行时bug**：及时看日志或用调试器debug

bug必须全部修复才能进入下一个phrase

## 调试手段

### 语法类型错误
拼写检查，pylint，mypy
### 单元/集成测试
写在`tests\`，目录复刻src
### 日志
去`logs`找最新的
### 实际测试（非常非常重要），黑盒，必须保证端到端测试ok
**用pty-agent手动测试试玩**，pty-agent在`.agents\skills\pty-agent`，使用说明在`.agents\skills\pty-agent\SKILL.md`，**你给cbc或子代理用pty-agent时要把使用说明的文档路径发出去***而且要告诉他不要stop pty-agent，也不要kill
代码要留调试接口，不要把时间消耗在其他前置游戏内容上

pty-agent推荐配置：屏幕快照模式，svg模式

pty-agent：请阅读skill
不要stop pty-agent，也不要kill不是你新建的会话
### 运行时bug
用pdb
### python的c层炸了，python直接挂了，日志都写不了怎么办
用cdb.exe，windows-debugging有

每次你从压缩状态恢复的时候，都要执行，以读取最新进度

任务执行过程中不要询问用户，不要中断，及时更新文档和记忆记录进度

### cbc子代理
cbc.cmd -p --permission-mode bypassPermissions "你让他干什么活"
任务描述务必十分清晰