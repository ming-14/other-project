"""!
@file core/engine/game.py
@brief 游戏引擎主控制器

纯引擎层，只提供基础设施：主循环、子系统初始化、渲染管线。
不包含任何游戏逻辑（迷宫/神庙逃亡等），游戏逻辑在 programs/ 中实现。
"""

import gc
import os
import sys
import time

import config
from core.logging import log_manager
from core.event_bus import EventBus, EventType
from core.state_machine import StateMachine
from core.registry import ComponentRegistry, get_registry
from core.settings import SettingsManager, get_settings
from core.engine.plugin import PluginManager, PluginContext
from core.engine.api import EngineAPI
from core.hud import HUD
from core.animation import TweenManager
from core.audio import AudioSystem
from world.player import Player
from world.raycaster import Raycaster
from world.world_manager import WorldManager
from render.pipeline import RenderPipeline
from render.lighting import Lighting
from input.base import InputSystem, MouseInput
from platform.base import PlatformOutput

_logger = log_manager.get_logger('core.game')


class Engine:
    """!@brief 游戏引擎主控制器

    纯引擎层，不包含游戏逻辑。
    提供主循环、子系统管理、插件系统、渲染管线等基础设施。
    游戏逻辑通过 set_program() 注入。
    """

    def __init__(self):
        log_manager.setup(config_path='log_config.json')
        _logger.info('引擎初始化开始')

        self._enable_ansi()

        # 核心基础设施
        self.events = EventBus()
        self.states = StateMachine()
        self.registry = get_registry()
        self.settings = get_settings()
        self.plugin_manager = PluginManager()
        self.hud = HUD()
        self.api = EngineAPI(self)

        # 世界子系统
        self.player = Player(1.5, 1.5, 0.0)
        self.raycaster = Raycaster(None)
        self.lighting = Lighting()
        self.render_pipeline = RenderPipeline(None, self.lighting)
        self.world_manager = WorldManager(self.events)

        from world.entity_manager import EntityManager
        from world.camera import Camera
        from world.collision_ext import TriggerSystem
        from render.sprite_renderer import SpriteRenderer
        from render.particle_renderer import ParticleRenderLayer

        self.entity_manager = EntityManager(self.events)
        self.camera = Camera(self.player)
        self.tweens = TweenManager()
        self.audio = AudioSystem(self.events)
        self.triggers = TriggerSystem(self.events)

        self._sprite_renderer = SpriteRenderer(self.entity_manager)
        self.render_pipeline.add_layer('sprites', self._sprite_renderer, priority=5)

        self.particle_layer = ParticleRenderLayer(player=self.player)
        self.render_pipeline.add_layer('particles', self.particle_layer, priority=6)

        # 平台层
        self.input_system = self._create_input()
        self.mouse = self._create_mouse()
        self.output = PlatformOutput.create()

        # 运行时状态
        self._paused_mouse_enabled = False
        self._frame_interval = 1.0 / config.TARGET_FPS
        self._fps = 0.0
        self._frame_count = 0
        self._fps_timer = 0.0
        self._running = False
        self._delta_time = 0.0
        self._program = None

        # 初始化
        self._setup_default_settings()
        self._register_default_components()
        self._setup_event_bridge()

        plugin_ctx = PluginContext(self)
        self.plugin_manager.initialize(plugin_ctx)

        log_manager.get_manager().subscribe_events(self.events)
        _logger.info('引擎初始化完成')

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def running(self) -> bool:
        return self._running

    @property
    def delta_time(self) -> float:
        return self._delta_time

    @property
    def program(self):
        return self._program

    @staticmethod
    def _create_input() -> InputSystem:
        from platform.win32_input import Win32InputSystem
        return Win32InputSystem()

    @staticmethod
    def _create_mouse() -> MouseInput:
        from platform.win32_mouse import Win32MouseInput
        return Win32MouseInput()

    @staticmethod
    def _enable_ansi():
        if os.name == 'nt':
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.GetStdHandle(-11)
                mode = ctypes.c_uint32()
                kernel32.GetConsoleMode(handle, ctypes.byref(mode))
                kernel32.SetConsoleMode(handle, mode.value | 0x0004)
            except Exception:
                pass
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    def _setup_default_settings(self) -> None:
        gameplay = self.settings.group('gameplay')
        gameplay.define('move_speed', config.MOVE_SPEED)
        gameplay.define('rotate_speed', config.ROTATE_SPEED)
        gameplay.define('sprint_multiplier', config.SPRINT_MULTIPLIER)
        gameplay.define('mouse_sensitivity', config.MOUSE_SENSITIVITY)
        gameplay.define('mouse_pitch_sensitivity', config.MOUSE_PITCH_SENSITIVITY)

        rendering = self.settings.group('rendering')
        rendering.define('target_fps', config.TARGET_FPS)
        rendering.define('render_strategy', config.RENDER_STRATEGY)
        rendering.define('color_quantize_bits', config.COLOR_QUANTIZE_BITS)
        rendering.define('fog_near', config.FOG_NEAR)
        rendering.define('fog_far', config.FOG_FAR)
        rendering.define('fog_gamma', config.FOG_GAMMA)

        world = self.settings.group('world')
        world.define('maze_width', config.MAZE_WIDTH)
        world.define('maze_height', config.MAZE_HEIGHT)

    def _register_default_components(self) -> None:
        self.registry.register('engine', self, 'core')
        self.registry.register('events', self.events, 'core')
        self.registry.register('player', self.player, 'world')
        self.registry.register('raycaster', self.raycaster, 'world')
        self.registry.register('lighting', self.lighting, 'render')
        self.registry.register('render_pipeline', self.render_pipeline, 'render')
        self.registry.register('input_system', self.input_system, 'input')
        self.registry.register('mouse', self.mouse, 'input')
        self.registry.register('output', self.output, 'platform')
        self.registry.register('hud', self.hud, 'ui')
        self.registry.register('world_manager', self.world_manager, 'world')
        self.registry.register('entity_manager', self.entity_manager, 'world')
        self.registry.register('camera', self.camera, 'world')
        self.registry.register('tweens', self.tweens, 'core')
        self.registry.register('audio', self.audio, 'core')
        self.registry.register('triggers', self.triggers, 'world')

    def _setup_event_bridge(self) -> None:
        self.events.subscribe(EventType.PLAYER_MOVED, self._on_player_moved)
        self.events.subscribe(EventType.GAME_STATE_CHANGE, self._on_state_change)

    def _on_player_moved(self, data) -> None:
        pass

    def _on_state_change(self, data) -> None:
        if data:
            _logger.info('游戏状态变更: %s -> %s',
                         data.get('from', '?'), data.get('to', '?'))

    # ========================================================================
    # 程序接口
    # ========================================================================

    def set_program(self, program) -> None:
        """!@brief 设置游戏程序

        @param program 实现了 on_setup(engine) 和 get_states() 的程序对象
        """
        self._program = program
        program.on_setup(self)

    # ========================================================================
    # 插件
    # ========================================================================

    def load_plugin(self, plugin) -> bool:
        if not self.plugin_manager.get_plugin(plugin.name):
            if not self.plugin_manager.register(plugin):
                return False
        return self.plugin_manager.load(plugin.name)

    # ========================================================================
    # 主循环
    # ========================================================================

    def run(self):
        """!@brief 游戏主循环"""
        if not self._program:
            _logger.error('未设置游戏程序，无法运行')
            return

        sys.stdout.write('\033[?25l\033[2J')
        sys.stdout.flush()
        self._running = True
        gc.disable()
        try:
            while self._running:
                frame_start = time.perf_counter()
                self.events.publish(EventType.GAME_FRAME_BEGIN)

                self.render_pipeline.resize()
                clicked = self.mouse.poll_click()

                if not self.states.update(clicked):
                    break

                gc.collect(0)
                sys.stdout.flush()
                elapsed = time.perf_counter() - frame_start
                self._delta_time = elapsed
                sleep_time = self._frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                self._update_fps(elapsed)
                self.events.publish(EventType.GAME_FRAME_END, {
                    'delta_time': elapsed, 'fps': self._fps})
        finally:
            self._running = False
            gc.enable()
            self.mouse.shutdown()
            self.output.shutdown()
            self.plugin_manager.unload_all()
            _logger.info('游戏退出')
            log_manager.shutdown()
            sys.stdout.write('\033[?25h\033[0m\033[2J\033[H')
            sys.stdout.flush()

    def stop(self) -> None:
        self._running = False

    def _update_fps(self, elapsed):
        self._frame_count += 1
        self._fps_timer += elapsed
        if self._fps_timer >= 0.5:
            self._fps = self._frame_count / self._fps_timer
            self._frame_count = 0
            self._fps_timer = 0.0

    def _render_mode(self):
        if self.output.available():
            return '直接输出(16色)'
        return '真彩色'


class Game(Engine):
    """!@brief 向后兼容的Game类（Engine别名）"""
    pass
