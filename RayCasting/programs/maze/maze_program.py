"""!
@file programs/maze/maze_program.py
@brief 迷宫程序

3D迷宫游戏：在随机生成的迷宫中找到绿色出口即可获胜。
"""

import sys
import math

import config
from core.event_bus import EventType
from core.hud import HUD
from world.maze import Maze
from world.player import Player
from world.raycaster import Raycaster
from render.pipeline import RenderPipeline
from plugins.minimap_plugin import MinimapPlugin
from core import log_manager

_logger = log_manager.get_logger('programs.maze')


class MazeProgram:
    """!@brief 迷宫游戏程序"""

    def __init__(self, seed=None):
        self.seed = seed
        self.maze = None
        self._paused_mouse_enabled = False

    def on_setup(self, engine) -> None:
        """!@brief 程序安装：配置引擎、注册状态"""
        self._engine = engine

        # 创建迷宫世界
        self.maze = Maze(seed=self.seed)
        engine.player.x = self.maze.start[0]
        engine.player.y = self.maze.start[1]
        engine.player.angle = 0.0
        engine.player.set_collision_fn(self.maze.is_wall)

        engine.raycaster.maze = self.maze
        engine.render_pipeline.maze = self.maze
        engine.render_pipeline.scene.maze = self.maze

        # 注册迷宫到registry
        engine.registry.register('maze', self.maze, 'world')

        # 加载小地图插件
        engine.load_plugin(MinimapPlugin())

        # 注册HUD
        engine.hud.add_provider('maze_default',
            HUD.default_provider(engine.player, False, 0.0, '真彩色'),
            priority=0)

        # 注册游戏状态
        engine.states.add_state('start', self._handle_start)
        engine.states.add_state('playing', self._handle_playing)
        engine.states.add_state('paused', self._handle_paused)
        engine.states.add_state('won', self._handle_won)

        engine.states.on_enter('playing', self._on_enter_playing)
        engine.states.on_exit('playing', self._on_exit_playing)

        engine.states.start('start')

        _logger.info('迷宫程序已安装')

    def _on_enter_playing(self, from_state) -> None:
        self._engine.events.publish(EventType.GAME_START if from_state == 'start'
                                    else EventType.GAME_RESUME)

    def _on_exit_playing(self, to_state) -> None:
        if to_state == 'paused':
            self._engine.events.publish(EventType.GAME_PAUSE)

    def _handle_start(self, clicked=None):
        msg = ('3D 迷宫 - RayCasting\n\n'
               '操作说明:\n'
               '  W/↑ 前进  S/↓ 后退  A 左移  D 右移\n'
               '  ← 左转  → 右转\n'
               '  Shift 疾跑\n'
               '  鼠标左键 锁定/解锁鼠标视角\n'
               '  ESC 暂停\n\n'
               '目标: 找到绿色出口即可获胜\n\n'
               '按任意键开始, ESC退出')
        sys.stdout.write('\033[H' + self._engine.render_pipeline.render_message(msg))
        sys.stdout.flush()
        if self._engine.input_system.wait_key():
            return False
        self._engine.states.transition('playing')
        sys.stdout.write('\033[2J')
        return True

    def _handle_playing(self, clicked=False):
        engine = self._engine
        actions = engine.input_system.poll()
        engine.input_system.process_actions(actions)

        if actions['quit']:
            self._paused_mouse_enabled = engine.mouse.enabled
            engine.mouse.disable()
            engine.states.transition('paused')
            return True

        if clicked:
            engine.mouse.toggle()

        rotate_delta, pitch_delta = engine.mouse.update_motion()
        if rotate_delta:
            engine.player.rotate(rotate_delta)
        if pitch_delta:
            engine.player.adjust_pitch(pitch_delta)

        speed = engine.settings.get('gameplay', 'move_speed', config.MOVE_SPEED)
        if actions['sprint']:
            speed *= engine.settings.get('gameplay', 'sprint_multiplier',
                                         config.SPRINT_MULTIPLIER)

        if actions['forward']:
            engine.player.move_forward(self.maze, speed)
        if actions['backward']:
            engine.player.move_forward(self.maze, -speed)
        if actions['turn_left']:
            engine.player.rotate(-config.ROTATE_SPEED)
        if actions['turn_right']:
            engine.player.rotate(config.ROTATE_SPEED)
        if actions['strafe_left']:
            engine.player.strafe(self.maze, -speed)
        if actions['strafe_right']:
            engine.player.strafe(self.maze, speed)

        if self.maze.is_exit(engine.player.x, engine.player.y):
            engine.events.publish(EventType.GAME_EXIT_REACHED, {
                'x': engine.player.x, 'y': engine.player.y})
            engine.states.transition('won')
            engine.mouse.disable()
            return True

        # 引擎通用更新
        engine.camera.update(engine.delta_time)
        engine.tweens.update(engine.delta_time)
        engine.entity_manager.update_all(engine.delta_time)

        dir_x, dir_y = engine.player.dir_vector
        plane_x, plane_y = engine.player.plane_vector
        hits = engine.raycaster.cast(engine.player.x, engine.player.y,
                                      dir_x, dir_y, plane_x, plane_y,
                                      engine.render_pipeline.width)
        engine.render_pipeline.render_scene(hits, engine.player, engine.camera)

        hud = engine.hud.build(engine.player, engine.mouse.enabled, engine.fps,
                                engine._render_mode(), engine.render_pipeline.width)

        if engine.output.available():
            engine.output.write_frame(
                engine.render_pipeline.buffer.data, engine.render_pipeline.width,
                engine.render_pipeline.height, hud)
        else:
            sys.stdout.buffer.write(engine.render_pipeline.render_to_bytes(hud))
        return True

    def _handle_paused(self, clicked=None):
        msg = ('游戏暂停\n\n'
               '按任意键继续, ESC退出')
        sys.stdout.write('\033[H' + self._engine.render_pipeline.render_message(msg))
        sys.stdout.flush()
        if self._engine.input_system.wait_key():
            return False
        self._engine.states.transition('playing')
        if self._paused_mouse_enabled:
            self._engine.mouse.enable()
        sys.stdout.write('\033[2J')
        return True

    def _handle_won(self, clicked=None):
        msg = ('恭喜! 你成功逃出了迷宫!\n\n'
               '按 ESC 退出')
        sys.stdout.write('\033[H' + self._engine.render_pipeline.render_message(msg))
        sys.stdout.flush()
        while not self._engine.input_system.wait_key():
            pass
        return False
