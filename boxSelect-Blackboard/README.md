# boxSelect-Blackboard
## 前言

从0开始学习图像识别，一天极限手搓，边学边做T_T

部分内容在学习过程使用到了AI

基本就是一个测颜色的小软件

就这样了，后续也不想改了

放 Github 上面只是为了 backup，希望没人看，不知道会不会成为黑历史 :sweat:，大佬看着玩就好

Python Logo 来自于 [SAWARATSUKI の Github]([SAWARATSUKI (SAWARATSUKI) (github.com)](https://github.com/SAWARATSUKI))

---

写这个程序主要因为觉得某人の研习——全自动黑板擦很好玩

虽然...确实有点土，但是还是很期待有一个小车在黑板上跑来跑去

现在做嵌入式都这么高级了吗？用集成化超高的 Micro:bit。当然，最nb的当然是老师帮忙（dai）做:label:

---

注意：本程序仅仅是演示，在具体项目中实施仍需完善代码


## OpenCVs是什么

OpenCV是一个基于Apache2.0许可（开源）发行的跨平台计算机视觉和机器学习软件库，可以运行在Linux、Windows、Android和Mac OS操作系统上。 [1]它轻量级而且高效——由一系列 C 函数和少量 C++ 类构成，同时提供了Python、Ruby、MATLAB等语言的接口，实现了图像处理和计算机视觉方面的很多通用算法。
OpenCV用C++语言编写，它具有C ++，Python，Java和MATLAB接口，并支持Windows，Linux，Android和Mac OS，OpenCV主要倾向于实时视觉应用，并在可用时利用MMX和SSE指令， 如今也提供对于C#、Ch、Ruby，GO的支持。


## 环境

Python

​		Windows 7 x64：https://mirrors.huaweicloud.com/python/3.8.9/python-3.8.9-amd64.exe

​		Windows 10 及以上：https://mirrors.huaweicloud.com/python/3.9.9/python-3.9.9-amd64.exe

​		OpenCV：`pip install -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple opencv-python`



## 原理

打开摄像头，循环读取每一帧，然后对每一帧筛颜色，去噪，膨胀。接着画框框，筛框框。再对框框边缘识别
