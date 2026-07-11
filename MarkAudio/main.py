# +-+-+-+-+-++-+-+-+-+-++-+-+-+-+-++-+-+-+-+-+
# developed by Rikka
# time: 2024/11/16
# version: 1.0
# Made with Visual Studio Code
# use to 对视频进行转音频，并为音频加上标题朗读信息
# 使用场景：没有屏幕的MP3
# +-+-+-+-+-++-+-+-+-+-++-+-+-+-+-++-+-+-+-+-+

import os
import subprocess

# function: 运行环境jiance
def checkEnvironment():
    try:
        subprocess.run("ffmpeg -version", check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return "ok"
    except subprocess.CalledProcessError as e:
        return e.stderr.decode()

# function: 合并音频文件
# audio_files: 音频文件列表, 格式为列表
#   e.g.['file1.wav', 'file2.wav', 'file3.wav']
# output_file: 输出文件路径
def mergeAudioFiles(audio_files, output_file):
    # 构建FFmpeg命令
    command = ['ffmpeg', '-i', audio_files[0]]
    for audio_file in audio_files[1:]:
        command.extend(['-i', audio_file])
    
    # 构建过滤器字符串
    filter_complex = ''.join([f'[{i}:a]' for i in range(len(audio_files))]) + f'concat=n={len(audio_files)}:v=0:a=1[out]'
    command += ['-filter_complex', filter_complex, '-map', '[out]', output_file]
    
    # 执行命令
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return "ok"
    except subprocess.CalledProcessError as e:
        return e.stderr.decode()

# function: 遍布目录  1.合成输出标题（文件名）朗读音频；
#                    2.将指定视频转音频；
#                    3.合并音频文件（标题音频+1秒的空音频+视频音频）；
# directory: 指定视频目录
# temp1: 标题朗读音频临时存放目录
# temp2: 视频转音频临时存放目录
# temp3: 空音频存放目录
# output: 输出目录
def executeProgramInDirectory(directory, temp1, temp2, temp3, output):
    # 遍历指定目录
    for root, dirs, files in os.walk(directory):
        for filename in files:
            # 获取文件的完整路径
            filePath = os.path.join(root, filename)
            fileSafeName = os.path.splitext(filename)[0].replace('”', "'").replace('“', "'") # 去除扩展名以及”“
            SafeOutPut = temp1.replace('”', "'").replace('“', "'") + fileSafeName.replace('”', "'").replace('“', "'")
            print(f"正在处理文件: {filePath}")

            # +-+-+- 1.创建标题音频 +-+-+-
            if not os.path.exists(f"{SafeOutPut}.wav"):
                command = f'Add-Type –AssemblyName System.Speech;\
                    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;\
                    $synth.SetOutputToWaveFile("{SafeOutPut}.wav");\
                    $synth.Speak("{fileSafeName}"); $synth.Dispose()'
                subprocess.Popen(['powershell', '-Command', command])
            else:
                print(f"标题音频{filename}已存在")

            # +-+-+- 2.视频转音频 +-+-+-
            if not os.path.exists(f"{temp2}{fileSafeName}.mp3"):
                subprocess.run(f'ffmpeg -i "{filePath}" "{temp2}{fileSafeName}.mp3"')
            else:
                print(f"音频{filename}已存在")

            # +-+-+- 3.合并音频 +-+-+-
            if not os.path.exists(f"{output}{fileSafeName}.mp3"):
                audioFiles = [
             f'{SafeOutPut}.wav',
             temp3,
             f'{temp2}{fileSafeName}.mp3']
                outputFile = f"{output}{fileSafeName}.mp3"
                if mergeAudioFiles(audioFiles, outputFile) != "ok":
                    print(f"合并音频{filename}失败")
            else:
                print(f"音频{filename}已存在")


if __name__ == "__main__":
    if checkEnvironment() != "ok":
        print("unable to find ffmpeg, please install it first")
        exit(1)
    executeProgramInDirectory(
        '.\\yourvideo',
        '.\\work\\',
        '.\\work2\\',
        '.\\empty_audio.wav',
        '.\\work3\\')
