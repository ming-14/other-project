# -*- coding: utf-8 -*-
"""
@file       tension_detector.py
@brief      圆形张力表盘识别模块（增强版）
@details    从图像中检测绿色圆弧区域，找出圆形表盘，计算指针角度并转换为 0~100% 的张力值。
            支持两种指针定位模式：间隙检测模式（绿色圆弧缺口）和环形指针检测模式。
            新增绿条稳定性检测功能，用于适配高难度钓鱼场景（绿条移动/消失）。
"""

import cv2
import math
import numpy as np
from typing import Optional, Tuple
from collections import deque


class TensionDetector:
    LOWER_GREEN = np.array([38, 110, 120])
    UPPER_GREEN = np.array([75, 255, 255])
    LOWER_YELLOW_POINTER = np.array([20, 100, 180])
    UPPER_YELLOW_POINTER = np.array([40, 255, 255])
    LOWER_WHITE_HIGHLIGHT = np.array([15, 0, 220])
    UPPER_WHITE_HIGHLIGHT = np.array([45, 80, 255])

    MIN_GAP_WIDTH = 1
    MAX_GAP_WIDTH = 8
    GAP_THRESHOLD = 2

    def __init__(self, debug_windows: bool = True):
        """
        @brief      构造函数
        @param      debug_windows: 是否显示调试窗口
        @details    初始化图像处理核和绿条稳定性跟踪缓冲区。
        """
        self.debug = debug_windows
        self.last_result: Optional[np.ndarray] = None
        self._kernel_open = np.ones((2, 2), np.uint8)
        self._kernel_close = np.ones((3, 3), np.uint8)

        self._stability_buffer: deque = deque(maxlen=10)
        self._last_cover_rate: float = 0.0
        self._last_circle_center: Tuple[int, int] = (0, 0)
        self._last_angle_range: float = 0.0
        self._detection_mode_changes: int = 0
        self._prev_detection_mode: Optional[str] = None

    def get_tension_percentage(self, frame: np.ndarray) -> Optional[float]:
        if frame is None or frame.ndim != 3 or frame.shape[0] <= 0 or frame.shape[1] <= 0:
            return None

        h_img, w_img = frame.shape[:2]

        roi_x = max(0, int(w_img * 0.3))
        roi_y = max(0, int(h_img * 0.1))
        roi_w = max(1, int(w_img * 0.4))
        roi_h = max(1, int(h_img * 0.4))
        roi = frame[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w].copy()

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        green_mask = cv2.inRange(hsv, self.LOWER_GREEN, self.UPPER_GREEN)
        green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, self._kernel_open)
        green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, self._kernel_close)

        green_points = np.where(green_mask == 255)
        if len(green_points[0]) == 0:
            return None
        green_xy = np.column_stack((green_points[1], green_points[0]))

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 3)
        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, dp=1, minDist=roi_h//8,
            param1=60, param2=30,
            minRadius=max(1, int(min(roi_w, roi_h)*0.25)),
            maxRadius=max(2, int(min(roi_w, roi_h)*0.45))
        )

        if circles is None or circles.shape[1] == 0:
            return None
        circles = np.uint16(np.around(circles))

        circle_candidates = []
        for circle in circles[0, :]:
            cx, cy, r = circle
            distances = np.sqrt((green_xy[:,0] - cx)**2 + (green_xy[:,1] - cy)**2)
            in_circle = np.sum(np.abs(distances - r) < 15)
            cover_rate = in_circle / len(green_xy)
            circle_candidates.append((cover_rate, int(r), int(cx), int(cy)))

        max_cover = max(c[0] for c in circle_candidates)
        filtered = [c for c in circle_candidates if (max_cover - c[0]) <= 0.20]
        filtered.sort(key=lambda x: (-x[1], -x[0]))
        best_cover_rate, best_r, best_cx, best_cy = filtered[0]

        if best_cover_rate < 0.3:
            print(f"\u274c 未找到足够绿色的圆，最高覆盖率：{best_cover_rate*100:.1f}%")
            return None

        cx, cy, r = best_cx, best_cy, best_r
        if self.debug:
            roi_circles = roi.copy()
            for circle in circles[0, :]:
                cx_tmp, cy_tmp, r_tmp = circle
                cv2.circle(roi_circles, (cx_tmp, cy_tmp), r_tmp, (80,80,80), 1)
            cv2.circle(roi_circles, (cx, cy), r, (0,255,0), 2)
            cv2.circle(roi_circles, (cx, cy), 3, (0,0,255), -1)
            cv2.putText(roi_circles, f"Green Cover: {best_cover_rate*100:.1f}%", (10,30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
            cv2.imshow("Dial Circle", roi_circles)
            cv2.moveWindow("Dial Circle", 100, 100)

        green_angles = np.degrees(np.arctan2(
            green_xy[:, 1].astype(np.float64) - cy,
            green_xy[:, 0].astype(np.float64) - cx
        ))
        green_angles[green_angles < 0] += 360
        green_angles_sorted = np.sort(green_angles)

        if len(green_angles_sorted) < 10:
            return None

        gaps = []
        for i in range(len(green_angles_sorted) - 1):
            diff = green_angles_sorted[i+1] - green_angles_sorted[i]
            if diff > self.GAP_THRESHOLD:
                gaps.append((green_angles_sorted[i], green_angles_sorted[i+1], diff))

        wrap_diff = (green_angles_sorted[0] + 360) - green_angles_sorted[-1]
        if wrap_diff > self.GAP_THRESHOLD and wrap_diff < 180:
            gaps.append((green_angles_sorted[-1], green_angles_sorted[0] + 360, wrap_diff))

        valid_gaps = []
        for gap_start, gap_end, gap_width in gaps:
            if self.MIN_GAP_WIDTH <= gap_width <= self.MAX_GAP_WIDTH:
                valid_gaps.append((gap_start, gap_end, gap_width))

        valid_gap = None
        if valid_gaps:
            valid_gap = max(valid_gaps, key=lambda x: x[2])

        use_gap_mode = False
        pointer_angle = 0.0
        if valid_gap is not None:
            use_gap_mode = True
            gap_start, gap_end, _ = valid_gap
            gap_mid = (gap_start + gap_end) / 2.0
            pointer_angle = gap_mid if gap_mid < 360 else gap_mid - 360

        px, py = 0, 0
        ring_min_r = ring_max_r = 0
        if not use_gap_mode:
            valid_green_distances = np.sqrt((green_xy[:,0]-cx)**2 + (green_xy[:,1]-cy)**2)
            ring_min_r = np.min(valid_green_distances) - 3
            ring_max_r = np.max(valid_green_distances) + 3

            ring_mask = np.zeros_like(green_mask)
            cv2.circle(ring_mask, (cx, cy), int(ring_max_r), 255, -1)
            cv2.circle(ring_mask, (cx, cy), int(ring_min_r), 0, -1)

            mask_yellow = cv2.inRange(hsv, self.LOWER_YELLOW_POINTER, self.UPPER_YELLOW_POINTER)
            mask_highlight = cv2.inRange(hsv, self.LOWER_WHITE_HIGHLIGHT, self.UPPER_WHITE_HIGHLIGHT)
            pointer_mask_raw = cv2.bitwise_or(mask_yellow, mask_highlight)
            pointer_mask_raw = cv2.morphologyEx(pointer_mask_raw, cv2.MORPH_OPEN, self._kernel_open)
            pointer_mask_raw = cv2.morphologyEx(pointer_mask_raw, cv2.MORPH_CLOSE, self._kernel_close)

            pointer_mask = cv2.bitwise_and(pointer_mask_raw, pointer_mask_raw, mask=ring_mask)

            pointer_points = np.where(pointer_mask == 255)
            if len(pointer_points[0]) == 0:
                return None

            contours, _ = cv2.findContours(pointer_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return None
            max_contour = max(contours, key=lambda x: cv2.arcLength(x, False))
            contour_pts = max_contour[:, 0, :]
            distances = np.sqrt((contour_pts[:,0]-cx)**2 + (contour_pts[:,1]-cy)**2)
            tip_idx = np.argmax(distances)
            px, py = contour_pts[tip_idx]

            pointer_angle = math.degrees(math.atan2(py - cy, px - cx))
            pointer_angle = pointer_angle + 360 if pointer_angle < 0 else pointer_angle

        start_angle = min(green_angles)
        end_angle = max(green_angles)
        if end_angle - start_angle > 180:
            angles_less_180 = [a for a in green_angles if a < 180]
            angles_more_180 = [a for a in green_angles if a >= 180]
            if angles_less_180 and angles_more_180:
                start_angle = min(angles_more_180)
                end_angle = max(angles_less_180) + 360

        if start_angle > end_angle:
            start_angle, end_angle = end_angle, start_angle

        angle_range = end_angle - start_angle
        if angle_range <= 10:
            return None

        if end_angle > 360 and pointer_angle < 180:
            pointer_angle += 360
        elif start_angle > 360 and pointer_angle < 180:
            pointer_angle += 360

        percentage = (pointer_angle - start_angle) / angle_range * 100.0

        if self.debug:
            result = roi.copy()
            cv2.ellipse(result, (cx, cy), (r, r), 0,
                        start_angle if start_angle <= 360 else start_angle-360,
                        end_angle if end_angle <= 360 else end_angle-360,
                        (0,255,0), 3)
            if use_gap_mode:
                tip_rad = math.radians(pointer_angle)
                tip_x = int(cx + r * math.cos(tip_rad))
                tip_y = int(cy + r * math.sin(tip_rad))
                cv2.line(result, (cx, cy), (tip_x, tip_y), (0,0,255), 2)
                cv2.circle(result, (tip_x, tip_y), 5, (0,0,255), -1)
                cv2.putText(result, "Mode: Gap Detect", (10,60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,0,0), 2)
            else:
                cv2.circle(result, (cx, cy), int(ring_max_r), (255,165,0), 1)
                cv2.circle(result, (cx, cy), int(ring_min_r), (255,165,0), 1)
                cv2.line(result, (cx, cy), (int(px), int(py)), (0,0,255), 2)
                cv2.circle(result, (int(px), int(py)), 5, (0,0,255), -1)
                cv2.putText(result, "Mode: Ring Pointer Detect", (10,60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,165,255), 2)
            cv2.putText(result, f"{percentage:.2f}%", (10,30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
            cv2.imshow("Result", result)
            cv2.moveWindow("Result", 400, 100)
            self.last_result = result

        self._update_stability_metrics(best_cover_rate, (best_cx, best_cy), angle_range,
                                       'gap' if use_gap_mode else 'ring')

        return round(percentage, 2)

    def _update_stability_metrics(self,
                                   cover_rate: float,
                                   circle_center: Tuple[int, int],
                                   angle_range: float,
                                   detection_mode: str) -> None:
        """
        @brief      更新稳定性指标
        @param      cover_rate: 当前帧的绿色覆盖率
        @param      circle_center: 检测到的圆心坐标
        @param      angle_range: 绿色圆弧的角度范围
        @param      detection_mode: 检测模式 ('gap' | 'ring')
        @details    计算多项稳定性指标并存储到缓冲区，供get_green_stability()使用。
        """
        if self._prev_detection_mode is not None and self._prev_detection_mode != detection_mode:
            self._detection_mode_changes += 1
        self._prev_detection_mode = detection_mode

        cover_change = abs(cover_rate - self._last_cover_rate) if self._last_cover_rate > 0 else 0
        self._last_cover_rate = cover_rate

        center_shift = math.sqrt((circle_center[0] - self._last_circle_center[0])**2 +
                                 (circle_center[1] - self._last_circle_center[1])**2)
        self._last_circle_center = circle_center

        range_change = abs(angle_range - self._last_angle_range) if self._last_angle_range > 0 else 0
        self._last_angle_range = angle_range

        stability_score = 1.0
        stability_score -= min(cover_change * 2, 0.3)
        stability_score -= min(center_shift / 50.0, 0.2)
        stability_score -= min(range_change / 100.0, 0.2)
        stability_score -= min(self._detection_mode_changes * 0.1, 0.3)

        stability_score = max(0.1, min(1.0, stability_score))

        self._stability_buffer.append(stability_score)

        if len(self._stability_buffer) > 15:
            self._detection_mode_changes = max(0, self._detection_mode_changes - 1)

    def get_green_stability(self) -> float:
        """
        @brief      获取绿条稳定性评分
        @return     稳定性评分 (0.0-1.0)，其中：
                    1.0 = 完全稳定（绿条位置、大小、形状均不变）
                    0.5 = 中等波动（钓普通鱼时的正常情况）
                    0.1 = 极不稳定（高难度鱼，绿条快速移动/消失）
        @details    基于最近10帧的检测数据综合评估：
                    - 绿色覆盖率变化量
                    - 圆心位置偏移量
                    - 角度范围变化量
                    - 检测模式切换频率
                当钓高难度鱼时（绿条移动/消失），此值会显著降低，
                预测控制器会据此降低预测置信度，采用更保守的控制策略。
        """
        if len(self._stability_buffer) == 0:
            return 1.0

        recent_scores = list(self._stability_buffer)[-5:]
        avg_stability = sum(recent_scores) / len(recent_scores)

        if len(recent_scores) >= 3:
            variance = sum((s - avg_stability)**2 for s in recent_scores) / len(recent_scores)
            stability_penalty = min(variance * 2, 0.2)
            avg_stability = max(0.1, avg_stability - stability_penalty)

        return avg_stability
