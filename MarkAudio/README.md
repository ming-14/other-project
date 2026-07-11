# MarkAudio

## 前言

我好像很难用一句话来简洁地说明这个程序的作用

方便你理解，我会列我的使用场景以及程序执行内容

小C想把自己爱听的说书拷贝到MP3上，  
可是这个MP3没有屏幕（别问我Why），How to solve it?  
一天。小C在逛 Github 的时候发现了这个perfect程序，可以totally解决他的问题，  
这个程序会遍布小C指定的目录，把这个目录下的所有视频转成音频，  
**接着，这个程序会生成每个视频文件名（当然没有扩展名啦~）（标题）的朗读文件，**
**并与音频拼接。**

> How wonderful! It isn't it?



## 运行环境

1. 安装 Pyhton；  
2. 安装 FFmpeg，并已加入系统Path。



## 项目目录

**MarkAudio**  
├─main.py 主程序  
└─example 示例，实际执行时不需要该文件夹  
    ├─video  
    ├─work  
    ├─work2  
    └─work3



## 食用方法

**main.py**  
核心函数：**executeProgramInDirectory**(directory, temp1, temp2, temp3, output)  
function: 遍布目录  1.合成输出标题（文件名）朗读音频；  
                   2.将指定视频转音频；  
                   3.合并音频文件（标题音频+空音频+视频音频）；  
directory: 指定视频目录  
temp1: 标题朗读音频临时存放目录  
temp2: 视频转音频临时存放目录  
temp3: 空音频存放目录  
output: 输出目录  
  
**tips**：空音频要提前准备好，  
  
FFmpeg 生成空音频：`ffmpeg -flavfi -i anullsrc=r=44100:cl=stereo -t (time) empty_audio.wav`

