"""!
@file programs/temple_run/temple_run_program.py
@brief 神庙逃亡程序

第三人称俯视固定相机视角，在无限走廊中自动奔跑，
躲避障碍、收集金币、被怪物追赶。
"""

import sys
import math
import random

from core.event_bus import EventType
from world.entity import Entity, Component
from world.sprite import SpriteFrame, SpriteComponent
from world.chunk_map import ChunkMap, CorridorChunkGenerator, MazeAdapter
from core import log_manager

_logger = log_manager.get_logger('programs.temple_run')

_WALL_GOLD = (195, 165, 105)
_WALL_GOLD_DARK = (155, 130, 85)
_FLOOR_STONE = (210, 195, 160)
_FLOOR_STONE_DARK = (190, 175, 140)
_SKY_BLUE = (100, 180, 240)
_COIN_GOLD = (255, 215, 0)
_OBSTACLE_BROWN = (160, 100, 50)
_OBSTACLE_GRAY = (140, 130, 120)
_PLAYER_COLOR = (50, 120, 220)
_PLAYER_DARK = (30, 80, 180)


class ObstacleComponent(Component):
    BARRIER = 'barrier'
    BEAM = 'beam'
    GAP = 'gap'
    PILLAR = 'pillar'

    def __init__(self, obstacle_type: str, lane: str = 'center'):
        super().__init__()
        self.obstacle_type = obstacle_type
        self.lane = lane
        self.passed = False

    def on_attach(self, entity): pass
    def on_detach(self, entity): pass
    def on_update(self, entity, delta_time): pass


class CoinComponent(Component):
    def __init__(self, value: int = 1):
        super().__init__()
        self.value = value
        self.collected = False
        self.bob_phase = random.random() * math.pi * 2

    def on_attach(self, entity): pass
    def on_detach(self, entity): pass

    def on_update(self, entity, delta_time):
        self.bob_phase += 3.0 * delta_time


class AutoRunSystem:
    def __init__(self, player, maze_adapter):
        self.player = player
        self.maze = maze_adapter
        self.base_speed = 0.08
        self.speed_increment = 0.002
        self.current_speed = 0.08
        self.max_speed = 0.20
        self.running_time = 0.0
        self.is_running = False
        self.turn_cooldown = 0
        self.look_dist = 1.5

    def start(self):
        self.is_running = True
        self.running_time = 0.0
        self.current_speed = self.base_speed

    def stop(self):
        self.is_running = False

    def update(self, delta_time):
        if not self.is_running:
            return
        self.running_time += delta_time
        self.current_speed = min(self.max_speed,
                                  self.base_speed + self.speed_increment * self.running_time)
        if self.turn_cooldown > 0:
            self.turn_cooldown -= 1
        self.player.move_forward(self.maze, self.current_speed)
        self._auto_navigate()

    def _auto_navigate(self):
        if self.turn_cooldown > 0:
            return
        px, py = self.player.x, self.player.y
        dx, dy = self.player.dir_vector
        if not self.maze.is_wall(px + dx * self.look_dist, py + dy * self.look_dist):
            return
        left_dx, left_dy = -dy, dx
        right_dx, right_dy = dy, -dx
        left_open = not self.maze.is_wall(px + left_dx * self.look_dist,
                                           py + left_dy * self.look_dist)
        right_open = not self.maze.is_wall(px + right_dx * self.look_dist,
                                            py + right_dy * self.look_dist)
        if left_open and not right_open:
            self._turn_left()
        elif right_open and not left_open:
            self._turn_right()
        elif left_open and right_open:
            pass
        else:
            self._turn_around()

    def handle_turn_input(self, turn_left: bool):
        if self.turn_cooldown > 0:
            return
        if turn_left:
            self._turn_left()
        else:
            self._turn_right()

    def _turn_left(self):
        self.player.rotate(-math.pi / 2)
        self.turn_cooldown = 10

    def _turn_right(self):
        self.player.rotate(math.pi / 2)
        self.turn_cooldown = 10

    def _turn_around(self):
        self.player.rotate(math.pi)
        self.turn_cooldown = 15


class JumpSlideSystem:
    def __init__(self):
        self.is_jumping = False
        self.is_sliding = False
        self.jump_height = 0.0
        self.jump_duration = 20
        self.slide_duration = 25
        self.jump_frame = 0
        self.slide_frame = 0

    def jump(self):
        if not self.is_jumping and not self.is_sliding:
            self.is_jumping = True
            self.jump_frame = 0

    def slide(self):
        if not self.is_jumping and not self.is_sliding:
            self.is_sliding = True
            self.slide_frame = 0

    def update(self):
        if self.is_jumping:
            self.jump_frame += 1
            t = self.jump_frame / self.jump_duration
            self.jump_height = 4 * t * (1 - t)
            if self.jump_frame >= self.jump_duration:
                self.is_jumping = False
                self.jump_height = 0.0
        if self.is_sliding:
            self.slide_frame += 1
            if self.slide_frame >= self.slide_duration:
                self.is_sliding = False

    def is_avoiding(self, obstacle_type: str) -> bool:
        if obstacle_type in (ObstacleComponent.BARRIER, ObstacleComponent.GAP):
            return self.is_jumping
        elif obstacle_type == ObstacleComponent.BEAM:
            return self.is_sliding
        return False


class ObstacleSpawner:
    def __init__(self, entity_manager, player):
        self._manager = entity_manager
        self._player = player
        self.spawn_distance = 12.0
        self.min_spacing = 6.0
        self._last_spawn_dist = 0.0
        self._counter = 0
        self.difficulty = 1.0

    def update(self, delta_time):
        self.difficulty += 0.01 * delta_time
        current_dist = self._player_distance()
        if current_dist - self._last_spawn_dist > self.min_spacing / self.difficulty:
            self._spawn_obstacle()
            self._last_spawn_dist = current_dist

    def _spawn_obstacle(self):
        dx, dy = self._player.dir_vector
        sx = self._player.x + dx * self.spawn_distance
        sy = self._player.y + dy * self.spawn_distance
        otype = random.choice([ObstacleComponent.BARRIER, ObstacleComponent.BEAM,
                                ObstacleComponent.GAP, ObstacleComponent.PILLAR])
        self._counter += 1
        entity = Entity(f'obs_{self._counter}', sx, sy, self._player.angle)
        entity.attach(ObstacleComponent(otype))
        entity.add_tag('obstacle')
        color_map = {
            ObstacleComponent.BARRIER: (180, 120, 60),
            ObstacleComponent.BEAM: (140, 100, 50),
            ObstacleComponent.GAP: (40, 30, 20),
            ObstacleComponent.PILLAR: (160, 140, 100),
        }
        frame = SpriteFrame.from_color(4, 4, color_map.get(otype, (150, 150, 150)))
        entity.attach(SpriteComponent(frame, visible_distance=13.0))
        self._manager.add(entity, 'obstacles')

    def _player_distance(self):
        return math.sqrt(self._player.x ** 2 + self._player.y ** 2)


class CoinSpawner:
    def __init__(self, entity_manager, player):
        self._manager = entity_manager
        self._player = player
        self.coins_collected = 0
        self._counter = 0
        self.spawn_distance = 10.0
        self._last_spawn_dist = 0.0
        self.min_spacing = 4.0

    def update(self, delta_time):
        current_dist = self._player_distance()
        if current_dist - self._last_spawn_dist > self.min_spacing:
            self._spawn_coins()
            self._last_spawn_dist = current_dist
        self._check_collection()

    def _spawn_coins(self):
        dx, dy = self._player.dir_vector
        for i in range(3):
            offset = self.spawn_distance + i * 2
            self._counter += 1
            entity = Entity(f'coin_{self._counter}',
                            self._player.x + dx * offset,
                            self._player.y + dy * offset, 0)
            entity.attach(CoinComponent(value=1))
            entity.add_tag('coin')
            frame = SpriteFrame.from_color(3, 3, (255, 215, 0), 'diamond')
            sprite = SpriteComponent(frame, visible_distance=13.0)
            sprite.bob_amplitude = 0.05
            sprite.bob_speed = 3.0
            entity.attach(sprite)
            self._manager.add(entity, 'coins')

    def _check_collection(self):
        px, py = self._player.x, self._player.y
        nearby = self._manager.query_radius(px, py, 0.6)
        for entity in nearby:
            if not entity.has_tag('coin'):
                continue
            comp = entity.get_component('CoinComponent')
            if comp and not comp.collected:
                comp.collected = True
                self.coins_collected += comp.value
                self._manager.remove(entity.id)

    def _player_distance(self):
        return math.sqrt(self._player.x ** 2 + self._player.y ** 2)


class MonsterSystem:
    def __init__(self, player):
        self.player = player
        self.monster_distance = 20.0
        self.min_distance = 1.0
        self.approach_speed = 0.02
        self.is_active = False

    def activate(self):
        self.is_active = True
        self.monster_distance = 20.0

    def update(self, delta_time):
        if not self.is_active:
            return
        self.monster_distance -= self.approach_speed
        self.monster_distance = max(self.min_distance, self.monster_distance)

    def retreat(self, amount=2.0):
        self.monster_distance = min(30.0, self.monster_distance + amount)

    def on_obstacle_hit(self):
        self.monster_distance -= 5.0

    @property
    def caught(self):
        return self.is_active and self.monster_distance <= self.min_distance


class ScoringSystem:
    def __init__(self, player, coin_spawner):
        self.player = player
        self.coins = coin_spawner
        self.score = 0
        self.distance = 0.0
        self.start_x = 0.0
        self.start_y = 0.0

    def start(self):
        self.score = 0
        self.distance = 0.0
        self.start_x = self.player.x
        self.start_y = self.player.y

    def update(self, delta_time):
        self.distance = math.sqrt(
            (self.player.x - self.start_x) ** 2 +
            (self.player.y - self.start_y) ** 2)
        self.score = int(self.distance * 10) + self.coins.coins_collected * 50

    @property
    def formatted_distance(self):
        return f'{self.distance:.0f}m'

    @property
    def formatted_score(self):
        return f'{self.score:,}'


def _pack(r, g, b):
    return (r << 16) | (g << 8) | b


class ThirdPersonRenderer:
    """!@brief 第三人称俯视渲染层

    从玩家后上方俯视，玩家角色在画面下方，走廊向上延伸。
    使用cell级渲染，每行只查询可见cell数的is_wall，避免逐像素查询。
    """

    def __init__(self, player, maze_adapter, entity_manager,
                 jump_slide, monster, scoring, coin_spawner):
        self._player = player
        self._maze = maze_adapter
        self._em = entity_manager
        self._jump_slide = jump_slide
        self._monster = monster
        self._scoring = scoring
        self._coin_spawner = coin_spawner
        self._max_depth = 14.0
        self._fov_half = 4.5

    def on_render(self, context):
        buffer = context['buffer']
        w = buffer.width
        h = buffer.pixel_height
        px, py = self._player.x, self._player.y
        dx, dy = self._player.dir_vector
        perp_x, perp_y = -dy, dx

        sky_pack = _pack(*_SKY_BLUE)
        for row in range(h):
            buffer.data[row][:] = [sky_pack] * w

        self._render_corridor(buffer, w, h, px, py, dx, dy, perp_x, perp_y)
        self._render_entities(buffer, w, h, px, py, dx, dy, perp_x, perp_y)
        self._render_player(buffer, w, h)
        self._render_monster_indicator(buffer, w, h)

    def _render_corridor(self, buffer, w, h, px, py, dx, dy, perp_x, perp_y):
        max_d = self._max_depth
        fov_h = self._fov_half
        maze = self._maze

        for row in range(h):
            row_t = 1.0 - row / h
            if row_t < 0.02:
                row_t = 0.02
            depth = 0.5 + (max_d - 0.5) * row_t * row_t

            half_w = fov_h * depth / max_d
            fog = max(0.35, 1.0 - (depth - 0.5) / (max_d - 0.5) * 0.65)

            cx = px + dx * depth
            cy = py + dy * depth

            steps = max(3, int(half_w * 2.5))
            inv_steps = 1.0 / steps

            lx = cx - perp_x * half_w
            ly = cy - perp_y * half_w
            rx = cx + perp_x * half_w
            ry = cy + perp_y * half_w
            drx = (rx - lx) * inv_steps
            dry = (ry - ly) * inv_steps

            wx = lx
            wy = ly
            for i in range(steps):
                col_start = int(w * i * inv_steps)
                col_end = int(w * (i + 1) * inv_steps)
                if col_end <= col_start:
                    col_end = col_start + 1

                is_wall = maze.is_wall(wx, wy)
                ix_i = int(wx)
                iy_i = int(wy)

                if is_wall:
                    base = _WALL_GOLD if (ix_i + iy_i) % 2 == 0 else _WALL_GOLD_DARK
                else:
                    base = _FLOOR_STONE if (ix_i + iy_i) % 2 == 0 else _FLOOR_STONE_DARK

                r = int(base[0] * fog)
                g = int(base[1] * fog)
                b = int(base[2] * fog)
                packed = _pack(r, g, b)

                span = col_end - col_start
                buffer.data[row][col_start:col_end] = [packed] * span

                wx += drx
                wy += dry

    def _render_entities(self, buffer, w, h, px, py, dx, dy, perp_x, perp_y):
        max_d = self._max_depth
        fov_h = self._fov_half

        entities = self._em.query().with_tag('coin').execute()
        entities += self._em.query().with_tag('obstacle').execute()

        for entity in entities:
            rel_x = entity.x - px
            rel_y = entity.y - py
            forward = rel_x * dx + rel_y * dy
            lateral = rel_x * perp_x + rel_y * perp_y

            if forward < 0.5 or forward > max_d:
                continue

            depth = forward
            half_w = fov_h * depth / max_d
            if abs(lateral) > half_w:
                continue

            screen_col = int(w * 0.5 * (1.0 + lateral / half_w))
            screen_row = int(h * (1.0 - math.sqrt((depth - 0.5) / (max_d - 0.5))))

            if entity.has_tag('coin'):
                comp = entity.get_component('CoinComponent')
                if comp and comp.collected:
                    continue
                size = max(1, int(3.0 / depth))
                color = _COIN_GOLD
            elif entity.has_tag('obstacle'):
                obs = entity.get_component('ObstacleComponent')
                if obs and obs.passed:
                    continue
                size = max(2, int(5.0 / depth))
                color = _OBSTACLE_BROWN if obs and obs.obstacle_type != ObstacleComponent.PILLAR else _OBSTACLE_GRAY
            else:
                continue

            packed = _pack(*color)
            y0 = max(0, screen_row - size)
            y1 = min(h, screen_row + size + 1)
            x0 = max(0, screen_col - size)
            x1 = min(w, screen_col + size + 1)
            for y in range(y0, y1):
                buffer.data[y][x0:x1] = [packed] * (x1 - x0)

    def _render_player(self, buffer, w, h):
        player_row = int(h * 0.78)
        player_col = w // 2

        jump_offset = 0
        if self._jump_slide.is_jumping:
            jump_offset = -int(self._jump_slide.jump_height * 8)
        slide = self._jump_slide.is_sliding

        body_h = 3 if slide else 6
        body_w = 5 if slide else 4
        head_r = 1 if slide else 2

        packed_body = _pack(*_PLAYER_COLOR)
        packed_head = _pack(*_PLAYER_DARK)

        start_row = player_row - body_h + jump_offset
        y0 = max(0, start_row)
        y1 = min(h, start_row + body_h)
        x0 = max(0, player_col - body_w // 2)
        x1 = min(w, player_col + body_w // 2 + 1)
        span = x1 - x0
        row_data = [packed_body] * span
        for y in range(y0, y1):
            buffer.data[y][x0:x1] = row_data

        head_start = start_row - head_r * 2
        hy0 = max(0, head_start)
        hy1 = min(h, head_start + head_r * 2)
        hx0 = max(0, player_col - head_r)
        hx1 = min(w, player_col + head_r + 1)
        hspan = hx1 - hx0
        hrow = [packed_head] * hspan
        for y in range(hy0, hy1):
            buffer.data[y][hx0:hx1] = hrow

        shadow_row = player_row + 1
        if 0 <= shadow_row < h:
            for x in range(max(0, player_col - 3), min(w, player_col + 4)):
                cur = buffer.data[shadow_row][x]
                cr = max(0, ((cur >> 16) & 0xFF) - 40)
                cg = max(0, ((cur >> 8) & 0xFF) - 40)
                cb = max(0, (cur & 0xFF) - 40)
                buffer.data[shadow_row][x] = _pack(cr, cg, cb)

    def _render_monster_indicator(self, buffer, w, h):
        if not self._monster.is_active:
            return
        dist = self._monster.monster_distance
        if dist < 3:
            color = (255, 40, 40)
        elif dist < 8:
            color = (255, 160, 40)
        elif dist < 15:
            color = (255, 220, 80)
        else:
            return

        packed = _pack(*color)
        bar_w = min(w - 4, 20)
        bar_x = w // 2 - bar_w // 2
        bar_y = h - 4
        if 0 <= bar_y < buffer.pixel_height:
            buffer.data[bar_y][bar_x:bar_x + bar_w] = [packed] * bar_w


class TempleRunProgram:
    """!@brief 神庙逃亡游戏程序"""

    def __init__(self, seed=42):
        self.seed = seed

    def on_setup(self, engine) -> None:
        self._engine = engine

        self.chunk_map = ChunkMap(seed=self.seed, generator=CorridorChunkGenerator())
        self.maze_adapter = MazeAdapter(self.chunk_map)

        engine.player.x = self.chunk_map.start[0]
        engine.player.y = self.chunk_map.start[1]
        engine.player.angle = 0.0
        engine.player.set_collision_fn(self.maze_adapter.is_wall)

        engine.raycaster.maze = self.maze_adapter
        engine.render_pipeline.maze = self.maze_adapter
        engine.render_pipeline.scene.maze = self.maze_adapter

        engine.lighting.override_wall_color(1, _WALL_GOLD)

        self.auto_run = AutoRunSystem(engine.player, self.maze_adapter)
        self.jump_slide = JumpSlideSystem()
        self.obstacle_spawner = ObstacleSpawner(engine.entity_manager, engine.player)
        self.coin_spawner = CoinSpawner(engine.entity_manager, engine.player)
        self.monster = MonsterSystem(engine.player)
        self.scoring = ScoringSystem(engine.player, self.coin_spawner)

        self._third_person = ThirdPersonRenderer(
            engine.player, self.maze_adapter, engine.entity_manager,
            self.jump_slide, self.monster, self.scoring, self.coin_spawner
        )
        engine.render_pipeline.add_layer('third_person', self._third_person, priority=-100)

        engine.api.bind_action('turn_left', self._on_turn_left)
        engine.api.bind_action('turn_right', self._on_turn_right)
        engine.api.bind_action('jump', self._on_jump)
        engine.api.bind_action('slide', self._on_slide)

        engine.hud.add_provider('temple_score', self._score_hud, priority=0)
        engine.hud.add_provider('temple_danger', self._danger_hud, priority=1)

        engine.states.add_state('start', self._handle_start)
        engine.states.add_state('playing', self._handle_playing)
        engine.states.add_state('paused', self._handle_paused)
        engine.states.add_state('game_over', self._handle_game_over)

        engine.states.on_enter('playing', self._on_enter_playing)
        engine.states.on_exit('playing', self._on_exit_playing)

        engine.states.start('start')

        _logger.info('神庙逃亡程序已安装')

    def _on_enter_playing(self, from_state) -> None:
        if from_state == 'start':
            self._engine.events.publish(EventType.GAME_START)
            self.auto_run.start()
            self.monster.activate()
            self.scoring.start()
        else:
            self._engine.events.publish(EventType.GAME_RESUME)

    def _on_exit_playing(self, to_state) -> None:
        if to_state == 'paused':
            self._engine.events.publish(EventType.GAME_PAUSE)

    def _handle_start(self, clicked=None):
        msg = ('神庙逃亡 - Temple Run\n\n'
               '操作:\n'
               '  A/← 左转  D/→ 右转\n'
               '  W/↑ 跳跃  S/↓ 滑行\n'
               '  ESC 暂停\n\n'
               '躲避障碍，收集金币，跑得越远越好！\n\n'
               '按任意键开始')
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
            engine.states.transition('paused')
            return True

        if actions.get('turn_left'):
            self.auto_run.handle_turn_input(turn_left=True)
        if actions.get('turn_right'):
            self.auto_run.handle_turn_input(turn_left=False)
        if actions.get('jump') or actions.get('forward'):
            self.jump_slide.jump()
        if actions.get('slide') or actions.get('backward'):
            self.jump_slide.slide()

        self.auto_run.update(engine.delta_time)
        self.jump_slide.update()
        self.obstacle_spawner.update(engine.delta_time)
        self.coin_spawner.update(engine.delta_time)
        self.monster.update(engine.delta_time)
        self.scoring.update(engine.delta_time)

        if self.monster.caught:
            engine.states.transition('game_over')
            return True

        self._check_obstacle_collision()

        self.chunk_map.update_player_position(engine.player.x, engine.player.y)
        engine.camera.update(engine.delta_time)
        engine.tweens.update(engine.delta_time)
        engine.triggers.update(engine.player.x, engine.player.y, engine.delta_time)
        engine.entity_manager.update_all(engine.delta_time)

        dir_x, dir_y = engine.player.dir_vector
        plane_x, plane_y = engine.player.plane_vector
        hits = engine.raycaster.cast(engine.player.x, engine.player.y,
                                      dir_x, dir_y, plane_x, plane_y,
                                      engine.render_pipeline.width)
        engine.render_pipeline.render_scene(hits, engine.player, engine.camera)

        hud = engine.hud.build(engine.player, False, engine.fps,
                                engine._render_mode(), engine.render_pipeline.width)

        if engine.output.available():
            engine.output.write_frame(
                engine.render_pipeline.buffer.data, engine.render_pipeline.width,
                engine.render_pipeline.height, hud)
        else:
            sys.stdout.buffer.write(engine.render_pipeline.render_to_bytes(hud))
        return True

    def _handle_paused(self, clicked=None):
        msg = ('游戏暂停\n\n按任意键继续, ESC退出')
        sys.stdout.write('\033[H' + self._engine.render_pipeline.render_message(msg))
        sys.stdout.flush()
        if self._engine.input_system.wait_key():
            return False
        self._engine.states.transition('playing')
        sys.stdout.write('\033[2J')
        return True

    def _handle_game_over(self, clicked=None):
        msg = ('游戏结束!\n\n'
               f'  距离: {self.scoring.formatted_distance}\n'
               f'  金币: {self.coin_spawner.coins_collected}\n'
               f'  分数: {self.scoring.formatted_score}\n\n'
               '按任意键重新开始, ESC退出')
        sys.stdout.write('\033[H' + self._engine.render_pipeline.render_message(msg))
        sys.stdout.flush()
        if self._engine.input_system.wait_key():
            return False
        self._engine.entity_manager.clear()
        self.auto_run.stop()
        self._engine.states.transition('start')
        return True

    def _check_obstacle_collision(self):
        engine = self._engine
        px, py = engine.player.x, engine.player.y
        nearby = engine.entity_manager.query_radius(px, py, 0.6)
        for entity in nearby:
            if not entity.has_tag('obstacle'):
                continue
            comp = entity.get_component('ObstacleComponent')
            if not comp or comp.passed:
                continue
            if self.jump_slide.is_avoiding(comp.obstacle_type):
                comp.passed = True
                self.monster.retreat(1.0)
            else:
                comp.passed = True
                self.monster.on_obstacle_hit()
                engine.camera.trigger_shake(0.08, 0.2)

    def _on_turn_left(self, pressed):
        if pressed:
            self.auto_run.handle_turn_input(turn_left=True)

    def _on_turn_right(self, pressed):
        if pressed:
            self.auto_run.handle_turn_input(turn_left=False)

    def _on_jump(self, pressed):
        if pressed:
            self.jump_slide.jump()

    def _on_slide(self, pressed):
        if pressed:
            self.jump_slide.slide()

    def _score_hud(self) -> str:
        return (f'  分数:{self.scoring.formatted_score}  '
                f'金币:{self.coin_spawner.coins_collected}  '
                f'距离:{self.scoring.formatted_distance}')

    def _danger_hud(self) -> str:
        if not self.monster.is_active:
            return ''
        dist = self.monster.monster_distance
        if dist < 3:
            return '  !!! 危险 !!!'
        elif dist < 8:
            return '  !! 注意 !!'
        elif dist < 15:
            return '  ! 警告 !'
        return ''
