# -*- coding: utf-8 -*-
"""
@file       smith_predictor.py
@brief      自适应 Smith 预估器控制模块
@details    实现基于 Smith 预估器的张力控制，用于补偿系统延迟，
            包括在线参数辨识、异常处理、PI 控制器和 PWM 调制。
"""

import time
import numpy as np
from collections import deque
from typing import Optional, Tuple, List, Deque


class AdaptiveSmithPredictor:
    """
    @brief      自适应 Smith 预估器类
    @details    实现完整的 Smith 预估控制方案，包括：
                - 异常检测与预处理
                - 延迟与模型参数在线辨识
                - Smith 预估补偿
                - PI 控制器
                - PWM 调制输出
    """

    def __init__(self,
                 target_tension: float = 50.0,
                 min_delay_ms: float = 40.0,
                 max_delay_ms: float = 300.0,
                 sample_window_size: int = 150,
                 identification_interval: int = 10,
                 forgetting_factor: float = 0.98):
        """
        @brief      构造函数
        @param      target_tension: 目标张力值（默认50%）
        @param      min_delay_ms: 最小延迟估计（毫秒）
        @param      max_delay_ms: 最大延迟估计（毫秒）
        @param      sample_window_size: 辨识用滑动窗口大小
        @param      identification_interval: 辨识执行间隔（帧数）
        @param      forgetting_factor: RLS 遗忘因子 (0.95-0.99)
        """
        self.target_tension = target_tension
        self.min_delay_ms = min_delay_ms
        self.max_delay_ms = max_delay_ms
        self.sample_window_size = sample_window_size
        self.identification_interval = identification_interval
        self.forgetting_factor = forgetting_factor

        self._init_buffers()
        self._init_models()
        self._init_controller()
        self._init_state()

    def _init_buffers(self) -> None:
        """
        @brief      初始化数据缓冲区
        """
        self._tension_raw_buffer: Deque[Optional[float]] = deque(maxlen=self.sample_window_size)
        self._tension_valid_buffer: Deque[float] = deque(maxlen=self.sample_window_size)
        self._control_cmd_buffer: Deque[float] = deque(maxlen=self.sample_window_size)
        self._timestamp_buffer: Deque[float] = deque(maxlen=self.sample_window_size)
        self._is_valid_buffer: Deque[bool] = deque(maxlen=self.sample_window_size)

    def _init_models(self) -> None:
        """
        @brief      初始化模型参数
        """
        self._estimated_delay_steps: int = 3
        self._model_a: float = 0.9
        self._model_b: float = 1.0
        self._P_cov: np.ndarray = np.eye(2) * 100.0
        self._y_m: float = 50.0
        self._y_md: float = 50.0
        self._y_m_history: Deque[float] = deque(maxlen=self.sample_window_size)
        self._y_md_history: Deque[float] = deque(maxlen=self.sample_window_size)

    def _init_controller(self) -> None:
        """
        @brief      初始化 PI 控制器
        """
        self._Kp: float = 0.08
        self._Ki: float = 0.02
        self._integral: float = 0.0
        self._integral_max: float = 2.0
        self._integral_min: float = -2.0

    def _init_state(self) -> None:
        """
        @brief      初始化状态变量
        """
        self._frame_count: int = 0
        self._last_valid_tension: Optional[float] = None
        self._consecutive_null_count: int = 0
        self._is_in_open_loop: bool = False
        self._null_start_time: float = 0.0
        self._avg_sample_period: float = 0.05

    def add_sample(self, tension: Optional[float], timestamp: Optional[float] = None, control_cmd: Optional[float] = None) -> None:
        """
        @brief      添加新的样本到缓冲区
        @param      tension: 当前张力值（None表示无效/NULL）
        @param      timestamp: 时间戳（默认为当前时间）
        @param      control_cmd: 上一次的控制命令（0-1，None表示保持）
        """
        if timestamp is None:
            timestamp = time.time()
        if control_cmd is None:
            control_cmd = self._control_cmd_buffer[-1] if len(self._control_cmd_buffer) > 0 else 0.5

        self._tension_raw_buffer.append(tension)
        self._timestamp_buffer.append(timestamp)
        self._control_cmd_buffer.append(control_cmd)

        valid_tension = self._preprocess_tension(tension)
        self._tension_valid_buffer.append(valid_tension)
        self._is_valid_buffer.append(tension is not None)

        if len(self._timestamp_buffer) >= 2:
            dt_list = []
            ts_list = list(self._timestamp_buffer)
            for i in range(1, min(len(ts_list), 20)):
                dt = ts_list[-1] - ts_list[-i-1]
                if dt > 0:
                    dt_list.append(dt / i)
            if len(dt_list) > 0:
                self._avg_sample_period = np.mean(dt_list)

        self._frame_count += 1

        if self._frame_count % self.identification_interval == 0 and len(self._tension_valid_buffer) >= 50:
            self._identify_parameters()

        self._update_smith_predictor()

    def _preprocess_tension(self, tension: Optional[float]) -> float:
        """
        @brief      预处理张力值，检测并修复异常
        @param      tension: 原始张力值
        @return     修复后的有效张力值
        """
        if tension is None:
            self._consecutive_null_count += 1
            if self._last_valid_tension is None:
                return 50.0
            return self._last_valid_tension

        self._consecutive_null_count = 0

        if tension < -20 or tension > 120:
            if self._last_valid_tension is None:
                return 50.0
            return self._last_valid_tension

        if self._last_valid_tension is not None:
            diff = abs(tension - self._last_valid_tension)
            if diff > 35:
                return self._last_valid_tension

        self._last_valid_tension = tension
        return max(0.0, min(100.0, tension))

    def _identify_parameters(self) -> None:
        """
        @brief      在线辨识延迟和模型参数
        @details    先通过残差扫描估计延迟，再用 RLS 更新模型参数
        """
        if len(self._tension_valid_buffer) < 60 or len(self._control_cmd_buffer) < 60:
            return

        best_delay = self._estimated_delay_steps
        best_residual = float('inf')

        min_delay_steps = max(1, int(self.min_delay_ms / (self._avg_sample_period * 1000)))
        max_delay_steps = min(20, int(self.max_delay_ms / (self._avg_sample_period * 1000)))

        y_arr = np.array(list(self._tension_valid_buffer))
        u_arr = np.array(list(self._control_cmd_buffer))

        for d_candidate in range(min_delay_steps, max_delay_steps + 1):
            a_est, b_est, residual = self._rls_estimate(y_arr, u_arr, d_candidate)
            if residual < best_residual:
                best_residual = residual
                best_delay = d_candidate

        if abs(best_delay - self._estimated_delay_steps) > 2:
            self._P_cov = np.eye(2) * 100.0

        self._estimated_delay_steps = best_delay

        self._model_a, self._model_b, _ = self._rls_estimate(y_arr, u_arr, self._estimated_delay_steps)

        self._update_controller_gains()

    def _rls_estimate(self, y: np.ndarray, u: np.ndarray, delay_steps: int) -> Tuple[float, float, float]:
        """
        @brief      递归最小二乘参数估计
        @param      y: 输出序列
        @param      u: 输入序列
        @param      delay_steps: 延迟步数
        @return     (a, b, residual)
        """
        n = len(y)
        if n < delay_steps + 5:
            return 0.9, 1.0, float('inf')

        P = np.eye(2) * 100.0
        theta = np.array([self._model_a, self._model_b])
        lambda_ = self.forgetting_factor
        residual_sum = 0.0

        for k in range(delay_steps + 1, n):
            phi_k = np.array([y[k-1], u[k-1-delay_steps]])
            y_k = y[k]
            y_hat = phi_k @ theta
            e_k = y_k - y_hat
            residual_sum += e_k ** 2

            K = P @ phi_k / (lambda_ + phi_k.T @ P @ phi_k)
            theta = theta + K * e_k
            P = (P - np.outer(K, phi_k.T) @ P) / lambda_

        a = np.clip(theta[0], 0.5, 0.999)
        b = np.clip(theta[1], 0.1, 5.0)

        return a, b, residual_sum / (n - delay_steps - 1)

    def _update_controller_gains(self) -> None:
        """
        @brief      根据模型参数更新 PI 控制器增益
        """
        T_est = -self._avg_sample_period / np.log(self._model_a) if self._model_a < 0.999 else 0.5
        K_est = self._model_b / (1.0 - self._model_a) if self._model_b > 0.01 else 1.0

        self._Kp = np.clip(0.6 / max(K_est, 0.1) * T_est / max(self._avg_sample_period, 0.01), 0.02, 0.2)
        self._Ki = np.clip(self._Kp / max(T_est, 0.1), 0.005, 0.08)

    def _update_smith_predictor(self) -> None:
        """
        @brief      更新 Smith 预估器状态
        """
        if len(self._control_cmd_buffer) < 2:
            return

        u_prev = self._control_cmd_buffer[-2]

        self._y_m = self._model_a * self._y_m + self._model_b * u_prev
        self._y_m = max(0.0, min(100.0, self._y_m))

        d = self._estimated_delay_steps
        if len(self._control_cmd_buffer) > d + 1:
            u_delay = self._control_cmd_buffer[-2 - d]
            self._y_md = self._model_a * self._y_md + self._model_b * u_delay
        else:
            self._y_md = self._y_m

        self._y_md = max(0.0, min(100.0, self._y_md))

        self._y_m_history.append(self._y_m)
        self._y_md_history.append(self._y_md)

    def get_compensated_tension(self) -> float:
        """
        @brief      获取 Smith 补偿后的张力值
        @return     补偿后的张力值（无延迟估计）
        """
        if len(self._tension_valid_buffer) == 0:
            return 50.0

        y_valid = self._tension_valid_buffer[-1]
        y_comp = self._y_m + (y_valid - self._y_md)
        return max(0.0, min(100.0, y_comp))

    def get_control_decision(self, is_button_pressed: bool) -> Tuple[bool, dict]:
        """
        @brief      获取控制决策
        @param      is_button_pressed: 当前按钮状态
        @return     (是否应该按下, 决策详情字典)
        """
        y_comp = self.get_compensated_tension()
        y_valid = self._tension_valid_buffer[-1] if len(self._tension_valid_buffer) > 0 else 50.0

        error = self.target_tension - y_comp
        self._integral = np.clip(self._integral + error * self._avg_sample_period,
                                 self._integral_min, self._integral_max)
        u_cont = self._Kp * error + self._Ki * self._integral
        u_cont = np.clip(u_cont, 0.0, 1.0)

        if self._consecutive_null_count >= 5:
            should_press = False
            action = 'hold'
            reason = f'open_loop: null_count={self._consecutive_null_count}'
        else:
            should_press, action, reason = self._pwm_modulate(u_cont, is_button_pressed, y_valid)

        decision_info = {
            'action': action or 'hold',
            'compensated_tension': y_comp,
            'actual_tension': y_valid,
            'control_output': u_cont,
            'error': error,
            'integral': self._integral,
            'Kp': self._Kp,
            'Ki': self._Ki,
            'estimated_delay_ms': self._estimated_delay_steps * self._avg_sample_period * 1000,
            'model_a': self._model_a,
            'model_b': self._model_b,
            'reason': reason or ''
        }

        return should_press, decision_info

    def _pwm_modulate(self, u_cont: float, current_state: bool, actual_tension: float) -> Tuple[bool, str, str]:
        """
        @brief      PWM 调制，将连续控制量转换为开关决策
        @param      u_cont: 连续控制输出 (0-1)
        @param      current_state: 当前按钮状态
        @param      actual_tension: 当前实际张力
        @return     (should_press, action, reason)
        """
        emergency_low = 35.0
        emergency_high = 65.0

        if not current_state and actual_tension < emergency_low:
            return True, 'press', f'emergency_low: {actual_tension:.1f}%'
        if current_state and actual_tension > emergency_high:
            return False, 'release', f'emergency_high: {actual_tension:.1f}%'

        threshold_on = 0.6
        threshold_off = 0.4

        if not current_state and u_cont > threshold_on:
            return True, 'press', f'PWM_on: {u_cont:.2f}'
        elif current_state and u_cont < threshold_off:
            return False, 'release', f'PWM_off: {u_cont:.2f}'
        else:
            return current_state, 'hold', f'PWM_hold: {u_cont:.2f}'

    def reset_state(self) -> None:
        """
        @brief      重置控制器状态（NULL持续1秒后调用）
        """
        self._init_buffers()
        self._init_models()
        self._init_controller()
        self._consecutive_null_count = 0
        self._last_valid_tension = None
        self._is_in_open_loop = False
        self._null_start_time = 0.0

    def get_debug_info(self) -> dict:
        """
        @brief      获取调试信息
        @return     调试信息字典
        """
        return {
            'compensated_tension': self.get_compensated_tension(),
            'actual_tension': self._tension_valid_buffer[-1] if len(self._tension_valid_buffer) > 0 else 50.0,
            'estimated_delay_ms': self._estimated_delay_steps * self._avg_sample_period * 1000,
            'model_a': self._model_a,
            'model_b': self._model_b,
            'Kp': self._Kp,
            'Ki': self._Ki,
            'integral': self._integral,
            'buffer_size': len(self._tension_valid_buffer),
            'consecutive_null': self._consecutive_null_count
        }
