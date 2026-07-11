# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-
# Rikka.py
# 许可证：The MIT License
# That means you can use it freely but not call me.
# However, you should remove my name in the project.
# time: 2024/11
# version: 2.0
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-
import cv2
import numpy as np
import log

# +-+-+-+-+-+-+-+-+-+-+-
# function: 列出所有摄像头
# return: 一个列表，包含所有摄像头的索引
# +-+-+-+-+-+-+-+-+-+-+-
def list_cameras():
    index = 0
    arr = []
    while True:
        # 尝试打开摄像头
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            arr.append(index)
            cap.release()
        else:
            break
        index += 1
    return arr

# +-+-+-+-+-+-+-+-+-+-+-
# function: 处理图像
# frame: 输入图像
# lower_green: 最小的阈值
# upper_green: 最大的阈值
# return: 处理后的图像
# +-+-+-+-+-+-+-+-+-+-+-
def recognize(frame, lower_green = np.array([35, 50, 50]), upper_green = np.array([95, 255, 255])):
        # 读取图片，image 就是后面处理的图像
        image = frame
        # 转换为HSV色彩空间
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # 创建掩模
        mask = cv2.inRange(hsv, lower_green, upper_green)

        # 去噪声和增强黑板轮廓
        kernel = np.ones((5, 5), np.uint8)
        morphed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        # 去除小区域
        kernel_open = np.ones((5, 5), np.uint8)
        morphed = cv2.morphologyEx(morphed, cv2.MORPH_OPEN, kernel_open)

        if log.debug:
            cv2.imshow('remove', morphed) # 展示处理并二值后的图片

        # 找轮廓
        contours, _ = cv2.findContours(morphed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # 遍历所有轮廓并绘制边界框
        for contour in contours:
            # 计算每个轮廓的面积
            area = cv2.contourArea(contour)
            x, y, w, h = cv2.boundingRect(contour)

            # 过滤掉不符合条件的轮廓
            if area > 1000:  # 最小轮廓面积
                # 绘矩形框
                cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)


        # 遍历所有框起来的地方，使用边缘检测提取粉笔字
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 500:  # 过滤掉较小的轮廓
                x, y, w, h = cv2.boundingRect(contour)

                # 提取小黑板区域
                blackboard_region = image[y:y + h, x:x + w]
                gray_region = cv2.cvtColor(blackboard_region, cv2.COLOR_BGR2GRAY)

                # 使用Canny边缘检测提取粉笔字
                edges = cv2.Canny(gray_region, 100, 200)

                # 将边缘图绘制到原图上
                # 创建一个与原图相同的空白图像
                colored_edges = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
        
                # 叠加边缘
                image[y:y + h, x:x + w] = cv2.addWeighted(image[y:y + h, x:x + w], 0.3, colored_edges, 0.7, 0)

        return image

# +-+-+-+-+-+-+-+-+-+-+-
# function: 使用摄像头测试
# capId: 摄像头的id
# title: 窗口标题
# +-+-+-+-+-+-+-+-+-+-+-
def capExample(capId = 0, title = "Rikka"):
    if log.debug:
        log.print(f"open {capId}")

    # 打开摄像头
    cap = cv2.VideoCapture(capId)

    # 检查摄像头是否成功打开
    if not cap.isOpened():
        log.print("无法打开摄像头")
        exit()

    while True:
        ret, frame = cap.read()
        if not ret:
            log.print("无法读取视频帧")
            break

        cv2.imshow(title, recognize(frame = frame))

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    log.print("结束本次处理")

    # 释放摄像头资源
    cap.release()
    # 关闭所有 OpenCV 窗口
    cv2.destroyAllWindows()

# +-+-+-+-+-+-+-+-+-+-+-
# function: 使用图片测试
# imgPath: 图片路径
# title: 窗口标题
# +-+-+-+-+-+-+-+-+-+-+-
def imgExample(imgPath, title = "Rikka"):
    try:
        cv2.imshow(title, recognize(frame = cv2.imread(imgPath)))
    except Exception as e:
        log.print(e)
        raise FileNotFoundError

    cv2.waitKey(0)
    cv2.destroyAllWindows()
    log.print("结束本次处理")