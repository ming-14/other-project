#!/usr/bin/env python3
"""
GitHub Release Downloader GUI
使用tkinter构建的图形界面，支持完整的下载功能和调试功能
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
import threading
import queue
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from config import Config, MirrorConfig, MirrorStrategy, RequestType
from fetcher import ReleaseFetcher, ApiReleaseFetcher, HtmlReleaseFetcher
from main import (
    HttpClient,
    FileDownloader,
    GitHubReleaseDownloader
)


class LogHandler(logging.Handler):
    """自定义日志处理器，将日志输出到GUI"""
    
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue
    
    def emit(self, record):
        msg = self.format(record)
        self.log_queue.put(('log', msg))


class MirrorConfigDialog(tk.Toplevel):
    """镜像站配置对话框"""
    
    def __init__(self, parent, title="镜像配置", mirror_config=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("450x350")
        self.resizable(False, False)
        self.result = None
        self.transient(parent)
        self.grab_set()
        
        mc = mirror_config or MirrorConfig("", strategy=MirrorStrategy.PREFIX,
                                            supported_types=[RequestType.API, RequestType.DOWNLOAD, RequestType.RAW, RequestType.GIST])
        
        main_frame = ttk.Frame(self, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(1, weight=1)
        
        # URL
        ttk.Label(main_frame, text="镜像URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_entry = ttk.Entry(main_frame, width=40)
        self.url_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        if mc.url:
            self.url_entry.insert(0, mc.url)
        
        # 策略
        ttk.Label(main_frame, text="请求策略:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.strategy_var = tk.StringVar(value="prefix" if mc.strategy == MirrorStrategy.PREFIX else "replace")
        strategy_frame = ttk.Frame(main_frame)
        strategy_frame.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        ttk.Radiobutton(strategy_frame, text="前缀拼接 (mirror+原始URL)", variable=self.strategy_var, value="prefix").pack(anchor=tk.W)
        ttk.Radiobutton(strategy_frame, text="域名替换 (替换域名部分)", variable=self.strategy_var, value="replace").pack(anchor=tk.W)
        
        # 支持的请求类型
        ttk.Label(main_frame, text="支持的请求类型:").grid(row=2, column=0, sticky=tk.W, pady=5)
        types_frame = ttk.Frame(main_frame)
        types_frame.grid(row=2, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        
        self.type_vars = {}
        type_options = [
            ('API (api.github.com)', RequestType.API),
            ('下载 (releases/download)', RequestType.DOWNLOAD),
            ('Raw (raw.githubusercontent.com)', RequestType.RAW),
            ('Gist (gist.githubusercontent.com)', RequestType.GIST),
            ('HTML (github.com页面)', RequestType.HTML),
            ('Git (git clone)', RequestType.GIT),
        ]
        
        for i, (label, rtype) in enumerate(type_options):
            var = tk.BooleanVar(value=rtype in mc.supported_types)
            self.type_vars[rtype] = var
            ttk.Checkbutton(types_frame, text=label, variable=var).grid(row=i, column=0, sticky=tk.W)
        
        # 按钮
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="确定", command=self.on_ok, width=10).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.on_cancel, width=10).grid(row=0, column=1, padx=5)
        
        self.url_entry.focus_set()
        self.bind('<Return>', lambda e: self.on_ok())
        self.bind('<Escape>', lambda e: self.on_cancel())
    
    def on_ok(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入镜像URL", parent=self)
            return
        
        strategy = MirrorStrategy.PREFIX if self.strategy_var.get() == "prefix" else MirrorStrategy.REPLACE
        supported_types = [rtype for rtype, var in self.type_vars.items() if var.get()]
        
        if not supported_types:
            messagebox.showwarning("提示", "请至少选择一种请求类型", parent=self)
            return
        
        self.result = MirrorConfig(url, strategy=strategy, supported_types=supported_types, name=url)
        self.destroy()
    
    def on_cancel(self):
        self.destroy()


class GitHubReleaseDownloaderGUI:
    """GitHub Release下载器GUI主类"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub Release Downloader")
        self.root.geometry("1000x800")
        self.root.minsize(600, 500)  # 设置最小窗口大小
        
        # 状态变量
        self.is_downloading = False
        self.is_fetching = False
        self.debug_mode = tk.BooleanVar(value=False)
        self.force_refresh = tk.BooleanVar(value=False)
        self.fetch_method = tk.StringVar(value="auto")  # auto, api, html
        self.log_queue = queue.Queue()
        
        # 配置
        self.config = Config()
        self.downloader = None
        
        # 设置日志
        self.setup_logging()
        
        # 创建UI
        self.create_ui()
        
        # 启动日志处理
        self.root.after(100, self.process_log_queue)
    
    def setup_logging(self):
        """设置日志系统"""
        self.logger = logging.getLogger('GitHubReleaseDownloader')
        self.logger.setLevel(logging.DEBUG)
        
        # 清除现有处理器
        self.logger.handlers.clear()
        
        # 添加队列处理器
        queue_handler = LogHandler(self.log_queue)
        queue_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', 
                                      datefmt='%H:%M:%S')
        queue_handler.setFormatter(formatter)
        self.logger.addHandler(queue_handler)
    
    def create_ui(self):
        """创建用户界面"""
        # 创建主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(0, weight=1)
        
        # 创建PanedWindow用于垂直分割
        self.paned_window = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        self.paned_window.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.rowconfigure(0, weight=1)
        
        # 创建上部区域（配置和镜像）
        top_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(top_frame, weight=1)
        
        # 创建中部区域（操作和进度）
        middle_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(middle_frame, weight=0)
        
        # 创建下部区域（日志）
        bottom_frame = ttk.Frame(self.paned_window)
        self.paned_window.add(bottom_frame, weight=2)
        
        # 标题
        title_label = ttk.Label(
            top_frame, 
            text="GitHub Release Downloader",
            font=('Arial', 16, 'bold')
        )
        title_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 10))
        
        # 配置区域
        self.create_config_section(top_frame)
        
        # 镜像配置区域
        self.create_mirror_section(top_frame)
        
        # 操作按钮区域
        self.create_action_section(middle_frame)
        
        # Release信息显示区域
        self.create_release_info_section(middle_frame)
        
        # 进度区域
        self.create_progress_section(middle_frame)
        
        # 日志区域
        self.create_log_section(bottom_frame)
    
    def create_config_section(self, parent):
        """创建配置区域"""
        config_frame = ttk.LabelFrame(parent, text="配置", padding="10")
        config_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        parent.columnconfigure(0, weight=1)
        config_frame.columnconfigure(1, weight=1)
        
        # 仓库
        ttk.Label(config_frame, text="仓库:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.repo_entry = ttk.Entry(config_frame)
        self.repo_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        self.repo_entry.insert(0, "owner/repo")
        
        # 正则表达式
        ttk.Label(config_frame, text="文件匹配:").grid(row=1, column=0, sticky=tk.W, padx=5)
        self.pattern_entry = ttk.Entry(config_frame)
        self.pattern_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        self.pattern_entry.insert(0, "\\.exe$")
        
        # 输出目录
        ttk.Label(config_frame, text="输出目录:").grid(row=2, column=0, sticky=tk.W, padx=5)
        output_frame = ttk.Frame(config_frame)
        output_frame.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        output_frame.columnconfigure(0, weight=1)
        
        self.output_entry = ttk.Entry(output_frame)
        self.output_entry.grid(row=0, column=0, sticky=(tk.W, tk.E))
        self.output_entry.insert(0, str(Path.cwd()))
        
        browse_btn = ttk.Button(output_frame, text="浏览...", command=self.browse_output_dir)
        browse_btn.grid(row=0, column=1, padx=(5, 0))
        
        # Token
        ttk.Label(config_frame, text="GitHub Token:").grid(row=3, column=0, sticky=tk.W, padx=5)
        self.token_entry = ttk.Entry(config_frame, show="*")
        self.token_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=5, pady=2)
        
        # 显示/隐藏Token
        self.show_token_var = tk.BooleanVar(value=False)
        show_token_btn = ttk.Checkbutton(
            config_frame, 
            text="显示Token",
            variable=self.show_token_var,
            command=self.toggle_token_visibility
        )
        show_token_btn.grid(row=3, column=2, padx=5)
    
    def create_mirror_section(self, parent):
        """创建镜像配置区域"""
        mirror_frame = ttk.LabelFrame(parent, text="镜像站配置", padding="10")
        mirror_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        parent.rowconfigure(2, weight=1)
        mirror_frame.columnconfigure(0, weight=1)
        mirror_frame.rowconfigure(0, weight=1)
        
        # 左侧：镜像列表
        list_frame = ttk.Frame(mirror_frame)
        list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        mirror_frame.columnconfigure(0, weight=3)
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # 使用Treeview显示镜像信息
        columns = ('url', 'strategy', 'types')
        self.mirror_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=6)
        self.mirror_tree.heading('url', text='镜像URL')
        self.mirror_tree.heading('strategy', text='策略')
        self.mirror_tree.heading('types', text='支持类型')
        self.mirror_tree.column('url', width=250)
        self.mirror_tree.column('strategy', width=80)
        self.mirror_tree.column('types', width=200)
        self.mirror_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.mirror_tree.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.mirror_tree.config(yscrollcommand=scrollbar.set)
        
        # 右侧：操作按钮
        button_frame = ttk.Frame(mirror_frame)
        button_frame.grid(row=0, column=1, padx=5)
        mirror_frame.columnconfigure(1, weight=0)
        
        ttk.Button(button_frame, text="添加镜像", command=self.add_mirror).grid(row=0, column=0, pady=2, sticky=tk.EW)
        ttk.Button(button_frame, text="编辑镜像", command=self.edit_mirror).grid(row=1, column=0, pady=2, sticky=tk.EW)
        ttk.Button(button_frame, text="删除镜像", command=self.remove_mirror).grid(row=2, column=0, pady=2, sticky=tk.EW)
        ttk.Button(button_frame, text="上移", command=self.move_mirror_up).grid(row=3, column=0, pady=2, sticky=tk.EW)
        ttk.Button(button_frame, text="下移", command=self.move_mirror_down).grid(row=4, column=0, pady=2, sticky=tk.EW)
        ttk.Button(button_frame, text="重置默认", command=self.reset_mirrors).grid(row=5, column=0, pady=2, sticky=tk.EW)
        
        # 加载默认镜像
        self.load_default_mirrors()
    
    def create_action_section(self, parent):
        """创建操作按钮区域"""
        action_frame = ttk.Frame(parent)
        action_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=10)
        parent.columnconfigure(0, weight=1)
        
        # 第一行按钮
        row0_frame = ttk.Frame(action_frame)
        row0_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        self.download_btn = ttk.Button(
            row0_frame, 
            text="开始下载",
            command=self.start_download,
            width=12
        )
        self.download_btn.pack(side=tk.LEFT, padx=3)
        
        self.stop_btn = ttk.Button(
            row0_frame,
            text="停止",
            command=self.stop_download,
            width=8,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=3)
        
        self.fetch_info_btn = ttk.Button(
            row0_frame,
            text="获取Release信息",
            command=self.fetch_release_info,
            width=15
        )
        self.fetch_info_btn.pack(side=tk.LEFT, padx=3)
        
        ttk.Button(row0_frame, text="清除日志", command=self.clear_log, width=8).pack(side=tk.LEFT, padx=3)
        ttk.Button(row0_frame, text="清除缓存", command=self.clear_release_cache, width=8).pack(side=tk.LEFT, padx=3)
        ttk.Button(row0_frame, text="导出配置", command=self.export_config, width=8).pack(side=tk.LEFT, padx=3)
        ttk.Button(row0_frame, text="导入配置", command=self.import_config, width=8).pack(side=tk.LEFT, padx=3)
        
        # 第二行选项
        row1_frame = ttk.Frame(action_frame)
        row1_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(5, 0))
        
        ttk.Checkbutton(
            row1_frame,
            text="调试模式",
            variable=self.debug_mode,
            command=self.toggle_debug_mode
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Checkbutton(
            row1_frame,
            text="强制刷新(忽略缓存)",
            variable=self.force_refresh
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Separator(row1_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        ttk.Label(row1_frame, text="获取方式:").pack(side=tk.LEFT)
        ttk.Radiobutton(row1_frame, text="自动", variable=self.fetch_method, value="auto").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(row1_frame, text="API", variable=self.fetch_method, value="api").pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(row1_frame, text="HTML", variable=self.fetch_method, value="html").pack(side=tk.LEFT, padx=2)
    
    def create_progress_section(self, parent):
        """创建进度区域"""
        progress_frame = ttk.LabelFrame(parent, text="进度", padding="10")
        progress_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        parent.columnconfigure(0, weight=1)
        progress_frame.columnconfigure(0, weight=1)
        
        # 进度条
        self.progress = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 状态标签
        self.status_label = ttk.Label(progress_frame, text="就绪")
        self.status_label.grid(row=1, column=0, sticky=tk.W)
    
    def create_release_info_section(self, parent):
        """创建Release信息显示区域"""
        info_frame = ttk.LabelFrame(parent, text="Release信息", padding="10")
        info_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        info_frame.columnconfigure(0, weight=1)
        info_frame.rowconfigure(0, weight=1)
        
        # Release信息文本框
        self.release_info_text = scrolledtext.ScrolledText(
            info_frame,
            height=8,
            wrap=tk.WORD,
            font=('Consolas', 9),
            state=tk.DISABLED
        )
        self.release_info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置颜色标签
        self.release_info_text.tag_config('tag', foreground='blue', font=('Consolas', 9, 'bold'))
        self.release_info_text.tag_config('asset', foreground='green')
        self.release_info_text.tag_config('header', foreground='purple', font=('Consolas', 9, 'bold'))
    
    def create_log_section(self, parent):
        """创建日志区域"""
        log_frame = ttk.LabelFrame(parent, text="日志", padding="10")
        log_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # 日志文本框
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=15,
            wrap=tk.WORD,
            font=('Consolas', 9)
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置日志颜色标签
        self.log_text.tag_config('INFO', foreground='black')
        self.log_text.tag_config('DEBUG', foreground='gray')
        self.log_text.tag_config('WARNING', foreground='orange')
        self.log_text.tag_config('ERROR', foreground='red')
        self.log_text.tag_config('SUCCESS', foreground='green')
    
    # ==================== 配置相关方法 ====================
    
    def browse_output_dir(self):
        """浏览输出目录"""
        directory = filedialog.askdirectory()
        if directory:
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, directory)
    
    def toggle_token_visibility(self):
        """切换Token可见性"""
        if self.show_token_var.get():
            self.token_entry.config(show="")
        else:
            self.token_entry.config(show="*")
    
    # ==================== 镜像相关方法 ====================
    
    def _format_types(self, supported_types):
        """格式化支持的请求类型"""
        type_names = {
            'api': 'API',
            'download': '下载',
            'raw': 'Raw',
            'gist': 'Gist',
            'html': 'HTML',
            'git': 'Git'
        }
        return ', '.join(type_names.get(t.value, t.value) for t in supported_types)
    
    def _add_mirror_to_tree(self, mirror_config):
        """添加镜像到Treeview"""
        if mirror_config.url is None:
            url = "原始GitHub"
        else:
            url = mirror_config.url
        
        strategy = "前缀拼接" if mirror_config.strategy == MirrorStrategy.PREFIX else "域名替换"
        types = self._format_types(mirror_config.supported_types)
        
        self.mirror_tree.insert('', tk.END, values=(url, strategy, types), tags=(str(id(mirror_config)),))
    
    def load_default_mirrors(self):
        """加载默认镜像"""
        for item in self.mirror_tree.get_children():
            self.mirror_tree.delete(item)
        for mirror_config in Config.DEFAULT_MIRRORS:
            self._add_mirror_to_tree(mirror_config)
    
    def add_mirror(self):
        """添加镜像"""
        dialog = MirrorConfigDialog(self.root, title="添加镜像")
        self.root.wait_window(dialog)
        
        if dialog.result:
            mc = dialog.result
            self._add_mirror_to_tree(mc)
            self.logger.info(f"添加镜像: {mc.name} (策略: {mc.strategy.value})")
    
    def edit_mirror(self):
        """编辑镜像"""
        selection = self.mirror_tree.selection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个镜像")
            return
        
        item = selection[0]
        values = self.mirror_tree.item(item, 'values')
        
        mirror_config = self._values_to_mirror_config(values)
        dialog = MirrorConfigDialog(self.root, title="编辑镜像", mirror_config=mirror_config)
        self.root.wait_window(dialog)
        
        if dialog.result:
            mc = dialog.result
            strategy = "前缀拼接" if mc.strategy == MirrorStrategy.PREFIX else "域名替换"
            types = self._format_types(mc.supported_types)
            self.mirror_tree.item(item, values=(mc.url or "原始GitHub", strategy, types))
            self.logger.info(f"编辑镜像: {mc.name}")
    
    def _values_to_mirror_config(self, values):
        """从Treeview值转换为MirrorConfig"""
        url, strategy_str, types_str = values
        
        if url == "原始GitHub":
            return MirrorConfig(None, name="原始GitHub")
        
        strategy = MirrorStrategy.PREFIX if strategy_str == "前缀拼接" else MirrorStrategy.REPLACE
        
        type_map = {
            'API': RequestType.API,
            '下载': RequestType.DOWNLOAD,
            'Raw': RequestType.RAW,
            'Gist': RequestType.GIST,
            'HTML': RequestType.HTML,
            'Git': RequestType.GIT
        }
        supported_types = []
        for part in types_str.split(', '):
            part = part.strip()
            if part in type_map:
                supported_types.append(type_map[part])
        
        if not supported_types:
            supported_types = [RequestType.API, RequestType.DOWNLOAD, RequestType.RAW, RequestType.GIST]
        
        return MirrorConfig(url, strategy=strategy, supported_types=supported_types, name=url)
    
    def remove_mirror(self):
        """删除镜像"""
        selection = self.mirror_tree.selection()
        if selection:
            item = selection[0]
            values = self.mirror_tree.item(item, 'values')
            self.mirror_tree.delete(item)
            self.logger.info(f"删除镜像: {values[0]}")
    
    def move_mirror_up(self):
        """上移镜像"""
        selection = self.mirror_tree.selection()
        if not selection:
            return
        item = selection[0]
        idx = self.mirror_tree.index(item)
        if idx > 0:
            values = self.mirror_tree.item(item, 'values')
            self.mirror_tree.delete(item)
            self.mirror_tree.insert('', idx - 1, values=values)
            children = self.mirror_tree.get_children()
            self.mirror_tree.selection_set(children[idx - 1])
    
    def move_mirror_down(self):
        """下移镜像"""
        selection = self.mirror_tree.selection()
        if not selection:
            return
        item = selection[0]
        idx = self.mirror_tree.index(item)
        children = self.mirror_tree.get_children()
        if idx < len(children) - 1:
            values = self.mirror_tree.item(item, 'values')
            self.mirror_tree.delete(item)
            self.mirror_tree.insert('', idx + 1, values=values)
            children = self.mirror_tree.get_children()
            self.mirror_tree.selection_set(children[idx + 1])
    
    def reset_mirrors(self):
        """重置镜像为默认"""
        self.load_default_mirrors()
        self.logger.info("镜像已重置为默认值")
    
    def get_mirrors_from_tree(self):
        """从Treeview获取镜像列表"""
        mirrors = []
        for item in self.mirror_tree.get_children():
            values = self.mirror_tree.item(item, 'values')
            mc = self._values_to_mirror_config(values)
            mirrors.append(mc)
        return mirrors
    
    # ==================== 获取Release信息相关方法 ====================
    
    def fetch_release_info(self):
        """获取Release信息（不下载）"""
        if self.is_fetching or self.is_downloading:
            return
        
        repo = self.repo_entry.get().strip()
        token = self.token_entry.get().strip() or None
        mirrors = self.get_mirrors_from_tree()
        force = self.force_refresh.get()
        
        if not repo:
            messagebox.showerror("错误", "请输入仓库地址")
            return
        
        self.is_fetching = True
        self.fetch_info_btn.config(state=tk.DISABLED)
        self.download_btn.config(state=tk.DISABLED)
        self.progress.start()
        self.status_label.config(text="获取Release信息中...")
        
        self.release_info_text.config(state=tk.NORMAL)
        self.release_info_text.delete(1.0, tk.END)
        self.release_info_text.config(state=tk.DISABLED)
        
        self.config = Config(token=token, mirrors=mirrors)
        
        self.fetch_thread = threading.Thread(
            target=self.fetch_info_worker,
            args=(repo, force),
            daemon=True
        )
        self.fetch_thread.start()
        
        self.logger.info(f"开始获取Release信息: {repo}" + (" (强制刷新)" if force else ""))
        self.logger.debug(f"获取方式: {self.fetch_method.get()}")
    
    def fetch_info_worker(self, repo, force=False):
        """获取Release信息工作线程"""
        try:
            method = self.fetch_method.get()
            
            if method == "api":
                self.downloader = GitHubReleaseDownloader(self.config)
                self.downloader.fetchers = [ApiReleaseFetcher(self.config, self.downloader.http_client)]
                release = self.downloader.get_latest_release(repo, force=force)
            elif method == "html":
                self.downloader = GitHubReleaseDownloader(self.config)
                self.downloader.fetchers = [HtmlReleaseFetcher(self.config, self.downloader.http_client)]
                release = self.downloader.get_latest_release(repo, force=force)
            else:
                self.downloader = GitHubReleaseDownloader(self.config)
                release = self.downloader.get_latest_release(repo, force=force)
            
            info_text = self.format_release_info(release)
            self.log_queue.put(('release_info', info_text))
            self.log_queue.put(('success', f"成功获取Release信息: {release.get('tag_name', 'unknown')}"))
            
        except Exception as e:
            self.log_queue.put(('error', f"获取Release信息失败: {str(e)}"))
            self.logger.exception("获取Release信息异常")
        finally:
            self.log_queue.put(('fetch_finish', None))
    
    def format_release_info(self, release):
        """格式化Release信息用于显示"""
        lines = []
        
        # Tag名称
        tag_name = release.get('tag_name', 'unknown')
        lines.append(f"Tag: {tag_name}")
        lines.append("=" * 50)
        lines.append("")
        
        # Assets
        assets = release.get('assets', [])
        if assets:
            lines.append(f"Assets ({len(assets)} 个文件):")
            lines.append("-" * 50)
            for i, asset in enumerate(assets, 1):
                name = asset.get('name', 'unknown')
                url = asset.get('browser_download_url', 'unknown')
                lines.append(f"{i}. {name}")
                lines.append(f"   URL: {url}")
                lines.append("")
        else:
            lines.append("无Assets文件")
        
        return "\n".join(lines)
    
    def reset_ui_state(self):
        """重置UI状态"""
        self.is_downloading = False
        self.is_fetching = False
        self.download_btn.config(state=tk.NORMAL)
        self.fetch_info_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.progress.stop()
        self.progress.config(value=0)
        self.status_label.config(text="就绪")
    
    # ==================== 下载相关方法 ====================
    
    def start_download(self):
        """开始下载"""
        if self.is_downloading:
            return
        
        repo = self.repo_entry.get().strip()
        pattern = self.pattern_entry.get().strip()
        output_dir = self.output_entry.get().strip()
        token = self.token_entry.get().strip() or None
        mirrors = self.get_mirrors_from_tree()
        force = self.force_refresh.get()
        
        if not repo:
            messagebox.showerror("错误", "请输入仓库地址")
            return
        if not pattern:
            messagebox.showerror("错误", "请输入文件匹配正则")
            return
        if not output_dir:
            messagebox.showerror("错误", "请选择输出目录")
            return
        
        self.is_downloading = True
        self.download_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress.start()
        self.status_label.config(text="下载中...")
        
        self.config = Config(token=token, mirrors=mirrors)
        self.downloader = GitHubReleaseDownloader(self.config)
        
        self.download_thread = threading.Thread(
            target=self.download_worker,
            args=(repo, pattern, output_dir, force),
            daemon=True
        )
        self.download_thread.start()
        
        self.logger.info(f"开始下载: {repo}" + (" (强制刷新)" if force else ""))
        self.logger.debug(f"配置 - 仓库: {repo}, 正则: {pattern}, 输出: {output_dir}")
        self.logger.debug(f"镜像数量: {len(mirrors)}")
    
    def download_worker(self, repo, pattern, output_dir, force=False):
        """下载工作线程"""
        try:
            self.downloader.download_matching_files(repo, pattern, output_dir, force=force)
            self.log_queue.put(('success', "下载完成!"))
        except Exception as e:
            self.log_queue.put(('error', f"下载失败: {str(e)}"))
            self.logger.exception("下载异常")
        finally:
            self.log_queue.put(('finish', None))
    
    def stop_download(self):
        """停止下载"""
        if self.is_downloading:
            self.is_downloading = False
            self.logger.warning("用户停止下载")
            self.log_queue.put(('finish', None))
    
    
    # ==================== 调试相关方法 ====================
    
    def toggle_debug_mode(self):
        """切换调试模式"""
        if self.debug_mode.get():
            self.logger.setLevel(logging.DEBUG)
            self.logger.info("调试模式已开启")
        else:
            self.logger.setLevel(logging.INFO)
            self.logger.info("调试模式已关闭")
    
    def clear_log(self):
        """清除日志"""
        self.log_text.delete(1.0, tk.END)
        self.logger.info("日志已清除")
    
    def clear_release_cache(self):
        """清除Release缓存"""
        if self.downloader:
            self.downloader.clear_cache()
            self.logger.info("Release缓存已清除")
        else:
            self.logger.info("无下载器实例，缓存为空")
    
    # ==================== 配置导入导出 ====================
    
    def export_config(self):
        """导出配置"""
        mirrors = self.get_mirrors_from_tree()
        config_data = {
            'repo': self.repo_entry.get(),
            'pattern': self.pattern_entry.get(),
            'output_dir': self.output_entry.get(),
            'token': self.token_entry.get(),
            'mirrors': [mc.to_dict() for mc in mirrors],
            'debug_mode': self.debug_mode.get()
        }
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            import json
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2, ensure_ascii=False)
                self.logger.info(f"配置已导出到: {file_path}")
                messagebox.showinfo("成功", "配置导出成功")
            except Exception as e:
                self.logger.error(f"导出配置失败: {e}")
                messagebox.showerror("错误", f"导出配置失败: {e}")
    
    def import_config(self):
        """导入配置"""
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            import json
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                self.repo_entry.delete(0, tk.END)
                self.repo_entry.insert(0, config_data.get('repo', ''))
                
                self.pattern_entry.delete(0, tk.END)
                self.pattern_entry.insert(0, config_data.get('pattern', ''))
                
                self.output_entry.delete(0, tk.END)
                self.output_entry.insert(0, config_data.get('output_dir', ''))
                
                self.token_entry.delete(0, tk.END)
                self.token_entry.insert(0, config_data.get('token', ''))
                
                self.debug_mode.set(config_data.get('debug_mode', False))
                
                # 加载镜像
                mirrors_data = config_data.get('mirrors', [])
                for item in self.mirror_tree.get_children():
                    self.mirror_tree.delete(item)
                
                for mirror_data in mirrors_data:
                    if isinstance(mirror_data, dict):
                        mc = MirrorConfig.from_dict(mirror_data)
                    elif isinstance(mirror_data, str):
                        mc = Config.create_mirror_from_string(mirror_data)
                    else:
                        continue
                    self._add_mirror_to_tree(mc)
                
                self.logger.info(f"配置已从 {file_path} 导入")
                messagebox.showinfo("成功", "配置导入成功")
            except Exception as e:
                self.logger.error(f"导入配置失败: {e}")
                messagebox.showerror("错误", f"导入配置失败: {e}")
    
    # ==================== 日志处理 ====================
    
    def process_log_queue(self):
        """处理日志队列"""
        try:
            while True:
                try:
                    msg_type, msg = self.log_queue.get_nowait()
                    
                    if msg_type == 'log':
                        # 确定日志级别和颜色
                        if '[DEBUG]' in msg:
                            tag = 'DEBUG'
                        elif '[INFO]' in msg:
                            tag = 'INFO'
                        elif '[WARNING]' in msg:
                            tag = 'WARNING'
                        elif '[ERROR]' in msg:
                            tag = 'ERROR'
                        else:
                            tag = 'INFO'
                        
                        # 如果不是调试模式，跳过DEBUG日志
                        if not self.debug_mode.get() and tag == 'DEBUG':
                            continue
                        
                        self.log_text.insert(tk.END, msg + '\n', tag)
                        self.log_text.see(tk.END)
                    
                    elif msg_type == 'success':
                        self.log_text.insert(tk.END, msg + '\n', 'SUCCESS')
                        self.log_text.see(tk.END)
                    
                    elif msg_type == 'error':
                        self.log_text.insert(tk.END, msg + '\n', 'ERROR')
                        self.log_text.see(tk.END)
                    
                    elif msg_type == 'finish':
                        self.reset_ui_state()
                    
                    elif msg_type == 'fetch_finish':
                        self.reset_ui_state()
                    
                    elif msg_type == 'release_info':
                        self.release_info_text.config(state=tk.NORMAL)
                        self.release_info_text.delete(1.0, tk.END)
                        self.release_info_text.insert(tk.END, msg, 'header')
                        self.release_info_text.config(state=tk.DISABLED)
                
                except queue.Empty:
                    break
        except Exception as e:
            print(f"日志处理错误: {e}")
        
        # 继续处理
        self.root.after(100, self.process_log_queue)


def main():
    """主函数"""
    root = tk.Tk()
    
    # 设置图标（如果有的话）
    try:
        # 可以在这里设置应用图标
        pass
    except:
        pass
    
    app = GitHubReleaseDownloaderGUI(root)
    
    # 处理窗口关闭事件
    def on_closing():
        if app.is_downloading:
            if messagebox.askokcancel("退出", "下载正在进行中，确定要退出吗？"):
                app.stop_download()
                root.destroy()
        else:
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    root.mainloop()


if __name__ == '__main__':
    main()
