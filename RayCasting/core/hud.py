"""!
@file core/hud.py
@brief HUD信息构建模块

从多个提供者收集状态，构建底部HUD文本。
支持插件/扩展注册自定义HUD信息。
"""

import math
from typing import Callable, Optional
from core import log_manager

_logger = log_manager.get_logger('core.hud')


class HUD:
    """!@brief HUD信息构建器

    支持多个HUD信息提供者，按优先级组合输出。
    """

    def __init__(self):
        self._providers: dict[str, tuple[int, Callable[[], str]]] = {}

    def add_provider(self, name: str, provider: Callable[[], str],
                     priority: int = 0) -> None:
        """!@brief 添加HUD信息提供者

        @param name     提供者名称（唯一标识）
        @param provider 无参回调，返回要显示的字符串
        @param priority 优先级，越小越靠前
        """
        self._providers[name] = (priority, provider)

    def remove_provider(self, name: str) -> None:
        """!@brief 移除HUD信息提供者"""
        self._providers.pop(name, None)

    def build(self, player, mouse_enabled: bool, fps: float,
              render_mode: str, width: int) -> str:
        """!@brief 构建底部HUD信息文本

        @param player        玩家对象
        @param mouse_enabled 鼠标锁定状态
        @param fps           当前帧率
        @param render_mode   渲染模式描述字符串
        @param width         终端宽度（用于截断）
        @return HUD字符串
        """
        parts = []
        sorted_providers = sorted(self._providers.items(),
                                  key=lambda x: x[1][0])
        for name, (priority, provider) in sorted_providers:
            try:
                text = provider()
                if text:
                    parts.append(text)
            except Exception as e:
                _logger.error('HUD提供者 "%s" 异常: %s', name, e)

        if not parts:
            angle_deg = math.degrees(player.angle) % 360.0
            mouse_status = '鼠标:开' if mouse_enabled else '鼠标:关'
            default = (' 坐标:(%.1f,%.1f) 朝向:%.0f° %s %s FPS:%.0f  '
                       'WASD移动 Shift疾跑 鼠标点击锁定 ESC暂停'
                       % (player.x, player.y, angle_deg,
                          mouse_status, render_mode, fps))
            if len(default) > width:
                default = default[:width]
            return default

        hud = ' '.join(parts)
        if len(hud) > width:
            hud = hud[:width]
        return hud

    @staticmethod
    def default_provider(player, mouse_enabled: bool, fps: float,
                         render_mode: str) -> Callable[[], str]:
        """!@brief 创建默认HUD提供者"""
        def provider() -> str:
            angle_deg = math.degrees(player.angle) % 360.0
            mouse_status = '鼠标:开' if mouse_enabled else '鼠标:关'
            return ('坐标:(%.1f,%.1f) 朝向:%.0f° %s %s FPS:%.0f'
                    % (player.x, player.y, angle_deg,
                       mouse_status, render_mode, fps))
        return provider
