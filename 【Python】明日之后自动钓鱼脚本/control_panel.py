# -*- coding: utf-8 -*-
"""
@file       control_panel.py
@brief      钓鱼脚本控制面板
@details    提供GUI界面用于开关功能和切换控制模式
"""

import tkinter as tk
from tkinter import ttk


class ControlPanel:
    def __init__(self, on_settings_change):
        """
        @brief      初始化控制面板
        @param      on_settings_change: 设置变化时的回调函数
        """
        self.root = tk.Tk()
        self.root.title("钓鱼脚本控制面板")
        self.root.geometry("280x200")
        self.root.resizable(False, False)
        
        self.on_settings_change = on_settings_change
        
        self.auto_fish_enabled = tk.BooleanVar(value=True)
        self.auto_renewal_enabled = tk.BooleanVar(value=True)
        self.control_mode = tk.StringVar(value="smith")
        
        self._create_widgets()
    
    def _create_widgets(self):
        """
        @brief      创建UI组件
        """
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(main_frame, text="🎣 钓鱼控制面板", font=("Microsoft YaHei", 12, "bold"))
        title_label.pack(pady=(0, 15))

        auto_fish_check = ttk.Checkbutton(
            main_frame,
            text="自动钓鱼 (张力控制)",
            variable=self.auto_fish_enabled,
            command=self._on_auto_fish_toggle
        )
        auto_fish_check.pack(anchor=tk.W, pady=5)

        auto_renewal_check = ttk.Checkbutton(
            main_frame,
            text="自动续鱼 (NULL恢复)",
            variable=self.auto_renewal_enabled,
            command=self._on_auto_renewal_toggle
        )
        auto_renewal_check.pack(anchor=tk.W, pady=5)

        mode_frame = ttk.LabelFrame(main_frame, text="控制模式", padding="5")
        mode_frame.pack(fill=tk.X, pady=10)

        smith_radio = ttk.Radiobutton(
            mode_frame,
            text="Smith预估器",
            value="smith",
            variable=self.control_mode,
            command=self._on_mode_change
        )
        smith_radio.pack(anchor=tk.W)

        simple_radio = ttk.Radiobutton(
            mode_frame,
            text="简单模式 (<50按/>50放)",
            value="simple",
            variable=self.control_mode,
            command=self._on_mode_change
        )
        simple_radio.pack(anchor=tk.W)
    
    def _on_auto_fish_toggle(self):
        """
        @brief      自动钓鱼开关回调
        """
        self.on_settings_change({
            'auto_fish': self.auto_fish_enabled.get()
        })
    
    def _on_auto_renewal_toggle(self):
        """
        @brief      自动续鱼开关回调
        """
        self.on_settings_change({
            'auto_renewal': self.auto_renewal_enabled.get()
        })

    def _on_mode_change(self):
        """
        @brief      控制模式改变回调
        """
        self.on_settings_change({
            'mode': self.control_mode.get()
        })
    
    def get_settings(self) -> dict:
        """
        @brief      获取当前设置
        @return     设置字典
        """
        return {
            'auto_fish': self.auto_fish_enabled.get(),
            'auto_renewal': self.auto_renewal_enabled.get(),
            'mode': self.control_mode.get()
        }
    
    def run(self):
        """
        @brief      运行控制面板主循环
        """
        self.root.mainloop()
    
    def update(self):
        """
        @brief      更新窗口(非阻塞)
        """
        self.root.update_idletasks()
        self.root.update()
    
    def is_alive(self) -> bool:
        """
        @brief      检查窗口是否存活
        @return     窗口是否仍然存在
        """
        try:
            return self.root.winfo_exists()
        except tk.TclError:
            return False