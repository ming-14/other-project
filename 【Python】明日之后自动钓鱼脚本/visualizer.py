# -*- coding: utf-8 -*-
"""
@file       visualizer.py
@brief      实时画面绘制辅助模块（增强版）
@details    在主循环中负责在捕获的画面上叠加张力、按钮状态、预测信息等。
            支持显示预测控制器的详细调试信息，便于实时监控系统状态。
"""

import cv2
import numpy as np
from typing import Tuple, Optional


class Visualizer:
    """
    @brief      可视化辅助类
    @details    提供静态方法用于在画面上绘制各种状态信息和调试数据。
    """

    @staticmethod
    def draw_info(frame: np.ndarray,
                  tension: Optional[float],
                  is_pressed: bool,
                  button_ratio: Tuple[float, float]) -> np.ndarray:
        """
        @brief      基础信息绘制（兼容旧接口）
        @param      frame: 输入图像帧
        @param      tension: 当前张力值
        @param      is_pressed: 按钮是否按下
        @param      button_ratio: 按钮位置比例
        @return     绘制后的图像帧
        """
        if frame is None:
            return frame

        tension_text = "NULL" if tension is None else f"{tension}%"
        cv2.putText(frame, f"Tension: {tension_text}", (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        status_text = "Button: PRESSED" if is_pressed else "Button: RELEASED"
        status_color = (0, 0, 255) if is_pressed else (0, 255, 0)
        cv2.putText(frame, status_text, (30, 120),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, status_color, 2)

        if button_ratio:
            h, w = frame.shape[:2]
            btn_x = int(w * button_ratio[0])
            btn_y = int(h * button_ratio[1])
            cv2.putText(frame, f"Button Ratio: {button_ratio}", (30, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.circle(frame, (btn_x, btn_y), 8, (0, 0, 255), -1)

        return frame

    @staticmethod
    def draw_enhanced_info(frame: np.ndarray,
                           tension: Optional[float],
                           is_pressed: bool,
                           button_ratio: Tuple[float, float],
                           predictive_controller) -> np.ndarray:
        """
        @brief      增强信息绘制
        @param      frame: 输入图像帧
        @param      tension: 当前实测张力值
        @param      is_pressed: 按钮当前状态
        @param      button_ratio: 按钮位置比例
        @param      predictive_controller: 预测控制器实例（可以为None）
        @return     绘制后的图像帧
        """
        if frame is None:
            return frame

        h, w = frame.shape[:2]

        tension_text = "NULL" if tension is None else f"{tension:.1f}%"
        color_actual = (0, 0, 255) if tension is None else (0, 255, 0)
        cv2.putText(frame, f"Tension: {tension_text}", (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, color_actual, 2)

        status_text = "● PRESSED" if is_pressed else "○ RELEASED"
        status_color = (0, 0, 255) if is_pressed else (0, 255, 0)
        cv2.putText(frame, status_text, (30, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, status_color, 2)

        if button_ratio:
            btn_x = int(w * button_ratio[0])
            btn_y = int(h * button_ratio[1])
            cv2.circle(frame, (btn_x, btn_y), 10, (0, 0, 255), -1)
            cv2.circle(frame, (btn_x, btn_y), 12, (255, 255, 255), 1)

        return frame

    @staticmethod
    def _draw_tension_info(frame: np.ndarray,
                           tension: Optional[float],
                           predictive_controller) -> None:
        """
        @brief      绘制张力信息区域
        @details    显示实测张力和预测张力，使用不同颜色区分。
        """
        predicted, meta = predictive_controller.get_prediction()

        tension_text = "NULL" if tension is None else f"{tension:.1f}%"
        color_actual = (0, 0, 255) if tension is None else (0, 255, 0)
        cv2.putText(frame, f"Actual: {tension_text}", (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, color_actual, 2)

        if predicted is not None:
            pred_text = f"Predicted: {predicted:.1f}%"
            cv2.putText(frame, pred_text, (30, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)

            target = predictive_controller.target_tension
            cv2.putText(frame, f"Target: {target:.1f}%", (30, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 165, 255), 2)

    @staticmethod
    def _draw_button_status(frame: np.ndarray, is_pressed: bool) -> None:
        """
        @brief      绘制按钮状态
        """
        status_text = "● PRESSED" if is_pressed else "○ RELEASED"
        status_color = (0, 0, 255) if is_pressed else (0, 255, 0)
        cv2.putText(frame, status_text, (30, 160),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, status_color, 2)

    @staticmethod
    def _draw_prediction_details(frame: np.ndarray, predictive_controller) -> None:
        """
        @brief      绘制预测详细信息
        @details    包括趋势、速度、自适应偏移量等调试信息。
        """
        _, meta = predictive_controller.get_prediction()

        trend = meta.get('trend', 'stable')
        velocity = meta.get('current_velocity', 0.0)

        trend_symbols = {
            'rising': '▲ RISING',
            'falling': '▼ FALLING',
            'stable': '→ STABLE'
        }
        trend_text = trend_symbols.get(trend, '?')
        trend_colors = {
            'rising': (0, 0, 255),
            'falling': (255, 165, 0),
            'stable': (0, 255, 0)
        }
        trend_color = trend_colors.get(trend, (255, 255, 255))

        cv2.putText(frame, f"Trend: {trend_text}", (30, 200),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, trend_color, 2)

        velocity_text = f"Velocity: {velocity:+.1f}%/s"
        vel_color = (0, 0, 255) if velocity > 10 else (255, 165, 0) if velocity < -10 else (0, 255, 0)
        cv2.putText(frame, velocity_text, (30, 235),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, vel_color, 2)

        debug = predictive_controller.get_debug_info()
        adaptive_p = debug['adaptive_offset_press']
        adaptive_r = debug['adaptive_offset_release']

        cv2.putText(frame, f"Adaptive Offset: [{adaptive_p:+.1f}, {adaptive_r:+.1f}]", (30, 270),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        stability = debug['green_stability_score']
        stab_color = (0, 255, 0) if stability > 0.8 else (255, 165, 0) if stability > 0.5 else (0, 0, 255)
        cv2.putText(frame, f"Green Stability: {stability:.2f}", (30, 300),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, stab_color, 1)

    @staticmethod
    def _draw_confidence_bar(frame: np.ndarray,
                             predictive_controller,
                             frame_height: int) -> None:
        """
        @brief      绘制置信度进度条
        @details    在画面右上角显示预测置信度的可视化条形图。
        """
        _, meta = predictive_controller.get_prediction()
        confidence = meta.get('confidence', 0.0)

        bar_width = 200
        bar_height = 20
        bar_x = frame.shape[1] - bar_width - 20
        bar_y = 20

        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (100, 100, 100), -1)
        fill_width = int(bar_width * confidence)
        if fill_width > 0:
            bar_color = (0, 255, 0) if confidence > 0.7 else (255, 165, 0) if confidence > 0.4 else (0, 0, 255)
            cv2.rectangle(frame, (bar_x, bar_y), (bar_x + fill_width, bar_y + bar_height), bar_color, -1)

        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height), (255, 255, 255), 1)
        conf_text = f"Confidence: {confidence:.0%}"
        cv2.putText(frame, conf_text, (bar_x, bar_y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    @staticmethod
    def get_button_ratio(frame: np.ndarray) -> Tuple[float, float]:
        """
        @brief      获取操作按钮的相对坐标位置
        @param      frame: 图像帧（保留接口兼容性，当前返回固定值）
        @return     Tuple[X比例, Y比例]
        @note       当前实现返回固定坐标(0.90, 0.73)，对应窗口右下角按钮位置。
                    可扩展为自动检测按钮位置的算法。
        """
        return (0.90, 0.73)
