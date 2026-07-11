# -*- coding: utf-8 -*-
"""
@file       main.py
@brief      基于自适应 Smith 预估器的张力自动控制程序
@details    使用 Smith 预估器补偿系统延迟，通过在线辨识动态调整模型参数，
            实现精确的张力控制在 50% 目标值。
"""

import cv2
import time
from typing import Optional
import numpy as np
import threading

from window_capture import WindowCapture
from tension_detector import TensionDetector
from mouse_controller import MouseController
from visualizer import Visualizer
from smith_predictor import AdaptiveSmithPredictor
from logger import init_logger, get_logger


class MainController:
    def __init__(self,
                 window_title: str = "ELZ-AN00",
                 target_tension: float = 50.0):
        self.window_capture = WindowCapture(window_title)
        self.tension_detector = TensionDetector(debug_windows=True)
        self.mouse_controller = MouseController()
        self.visualizer = Visualizer()

        self.smith_predictor = AdaptiveSmithPredictor(
            target_tension=target_tension,
            min_delay_ms=40.0,
            max_delay_ms=300.0,
            sample_window_size=150,
            identification_interval=10,
            forgetting_factor=0.98
        )

        self.target_tension = target_tension
        self.is_button_pressed = False
        self._last_control_cmd: float = 0.5

        self._in_null_state = False
        self._skip_fail_count = 0
        self._drop_count = 0
        self._null_start_time: float = 0.0
        self._null_cooldown_until: float = 0.0

        self._last_action_time: float = 0.0
        self._frame_count: int = 0
        
        # 控制面板设置
        self.auto_fish_enabled = True
        self.auto_renewal_enabled = True
        self.control_mode = "smith"  # "smith" 或 "simple"
        
        # 运行状态
        self._running = True
        
        # 锁，用于线程安全
        self._lock = threading.Lock()
    
    def set_auto_fish(self, enabled: bool):
        """
        @brief      设置自动钓鱼开关
        @param      enabled: 是否启用
        """
        with self._lock:
            self.auto_fish_enabled = enabled
        logger = get_logger()
        logger.info(f"自动钓鱼: {'开启' if enabled else '关闭'}")
    
    def set_auto_renewal(self, enabled: bool):
        """
        @brief      设置自动续鱼开关
        @param      enabled: 是否启用
        """
        with self._lock:
            self.auto_renewal_enabled = enabled
        logger = get_logger()
        logger.info(f"自动续鱼: {'开启' if enabled else '关闭'}")
    
    def set_control_mode(self, mode: str):
        """
        @brief      设置控制模式
        @param      mode: "smith" 或 "simple"
        """
        with self._lock:
            self.control_mode = mode
        logger = get_logger()
        mode_name = "Smith预估器" if mode == "smith" else "简单模式"
        logger.info(f"控制模式切换为: {mode_name}")
        if mode == "simple":
            self.smith_predictor.reset_state()

    def run(self) -> None:
        logger = get_logger()

        if not self.window_capture.find_window():
            logger.error("未找到目标窗口，程序退出")
            return

        cv2.namedWindow("Real-Time Capture", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Real-Time Capture", 1000, 600)
        
        logger.info(f"自适应 Smith 预估器已启用 | 目标张力: {self.target_tension}%")

        try:
            while self._running:
                frame = self.window_capture.capture()
                if frame is None:
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                    continue

                self._frame_count += 1
                current_time = time.time()

                tension = self.tension_detector.get_tension_percentage(frame)

                self.smith_predictor.add_sample(tension, current_time, self._last_control_cmd)

                button_ratio = self.visualizer.get_button_ratio(frame)

                if button_ratio:
                    ratio_x, ratio_y = button_ratio
                    self._process_control_logic(tension, ratio_x, ratio_y, current_time)

                display_frame = self.visualizer.draw_enhanced_info(
                    frame, tension, self.is_button_pressed, button_ratio,
                    None
                )

                if display_frame is not None:
                    display_frame = self._draw_smith_info(display_frame)

                if display_frame is not None:
                    cv2.imshow("Real-Time Capture", display_frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or cv2.getWindowProperty("Real-Time Capture", cv2.WND_PROP_VISIBLE) < 1:
                    break

        except Exception as e:
            logger.error(f"主循环异常: {str(e)}")
        finally:
            self._cleanup()
    
    def stop(self):
        """
        @brief      停止运行
        """
        self._running = False

    def _draw_smith_info(self, frame: np.ndarray) -> np.ndarray:
        """
        @brief      在画面上绘制 Smith 预估器调试信息
        @param      frame: 原始画面
        @return     绘制信息后的画面
        """
        if frame is None:
            return None

        info = self.smith_predictor.get_debug_info()

        y_pos = 30
        line_height = 25

        cv2.putText(frame, f"Smith Predictor", (10, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 200, 100), 2)
        y_pos += line_height

        comp_t = info.get('compensated_tension', 0.0) or 0.0
        actual_t = info.get('actual_tension', 0.0) or 0.0
        delay_ms = info.get('estimated_delay_ms', 0.0) or 0.0
        cv2.putText(frame, f"Comp: {comp_t:.1f}%  Actual: {actual_t:.1f}%", (10, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 255, 200), 1)
        y_pos += line_height
        
        model_a = info.get('model_a', 0.9) or 0.9
        model_b = info.get('model_b', 1.0) or 1.0
        cv2.putText(frame, f"Delay: {delay_ms:.0f}ms  Model: a={model_a:.3f} b={model_b:.2f}", (10, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 255), 1)
        y_pos += line_height
        
        kp = info.get('Kp', 0.08) or 0.08
        ki = info.get('Ki', 0.02) or 0.02
        integral = info.get('integral', 0.0) or 0.0
        cv2.putText(frame, f"PI: Kp={kp:.3f} Ki={ki:.3f} Int={integral:.2f}", (10, y_pos),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 200), 1)

        return frame

    def _process_control_logic(self,
                               tension: Optional[float],
                               ratio_x: float,
                               ratio_y: float,
                               current_time: float) -> None:
        logger = get_logger()

        if tension is None:
            self._in_null_state = True
            self._handle_null_state(ratio_x, ratio_y, current_time)
        else:
            if self._in_null_state:
                logger.info("张力检测恢复")
            self._in_null_state = False
            self._handle_valid_tension(tension, ratio_x, ratio_y, current_time)

    def _handle_null_state(self,
                           ratio_x: float,
                           ratio_y: float,
                           current_time: float) -> None:
        logger = get_logger()

        with self._lock:
            auto_renewal = self.auto_renewal_enabled

        if not auto_renewal:
            return

        if self._skip_fail_count < 2:
            self._skip_fail_count += 1
        else:
            if self.is_button_pressed:
                self._execute_action(ratio_x, ratio_y, press=False, action_type='release', current_time=current_time)
                self.is_button_pressed = False

            now = current_time
            if now >= self._null_cooldown_until:
                if self._null_start_time == 0.0:
                    self._null_start_time = now
                elif now - self._null_start_time >= 1.0:
                    self._execute_action(ratio_x, ratio_y, press=True, action_type='null_recovery', current_time=now)
                    self._execute_action(ratio_x, ratio_y, press=False, action_type='null_recovery', current_time=now)
                    self._null_start_time = 0.0
                    self._null_cooldown_until = now + 2.0
                    self.smith_predictor.reset_state()
                    logger.warning("NULL持续1秒，已点击按钮尝试恢复，重置Smith状态，冷却2秒")

    def _handle_valid_tension(self,
                              tension: float,
                              ratio_x: float,
                              ratio_y: float,
                              current_time: float) -> None:
        logger = get_logger()

        self._skip_fail_count = 0
        self._null_start_time = 0.0

        with self._lock:
            auto_fish = self.auto_fish_enabled
            mode = self.control_mode

        if not auto_fish:
            return

        if mode == "simple":
            # 简单模式：低于50%按下，高于50%释放
            should_press = tension < self.target_tension
            
            if not self.is_button_pressed and should_press:
                self._execute_action(ratio_x, ratio_y, press=True, action_type='simple_press', current_time=current_time)
                self.is_button_pressed = True
            elif self.is_button_pressed and not should_press:
                self._execute_action(ratio_x, ratio_y, press=False, action_type='simple_release', current_time=current_time)
                self.is_button_pressed = False
                
            if self._frame_count % 15 == 0:
                logger.info(
                    f"Actual:{tension:.1f}% "
                    f"Mode:simple "
                    f"Dec:{'press' if should_press else 'release'}"
                )
        else:
            # Smith模式
            should_press, decision_info = self.smith_predictor.get_control_decision(self.is_button_pressed)

            self._last_control_cmd = decision_info.get('control_output', 0.5) or 0.5

            if self._frame_count % 15 == 0:
                actual = decision_info.get('actual_tension', 0.0) or 0.0
                comp = decision_info.get('compensated_tension', 0.0) or 0.0
                err = decision_info.get('error', 0.0) or 0.0
                u = decision_info.get('control_output', 0.0) or 0.0
                delay = decision_info.get('estimated_delay_ms', 0.0) or 0.0
                action = decision_info.get('action', 'hold') or 'hold'
                logger.info(
                    f"Actual:{actual:.1f}% "
                    f"Comp:{comp:.1f}% "
                    f"Err:{err:+.1f}% "
                    f"U:{u:.2f} "
                    f"Delay:{delay:.0f}ms "
                    f"Dec:{action}"
                )

            if not self.is_button_pressed and should_press:
                action = decision_info.get('action', 'press') or 'press'
                self._execute_action(ratio_x, ratio_y, press=True, action_type=action, current_time=current_time)
                self.is_button_pressed = True
            elif self.is_button_pressed and not should_press:
                action = decision_info.get('action', 'release') or 'release'
                self._execute_action(ratio_x, ratio_y, press=False, action_type=action, current_time=current_time)
                self.is_button_pressed = False

    def _execute_action(self,
                        ratio_x: float,
                        ratio_y: float,
                        press: bool,
                        action_type: str,
                        current_time: float) -> None:
        self._perform_mouse_action(ratio_x, ratio_y, press)
        self._last_action_time = current_time

    def _perform_mouse_action(self, ratio_x: float, ratio_y: float, press: bool) -> None:
        logger = get_logger()

        game_height = self.window_capture.client_height - self.window_capture.crop_top
        game_x = int(self.window_capture.client_width * ratio_x)
        game_y = int(game_height * ratio_y)
        client_x = game_x
        client_y = game_y + self.window_capture.crop_top

        if not (0 <= client_x <= self.window_capture.client_width and 0 <= client_y <= self.window_capture.client_height):
            logger.warning(f"坐标超出窗口范围: ({client_x},{client_y})")
            return

        screen_pos = self.window_capture.client_to_screen(client_x, client_y)
        if screen_pos is None:
            return
        abs_x, abs_y = self.window_capture.convert_absolute_mouse_coords(screen_pos[0], screen_pos[1])

        success = self.mouse_controller.click_at_abs(abs_x, abs_y, press)
        action = "按下" if press else "松开"
        if success:
            logger.debug(f"按钮{action} | ({ratio_x:.2f},{ratio_y:.2f}) -> ({client_x},{client_y})")
        else:
            logger.error(f"按钮{action}失败")

    def _cleanup(self) -> None:
        logger = get_logger()

        if self.is_button_pressed:
            button_ratio = self.visualizer.get_button_ratio(None)
            self._perform_mouse_action(button_ratio[0], button_ratio[1], press=False)
            logger.info("程序退出，已强制松开按钮")
        cv2.destroyAllWindows()


def main() -> None:
    log_file = "fishing_smith.log"
    init_logger(log_file=log_file)
    logger = get_logger()
    logger.info("程序启动 - 自适应 Smith 预估器版本")

    controller = MainController(
        window_title="ELZ-AN00",
        target_tension=50.0
    )
    
    # 在子线程中运行主控制器
    import threading
    main_thread = threading.Thread(target=controller.run, daemon=True)
    main_thread.start()
    
    # 导入并启动控制面板（必须在主线程）
    from control_panel import ControlPanel
    
    def on_settings_change(settings):
        if 'auto_fish' in settings:
            controller.set_auto_fish(settings['auto_fish'])
        if 'auto_renewal' in settings:
            controller.set_auto_renewal(settings['auto_renewal'])
        if 'mode' in settings:
            controller.set_control_mode(settings['mode'])
    
    panel = ControlPanel(on_settings_change)
    logger.info("控制面板已启动")
    
    # 运行控制面板（阻塞主线程）
    panel.root.protocol("WM_DELETE_WINDOW", lambda: (controller.stop(), panel.root.destroy()))
    panel.root.mainloop()
    
    logger.info("程序结束")


if __name__ == "__main__":
    main()