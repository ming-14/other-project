#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
百度贴吧主楼评论提取器 - GUI版本

功能说明：
1. 图形化界面，操作简单直观
2. 支持选择HAR文件
3. 提供筛选特定作者、提取文本、移除表情符号等选项
4. 实时显示处理进度和日志
5. 与命令行版本共享核心功能

使用方式：
直接运行本文件即可启动GUI界面
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.scrolledtext as scrolledtext

# 导入核心功能模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from tieba_comment_extractor import TiebaCommentExtractor


class TiebaCommentGUI:
    """百度贴吧评论提取器GUI类"""
    
    def __init__(self, root):
        """
        初始化GUI界面
        
        Args:
            root: Tkinter根窗口对象
        """
        self.root = root
        self.root.title("百度贴吧主楼评论提取器")
        self.root.geometry("400x600")
        self.root.resizable(True, True)
        
        # 设置主题样式
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        # 初始化变量
        self.har_file_path = tk.StringVar()
        self.author_id = tk.StringVar()
        self.extract_text = tk.BooleanVar(value=True)
        self.remove_emoji = tk.BooleanVar(value=True)
        self.is_processing = False
        
        # 创建组件
        self.create_widgets()
        
    def create_widgets(self):
        """创建GUI组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="百度贴吧主楼评论提取器", font=("微软雅黑", 16, "bold"))
        title_label.pack(pady=10)
        
        # 文件选择区域
        file_frame = ttk.LabelFrame(main_frame, text="文件选择", padding="10")
        file_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(file_frame, text="HAR文件:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(file_frame, textvariable=self.har_file_path, width=60).grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(file_frame, text="浏览", command=self.browse_file).grid(row=0, column=2, padx=5, pady=5)
        
        # 配置列权重，使输入框可扩展
        file_frame.columnconfigure(1, weight=1)
        
        # 选项设置区域
        options_frame = ttk.LabelFrame(main_frame, text="选项设置", padding="10")
        options_frame.pack(fill=tk.X, pady=10)
        
        # 作者ID筛选
        ttk.Label(options_frame, text="作者ID (可选):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(options_frame, textvariable=self.author_id, width=30).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        
        # 功能选项
        ttk.Checkbutton(options_frame, text="提取文本内容", variable=self.extract_text).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Checkbutton(options_frame, text="移除表情符号", variable=self.remove_emoji).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # 操作按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)
        
        self.start_button = ttk.Button(button_frame, text="开始提取", command=self.start_processing, style="Accent.TButton")
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.cancel_button = ttk.Button(button_frame, text="取消", command=self.cancel_processing, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=5)
        
        self.clear_button = ttk.Button(button_frame, text="清空日志", command=self.clear_log)
        self.clear_button.pack(side=tk.LEFT, padx=5)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=10)
        
        # 日志输出区域
        log_frame = ttk.LabelFrame(main_frame, text="处理日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, width=80, height=20, font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
        # 底部状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 自定义样式
        self.style.configure("Accent.TButton", font=("微软雅黑", 10, "bold"))
    
    def browse_file(self):
        """浏览并选择HAR文件"""
        file_path = filedialog.askopenfilename(
            title="选择HAR文件",
            filetypes=[("HAR文件", "*.har"), ("所有文件", "*.*")]
        )
        if file_path:
            self.har_file_path.set(file_path)
            self.log(f"已选择文件: {file_path}")
    
    def log(self, message):
        """
        记录日志信息
        
        Args:
            message: 要记录的日志消息
        """
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def clear_log(self):
        """清空日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.log("日志已清空")
    
    def update_status(self, status):
        """
        更新状态栏
        
        Args:
            status: 要显示的状态信息
        """
        self.status_var.set(status)
    
    def update_progress(self, value):
        """
        更新进度条
        
        Args:
            value: 进度值 (0-100)
        """
        self.progress_var.set(value)
    
    def start_processing(self):
        """开始处理HAR文件"""
        # 检查文件是否选择
        if not self.har_file_path.get():
            messagebox.showerror("错误", "请先选择HAR文件")
            return
        
        # 检查文件是否存在
        if not os.path.exists(self.har_file_path.get()):
            messagebox.showerror("错误", "所选文件不存在")
            return
        
        # 禁用按钮
        self.start_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.is_processing = True
        
        # 清空日志和进度条
        self.clear_log()
        self.update_progress(0)
        self.update_status("正在处理...")
        
        # 启动后台线程处理
        threading.Thread(target=self.process_har_file, daemon=True).start()
    
    def cancel_processing(self):
        """取消处理"""
        self.is_processing = False
        self.update_status("已取消")
        self.start_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
    
    def process_har_file(self):
        """
        处理HAR文件的核心逻辑
        在后台线程中执行
        """
        try:
            # 创建提取器实例
            extractor = TiebaCommentExtractor(self.har_file_path.get())
            
            # 重定向标准输出到日志
            original_stdout = sys.stdout
            sys.stdout = self
            
            # 解析HAR文件 (20%进度)
            self.update_progress(20)
            json_files = extractor.parse_har_file()
            
            if not self.is_processing:
                return
            
            # 提取主评论 (40%进度)
            self.update_progress(40)
            extractor.extract_main_comments(json_files)
            
            if not self.is_processing:
                return
            
            # 清理临时文件夹
            import shutil
            shutil.rmtree(extractor.temp_dir)
            self.log(f"已清理临时目录: {extractor.temp_dir}")
            
            # 筛选特定作者 (60%进度)
            author_id = self.author_id.get().strip()
            if author_id:
                self.update_progress(60)
                extractor.filter_by_author(author_id)
            
            if not self.is_processing:
                return
            
            # 提取文本内容 (80%进度)
            if self.extract_text.get():
                self.update_progress(80)
                extractor.extract_texts(use_filtered=bool(author_id))
                
                # 移除表情符号 (100%进度)
                if self.remove_emoji.get():
                    self.update_progress(100)
                    extractor.remove_emoticons()
            
            if not self.is_processing:
                return
            
            # 处理完成
            self.update_progress(100)
            self.update_status("处理完成")
            self.log("\n" + "=" * 60)
            self.log("提取完成！")
            messagebox.showinfo("成功", "评论提取完成！")
            
        except Exception as e:
            self.log(f"错误: {str(e)}")
            self.update_status(f"处理失败: {str(e)}")
            messagebox.showerror("错误", f"处理过程中发生错误: {str(e)}")
        finally:
            # 恢复标准输出
            sys.stdout = original_stdout
            
            # 启用按钮
            self.start_button.config(state=tk.NORMAL)
            self.cancel_button.config(state=tk.DISABLED)
            self.is_processing = False
    
    def write(self, text):
        """
        重定向标准输出的write方法
        用于将命令行输出显示到日志中
        
        Args:
            text: 要写入的文本
        """
        if text.strip():
            self.log(text.strip())
    
    def flush(self):
        """重定向标准输出的flush方法"""
        pass


def main():
    """主函数，启动GUI应用"""
    import tkinter as tk
    
    # 创建主窗口
    root = tk.Tk()
    
    # 设置窗口图标（如果有）
    try:
        from PIL import Image, ImageTk
        # 这里可以添加图标设置代码
    except ImportError:
        pass
    
    # 创建GUI实例
    app = TiebaCommentGUI(root)
    
    # 运行主循环
    root.mainloop()


if __name__ == '__main__':
    main()
