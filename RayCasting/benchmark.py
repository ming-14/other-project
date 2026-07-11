"""!
@file benchmark.py
@brief 渲染管线性能基准测试（输出到日志文件）

测试不同RENDER_STRATEGY下各操作的开销，包含：
  - 环境信息（Python/OS/CPU/内存）
  - 多分辨率测试
  - 稳定性分析（均值/标准差/最小/最大/P50/P95/P99）
  - 各策略流水线耗时占比
  - 微基准扩展（光照/缓冲区/量化/事件总线/状态机/HUD/迷宫/玩家）
  - 内存占用统计
  - 配置快照
  - 结果汇总表
结果写入benchmark_log.txt。
"""

import time
import sys
import os
import math
import shutil
import ctypes
import logging
import statistics
import struct
import tracemalloc
from collections import OrderedDict

_script_dir = os.path.dirname(os.path.abspath(__file__))
for _i, _p in enumerate(sys.path):
    if os.path.abspath(_p) == _script_dir:
        sys.path.pop(_i)
        break
import platform as _stdlib_platform
_stdlib_platform_data = {
    'python_version': _stdlib_platform.python_version,
    'python_implementation': _stdlib_platform.python_implementation,
    'system': _stdlib_platform.system,
    'version': _stdlib_platform.version,
    'platform': _stdlib_platform.platform,
    'machine': _stdlib_platform.machine,
    'processor': _stdlib_platform.processor,
}
del sys.modules['platform']
del _stdlib_platform
sys.path.insert(0, _script_dir)

import config
from world.maze import Maze
from world.player import Player
from world.raycaster import Raycaster
from render.pipeline import RenderPipeline
from render.lighting import Lighting
from render.buffer import PixelBuffer
from render.scene_builder import SceneBuilder
from render.minimap import MinimapRenderer
from core.hud import HUD
from core.event_bus import EventBus, EventType
from core.state_machine import StateMachine

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'benchmark_log.txt')

_results = []
_summary_rows = []

WARMUP_ITER = 10


def log(msg=""):
    _results.append(msg)
    print(msg)


def time_detailed(func, iterations=100, label="", warmup=WARMUP_ITER):
    """!@brief 详细计时，返回统计信息字典"""
    for _ in range(min(warmup, iterations // 5)):
        func()
    samples = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        func()
        samples.append(time.perf_counter() - t0)
    elapsed_total = sum(samples)
    avg_us = elapsed_total / iterations * 1_000_000
    fps = iterations / elapsed_total if elapsed_total > 0 else 0
    stdev_us = statistics.stdev(samples) * 1_000_000 if iterations > 1 else 0.0
    min_us = min(samples) * 1_000_000
    max_us = max(samples) * 1_000_000
    sorted_s = sorted(samples)
    p50_us = sorted_s[len(sorted_s) // 2] * 1_000_000
    p95_us = sorted_s[int(len(sorted_s) * 0.95)] * 1_000_000
    p99_us = sorted_s[int(len(sorted_s) * 0.99)] * 1_000_000
    line = "  %-40s  %8.1f us ±%5.1f  %6.1f FPS  [%5.1f..%5.1f] P95=%5.1f" % (
        label, avg_us, stdev_us, fps, min_us, max_us, p95_us)
    log(line)
    return {
        'label': label, 'avg_us': avg_us, 'stdev_us': stdev_us,
        'min_us': min_us, 'max_us': max_us, 'p50_us': p50_us,
        'p95_us': p95_us, 'p99_us': p99_us, 'fps': fps,
        'iterations': iterations, 'total_us': elapsed_total * 1_000_000,
    }


def time_it(func, iterations=100, label="", warmup=WARMUP_ITER):
    """!@brief 简洁计时接口，兼容旧调用"""
    return time_detailed(func, iterations, label, warmup)


def apply_strategy(strategy, quantize_bits=4):
    config.RENDER_STRATEGY = strategy
    config.COLOR_QUANTIZE_ENABLED = (strategy == 'quantize')
    config.BYPASS_ANSI_ENABLED = (strategy == 'bypass_ansi')
    config.COLOR_QUANTIZE_BITS = quantize_bits


def save_strategy():
    return (config.RENDER_STRATEGY, config.COLOR_QUANTIZE_ENABLED,
            config.COLOR_QUANTIZE_BITS, config.BYPASS_ANSI_ENABLED)


def restore_strategy(saved):
    config.RENDER_STRATEGY, config.COLOR_QUANTIZE_ENABLED, \
        config.COLOR_QUANTIZE_BITS, config.BYPASS_ANSI_ENABLED = saved


def get_env_info():
    """!@brief 收集运行环境信息"""
    info = OrderedDict()
    info['Python版本'] = _stdlib_platform_data['python_version']()
    info['Python实现'] = _stdlib_platform_data['python_implementation']()
    info['Python路径'] = sys.executable
    info['操作系统'] = _stdlib_platform_data['system']()
    info['OS版本'] = _stdlib_platform_data['version']()
    info['平台'] = _stdlib_platform_data['platform']()
    info['架构'] = _stdlib_platform_data['machine']()
    info['处理器'] = _stdlib_platform_data['processor']() or 'N/A'
    info['CPU核心数'] = os.cpu_count() or 'N/A'
    ts = shutil.get_terminal_size()
    info['终端尺寸'] = '%d x %d' % (ts.columns, ts.lines)
    try:
        is_cmd = bool(ctypes.windll.kernel32.GetConsoleWindow())
        info['终端类型'] = 'cmd (conhost)' if is_cmd else 'Windows Terminal / pwsh'
    except Exception:
        info['终端类型'] = '未知'
    info['指针宽度'] = '%d bit' % (struct.calcsize('P') * 8)
    info['字节序'] = sys.byteorder
    info['时间'] = time.strftime('%Y-%m-%d %H:%M:%S')
    try:
        import psutil
        mem = psutil.virtual_memory()
        info['物理内存'] = '%.1f GB (可用 %.1f GB)' % (mem.total / 1e9, mem.available / 1e9)
        cpu_freq = psutil.cpu_freq()
        if cpu_freq:
            info['CPU频率'] = '%.0f MHz' % cpu_freq.current
    except ImportError:
        pass
    return info


def print_config_snapshot():
    """!@brief 输出当前配置快照"""
    log("  配置快照:")
    cfg_items = [
        ('MAZE_WIDTH', config.MAZE_WIDTH), ('MAZE_HEIGHT', config.MAZE_HEIGHT),
        ('FOV', '%.1f°' % math.degrees(config.FOV)),
        ('MOVE_SPEED', config.MOVE_SPEED), ('ROTATE_SPEED', config.ROTATE_SPEED),
        ('TARGET_FPS', config.TARGET_FPS),
        ('RENDER_STRATEGY', config.RENDER_STRATEGY),
        ('COLOR_QUANTIZE_BITS', config.COLOR_QUANTIZE_BITS),
        ('FOG_NEAR', config.FOG_NEAR), ('FOG_FAR', config.FOG_FAR),
        ('FOG_GAMMA', config.FOG_GAMMA), ('MIN_BRIGHTNESS', config.MIN_BRIGHTNESS),
        ('WALL_SIDE_SHADE', config.WALL_SIDE_SHADE),
        ('WALL_VERTICAL_SHADE', config.WALL_VERTICAL_SHADE),
        ('WALL_STRIPE_PERIOD', config.WALL_STRIPE_PERIOD),
        ('PLAYER_EYE_HEIGHT', config.PLAYER_EYE_HEIGHT),
        ('MOUSE_SENSITIVITY', config.MOUSE_SENSITIVITY),
        ('SPRINT_MULTIPLIER', config.SPRINT_MULTIPLIER),
    ]
    for name, val in cfg_items:
        log("    %-28s = %s" % (name, val))


def measure_memory(func, label=""):
    """!@brief 测量函数执行的峰值内存增量"""
    tracemalloc.start()
    tracemalloc.reset_peak()
    baseline = tracemalloc.get_traced_memory()[0]
    func()
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    delta_kb = (peak - baseline) / 1024
    if label:
        log("  %-40s  %8.1f KB 峰值内存增量" % (label, delta_kb))
    return delta_kb


def run_benchmark():
    env = get_env_info()
    W = shutil.get_terminal_size().columns
    H = shutil.get_terminal_size().lines

    log("=" * 80)
    log("RayCasting 性能基准测试 v2.0")
    log("=" * 80)
    for k, v in env.items():
        log("  %-16s: %s" % (k, v))
    log()
    print_config_snapshot()
    log()

    maze = Maze()
    player = Player(maze.start[0], maze.start[1], 0.0)
    raycaster = Raycaster(maze)
    dir_x, dir_y = player.dir_vector
    plane_x, plane_y = player.plane_vector

    # ========================================================================
    # 阶段1: 迷宫生成与玩家操作
    # ========================================================================
    log("=" * 80)
    log("阶段1: 迷宫生成与玩家操作")
    log("=" * 80)
    time_it(lambda: Maze(), iterations=50, label="Maze() 生成迷宫")
    time_it(lambda: Maze(seed=42), iterations=50, label="Maze(seed=42) 可复现迷宫")

    seeds = [None, 42, 123, 999]
    for s in seeds:
        m = Maze(seed=s)
        log("  seed=%-6s  出口=(%d,%d)  墙壁数=%d" % (
            str(s), m.exit[0], m.exit[1],
            sum(1 for row in m.grid for c in row if c >= 1)))

    time_it(lambda: player.move_forward(maze, config.MOVE_SPEED),
            iterations=5000, label="player.move_forward()")
    time_it(lambda: player.strafe(maze, config.MOVE_SPEED),
            iterations=5000, label="player.strafe()")
    time_it(lambda: player.rotate(config.ROTATE_SPEED),
            iterations=10000, label="player.rotate()")
    time_it(lambda: player.adjust_pitch(0.01),
            iterations=10000, label="player.adjust_pitch()")
    time_it(lambda: player.dir_vector, iterations=10000, label="player.dir_vector")
    time_it(lambda: player.plane_vector, iterations=10000, label="player.plane_vector")
    time_it(lambda: maze.is_wall(player.x, player.y),
            iterations=50000, label="maze.is_wall()")
    time_it(lambda: maze.cell_type(player.x, player.y),
            iterations=50000, label="maze.cell_type()")
    time_it(lambda: maze.is_exit(player.x, player.y),
            iterations=50000, label="maze.is_exit()")
    log()

    # ========================================================================
    # 阶段2: 光线投射
    # ========================================================================
    log("=" * 80)
    log("阶段2: 光线投射 (DDA)")
    log("=" * 80)
    resolutions = [(W, "终端宽度"), (80, "80列"), (120, "120列"), (160, "160列"), (200, "200列")]
    for rw, desc in resolutions:
        time_it(lambda: raycaster.cast(player.x, player.y, dir_x, dir_y,
                                        plane_x, plane_y, rw),
                iterations=200, label="raycaster.cast() %s(%d列)" % (desc, rw))

    hits = raycaster.cast(player.x, player.y, dir_x, dir_y, plane_x, plane_y, W)
    log("  命中结果数: %d, 平均距离: %.2f, 最大距离: %.2f" % (
        len(hits), sum(h.distance for h in hits) / len(hits),
        max(h.distance for h in hits)))

    time_it(lambda: raycaster._cast_single(player.x, player.y, dir_x, dir_y),
            iterations=5000, label="_cast_single() 单条光线")
    log()

    # ========================================================================
    # 阶段3: 各渲染策略完整测试
    # ========================================================================
    strategies = [
        ('ansi',       8, "ansi (真彩色+RLE)"),
        ('quantize',   5, "quantize 5位"),
        ('quantize',   4, "quantize 4位"),
        ('quantize',   3, "quantize 3位"),
        ('bypass_ansi', 8, "bypass_ansi (16色直接输出)"),
    ]

    strategy_summary = OrderedDict()

    for strategy, qbits, desc in strategies:
        log("=" * 80)
        log("阶段3: 策略测试 — %s" % desc)
        log("=" * 80)

        try:
            is_cmd = bool(ctypes.windll.kernel32.GetConsoleWindow())
        except Exception:
            is_cmd = False
        if strategy == 'bypass_ansi' and not is_cmd:
            log("  (跳过: 仅cmd支持)")
            log()
            continue

        saved = save_strategy()
        apply_strategy(strategy, qbits)

        lighting = Lighting()
        pipeline = RenderPipeline(maze, lighting)
        pipeline.buffer.width = W
        pipeline.buffer.height = H
        pipeline.buffer.pixel_height = H * 2
        pipeline.buffer._init()

        r = OrderedDict()
        r['desc'] = desc

        log("  [子操作]")
        r['scene'] = time_it(
            lambda: pipeline.scene.build(pipeline.buffer, hits, player),
            iterations=200, label="scene_builder.build()")

        pipeline.scene.build(pipeline.buffer, hits, player)

        r['minimap'] = time_it(
            lambda: pipeline.minimap.draw(pipeline.buffer, player),
            iterations=200, label="minimap.draw()")

        if strategy != 'bypass_ansi':
            r['render_to_bytes'] = time_it(
                lambda: pipeline.render_to_bytes("HUD测试"),
                iterations=100, label="render_to_bytes() (ANSI编码)")
            data = pipeline.render_to_bytes("HUD测试")
            log("  %-40s  %8d bytes  %5.1f KB" % (
                "ANSI输出数据量", len(data), len(data) / 1024))
            r['output_bytes'] = len(data)

        if strategy == 'bypass_ansi':
            from platform.win32_output import Win32ConsoleOutput
            output = Win32ConsoleOutput()
            if output.available():
                r['write_frame'] = time_it(
                    lambda: output.write_frame(
                        pipeline.buffer.data, W, H, "HUD测试"),
                    iterations=100, label="write_frame() (BYPASS_ANSI)")
            else:
                log("  (BYPASS_ANSI不可用)")

        log("  [完整流水线]")

        def full_scene(p=pipeline, h=hits, pl=player):
            p.scene.build(p.buffer, h, pl)
            p.minimap.draw(p.buffer, pl)

        r['full_scene'] = time_it(full_scene, iterations=200,
                                  label="完整场景构建(场景+小地图)")

        if strategy != 'bypass_ansi':
            def full_ansi(p=pipeline, h=hits, pl=player):
                p.scene.build(p.buffer, h, pl)
                p.minimap.draw(p.buffer, pl)
                p.render_to_bytes("HUD测试")

            r['full_pipeline'] = time_it(full_ansi, iterations=100,
                                         label="完整流水线 + ANSI输出")

        if strategy == 'bypass_ansi':
            from platform.win32_output import Win32ConsoleOutput
            output2 = Win32ConsoleOutput()
            if output2.available():
                def full_bypass(p=pipeline, h=hits, pl=player, o=output2):
                    p.scene.build(p.buffer, h, pl)
                    p.minimap.draw(p.buffer, pl)
                    o.write_frame(p.buffer.data, W, H, "HUD测试")
                r['full_pipeline'] = time_it(full_bypass, iterations=100,
                                             label="完整流水线 + BYPASS_ANSI输出")

        log("  [流水线耗时占比]")
        N = 100
        t_cast = t_scene = t_minimap = t_output = t_total = 0.0
        for _ in range(N):
            t0 = time.perf_counter()
            hits_local = raycaster.cast(player.x, player.y, dir_x, dir_y,
                                        plane_x, plane_y, W)
            t1 = time.perf_counter()
            pipeline.scene.build(pipeline.buffer, hits_local, player)
            t2 = time.perf_counter()
            pipeline.minimap.draw(pipeline.buffer, player)
            t3 = time.perf_counter()
            if strategy != 'bypass_ansi':
                pipeline.render_to_bytes("HUD测试")
            t4 = time.perf_counter()
            t_cast += t1 - t0
            t_scene += t2 - t1
            t_minimap += t3 - t2
            t_output += t4 - t3
            t_total += t4 - t0

        if t_total > 0:
            log("  %-20s  %8.1f us  %5.1f%%" % ("光线投射", t_cast/N*1e6, t_cast/t_total*100))
            log("  %-20s  %8.1f us  %5.1f%%" % ("场景构建", t_scene/N*1e6, t_scene/t_total*100))
            log("  %-20s  %8.1f us  %5.1f%%" % ("小地图", t_minimap/N*1e6, t_minimap/t_total*100))
            output_label = "ANSI编码" if strategy != 'bypass_ansi' else "Win32输出"
            log("  %-20s  %8.1f us  %5.1f%%" % (output_label, t_output/N*1e6, t_output/t_total*100))
            log("  %-20s  %8.1f us  %5.1f FPS" % ("总计", t_total/N*1e6, N/t_total))
        r['pipeline_fps'] = N / t_total if t_total > 0 else 0

        log("  [内存占用]")
        measure_memory(
            lambda: pipeline.scene.build(pipeline.buffer, hits, player),
            label="scene_builder.build() 内存")
        measure_memory(
            lambda: pipeline.render_to_bytes("HUD测试") if strategy != 'bypass_ansi' else None,
            label="render_to_bytes() 内存" if strategy != 'bypass_ansi' else "write_frame() 内存")

        strategy_summary[desc] = r
        restore_strategy(saved)
        log()

    # ========================================================================
    # 阶段4: 多分辨率对比
    # ========================================================================
    log("=" * 80)
    log("阶段4: 多分辨率对比 (ansi策略)")
    log("=" * 80)
    saved = save_strategy()
    apply_strategy('ansi')

    res_list = [(80, 24), (120, 30), (160, 40), (W, H)]
    for rw, rh in res_list:
        lighting = Lighting()
        pipeline = RenderPipeline(maze, lighting)
        pipeline.buffer.width = rw
        pipeline.buffer.height = rh
        pipeline.buffer.pixel_height = rh * 2
        pipeline.buffer._init()
        hits_rw = raycaster.cast(player.x, player.y, dir_x, dir_y,
                                 plane_x, plane_y, rw)

        def full_at_res(p=pipeline, h=hits_rw, pl=player):
            p.scene.build(p.buffer, h, pl)
            p.minimap.draw(p.buffer, pl)
            p.render_to_bytes("HUD")

        time_it(full_at_res, iterations=100,
                label="完整流水线 %dx%d" % (rw, rh))
    restore_strategy(saved)
    log()

    # ========================================================================
    # 阶段5: 微基准测试
    # ========================================================================
    log("=" * 80)
    log("阶段5: 微基准测试")
    log("=" * 80)

    log("  [光照系统]")
    saved = save_strategy()
    apply_strategy('ansi')
    time_it(lambda: Lighting.fog_factor(5.0),
            iterations=100000, label="fog_factor() d=5.0")
    time_it(lambda: Lighting.fog_factor(1.0),
            iterations=100000, label="fog_factor() d=1.0 (近)")
    time_it(lambda: Lighting.fog_factor(13.0),
            iterations=100000, label="fog_factor() d=13.0 (远)")
    time_it(lambda: Lighting.fog_factor(7.0),
            iterations=100000, label="fog_factor() d=7.0 (中)")
    time_it(lambda: [Lighting.fog_factor(d) for d in range(1, 20)],
            iterations=10000, label="fog_factor() x19 批量")

    lighting = Lighting()
    hit_test = hits[len(hits) // 2]
    time_it(lambda: lighting.wall_color(hit_test, 0.5),
            iterations=50000, label="lighting.wall_color()")
    time_it(lambda: lighting.ceiling_color(10, 24, 48),
            iterations=50000, label="lighting.ceiling_color()")
    time_it(lambda: lighting.floor_color(38, 24, 48),
            iterations=50000, label="lighting.floor_color()")
    time_it(lambda: Lighting._lerp((15, 15, 35), (35, 35, 65), 0.5),
            iterations=100000, label="Lighting._lerp()")
    time_it(lambda: Lighting._apply_brightness((150, 150, 175), 0.8),
            iterations=100000, label="Lighting._apply_brightness()")

    log("  [量化系统]")
    for qbits in [3, 4, 5, 6, 8]:
        apply_strategy('quantize', qbits)
        lq = Lighting()
        qt = lq._qtab
        time_it(lambda: (qt[128], qt[64], qt[200]),
                iterations=100000, label="量化查表 %d位 x3" % qbits)
    restore_strategy(saved)

    log("  [像素缓冲区]")
    buf = PixelBuffer(W, H)
    time_it(lambda: buf.fill_row(0, (100, 100, 100)),
            iterations=5000, label="buffer.fill_row() %d像素" % W)
    time_it(lambda: buf.set_pixel(10, 10, (100, 100, 100)),
            iterations=100000, label="buffer.set_pixel()")
    time_it(lambda: buf.resize(),
            iterations=10000, label="buffer.resize() (无变化)")
    time_it(lambda: PixelBuffer(80, 24),
            iterations=1000, label="PixelBuffer() 构造 80x24")

    log("  [HUD]")
    time_it(lambda: HUD.build(player, False, 60.0, "真彩色", W),
            iterations=10000, label="HUD.build()")
    time_it(lambda: HUD.build(player, True, 30.0, "16色", 80),
            iterations=10000, label="HUD.build() (短宽度)")

    log("  [事件总线]")
    eb = EventBus()
    counter = [0]
    def handler(data):
        counter[0] += 1
    eb.subscribe('test.event', handler)
    time_it(lambda: EventBus().subscribe('test.event', handler),
            iterations=50000, label="EventBus.subscribe()")
    time_it(lambda: eb.publish('test.event', {'key': 1}),
            iterations=50000, label="EventBus.publish() (1个handler)")
    eb2 = EventBus()
    eb2.subscribe('test.event2', handler)
    eb2.subscribe('test.event2', handler)
    time_it(lambda: eb2.publish('test.event2', None),
            iterations=50000, label="EventBus.publish() (2个handler)")
    time_it(lambda: eb2.unsubscribe('test.event2', handler),
            iterations=50000, label="EventBus.unsubscribe()")

    log("  [状态机]")
    sm = StateMachine()
    sm.add_state('idle', lambda: True)
    sm.add_state('active', lambda: True)
    sm.start('idle')
    time_it(lambda: sm.transition('active'),
            iterations=50000, label="StateMachine.transition()")
    time_it(lambda: sm.current,
            iterations=100000, label="StateMachine.current")
    sm.transition('idle')
    time_it(lambda: sm.update(),
            iterations=100000, label="StateMachine.update()")

    log("  [Win32平台操作]")
    try:
        from platform.win32_output import _rgb_to_attr
        _rgb_to_attr(128, 128, 128)
        time_it(lambda: _rgb_to_attr(128, 128, 128),
                iterations=100000, label="_rgb_to_attr() (缓存命中)")
        time_it(lambda: _rgb_to_attr(200, 100, 50),
                iterations=50000, label="_rgb_to_attr() (缓存未命中)")
        time_it(lambda: _rgb_to_attr(0, 0, 0),
                iterations=100000, label="_rgb_to_attr() (纯黑)")
        time_it(lambda: _rgb_to_attr(255, 255, 255),
                iterations=100000, label="_rgb_to_attr() (纯白)")
    except Exception:
        log("  (_rgb_to_attr 不可用)")

    time_it(lambda: shutil.get_terminal_size((80, 24)),
            iterations=10000, label="get_terminal_size()")
    log()

    # ========================================================================
    # 阶段6: 稳定性测试（长时间运行方差）
    # ========================================================================
    log("=" * 80)
    log("阶段6: 稳定性测试 (ansi策略, 500帧)")
    log("=" * 80)
    saved = save_strategy()
    apply_strategy('ansi')
    lighting = Lighting()
    pipeline = RenderPipeline(maze, lighting)
    pipeline.buffer.width = W
    pipeline.buffer.height = H
    pipeline.buffer.pixel_height = H * 2
    pipeline.buffer._init()

    N_STABLE = 500
    frame_times = []
    for i in range(N_STABLE):
        t0 = time.perf_counter()
        hits_i = raycaster.cast(player.x, player.y, dir_x, dir_y,
                                plane_x, plane_y, W)
        pipeline.scene.build(pipeline.buffer, hits_i, player)
        pipeline.minimap.draw(pipeline.buffer, player)
        pipeline.render_to_bytes("HUD")
        frame_times.append(time.perf_counter() - t0)

    avg_us = statistics.mean(frame_times) * 1e6
    stdev_us = statistics.stdev(frame_times) * 1e6 if N_STABLE > 1 else 0
    min_us = min(frame_times) * 1e6
    max_us = max(frame_times) * 1e6
    sorted_ft = sorted(frame_times)
    p50 = sorted_ft[len(sorted_ft) // 2] * 1e6
    p95 = sorted_ft[int(len(sorted_ft) * 0.95)] * 1e6
    p99 = sorted_ft[int(len(sorted_ft) * 0.99)] * 1e6
    avg_fps = 1.0 / statistics.mean(frame_times)

    log("  帧数: %d" % N_STABLE)
    log("  平均: %.1f us  标准差: %.1f us  CV: %.1f%%" % (
        avg_us, stdev_us, stdev_us / avg_us * 100 if avg_us > 0 else 0))
    log("  最小: %.1f us  最大: %.1f us  范围: %.1f us" % (min_us, max_us, max_us - min_us))
    log("  P50: %.1f us  P95: %.1f us  P99: %.1f us" % (p50, p95, p99))
    log("  平均FPS: %.1f" % avg_fps)

    slow_frames = sum(1 for t in frame_times if t * 1e6 > p95)
    log("  超过P95的帧数: %d (%.1f%%)" % (slow_frames, slow_frames / N_STABLE * 100))

    under_30 = sum(1 for t in frame_times if 1.0 / t >= 30.0)
    under_60 = sum(1 for t in frame_times if 1.0 / t >= 60.0)
    log("  达到30FPS的帧: %d/%d (%.1f%%)" % (under_30, N_STABLE, under_30 / N_STABLE * 100))
    log("  达到60FPS的帧: %d/%d (%.1f%%)" % (under_60, N_STABLE, under_60 / N_STABLE * 100))

    log("  帧时间分布:")
    buckets = [0, 5000, 10000, 15000, 20000, 30000, 50000, 100000]
    for i in range(len(buckets) - 1):
        lo, hi = buckets[i], buckets[i + 1]
        count = sum(1 for t in frame_times if lo <= t * 1e6 < hi)
        bar = '#' * int(count / N_STABLE * 60)
        log("    %5d-%5d us: %4d (%5.1f%%) %s" % (lo, hi, count, count / N_STABLE * 100, bar))
    count_over = sum(1 for t in frame_times if t * 1e6 >= buckets[-1])
    bar = '#' * int(count_over / N_STABLE * 60)
    log("    %5d+     us: %4d (%5.1f%%) %s" % (buckets[-1], count_over, count_over / N_STABLE * 100, bar))

    restore_strategy(saved)
    log()

    # ========================================================================
    # 阶段7: 内存占用估算
    # ========================================================================
    log("=" * 80)
    log("阶段7: 内存占用估算")
    log("=" * 80)
    tracemalloc.start()
    tracemalloc.reset_peak()

    m = Maze()
    p = Player(m.start[0], m.start[1], 0.0)
    rc = Raycaster(m)
    lg = Lighting()
    rp = RenderPipeline(m, lg)
    rp.buffer.width = W
    rp.buffer.height = H
    rp.buffer.pixel_height = H * 2
    rp.buffer._init()
    h = rc.cast(p.x, p.y, *p.dir_vector, *p.plane_vector, W)
    rp.scene.build(rp.buffer, h, p)
    rp.minimap.draw(rp.buffer, p)
    data = rp.render_to_bytes("HUD")

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    log("  游戏对象总内存: %.1f KB (当前) / %.1f KB (峰值)" % (current / 1024, peak / 1024))
    log("  ANSI输出数据:   %.1f KB" % (len(data) / 1024))
    log("  像素缓冲区:     %d x %d x 2 = %d 像素, 每像素~24B, 估算 %.1f KB" % (
        W, H, W * H * 2, W * H * 2 * 24 / 1024))
    log("  迷宫网格:       %d x %d = %d 单元格" % (m.width, m.height, m.width * m.height))

    measure_memory(lambda: Maze(), label="Maze() 单独创建")
    measure_memory(lambda: PixelBuffer(W, H), label="PixelBuffer() 单独创建")
    measure_memory(lambda: Lighting(), label="Lighting() 单独创建")
    log()

    # ========================================================================
    # 阶段8: 不同玩家位置/朝向下的性能
    # ========================================================================
    log("=" * 80)
    log("阶段8: 不同视角下的渲染性能 (ansi策略)")
    log("=" * 80)
    saved = save_strategy()
    apply_strategy('ansi')
    lighting = Lighting()
    pipeline = RenderPipeline(maze, lighting)
    pipeline.buffer.width = W
    pipeline.buffer.height = H
    pipeline.buffer.pixel_height = H * 2
    pipeline.buffer._init()

    test_angles = [0, math.pi / 4, math.pi / 2, math.pi, 1.5 * math.pi]
    angle_names = ['0°(东)', '45°', '90°(北)', '180°(西)', '270°(南)']
    for angle, name in zip(test_angles, angle_names):
        test_player = Player(maze.start[0], maze.start[1], angle)
        dx, dy = test_player.dir_vector
        px, py = test_player.plane_vector
        hits_a = raycaster.cast(test_player.x, test_player.y, dx, dy, px, py, W)

        def render_at_angle(p=pipeline, h=hits_a, pl=test_player):
            p.scene.build(p.buffer, h, pl)
            p.minimap.draw(p.buffer, pl)
            p.render_to_bytes("HUD")

        time_it(render_at_angle, iterations=100,
                label="渲染 朝向=%s" % name)

    test_player_moved = Player(maze.width / 2.0, maze.height / 2.0, 0.0)
    if not maze.is_wall(test_player_moved.x, test_player_moved.y):
        dx2, dy2 = test_player_moved.dir_vector
        px2, py2 = test_player_moved.plane_vector
        hits_m = raycaster.cast(test_player_moved.x, test_player_moved.y,
                                dx2, dy2, px2, py2, W)

        def render_moved(p=pipeline, h=hits_m, pl=test_player_moved):
            p.scene.build(p.buffer, h, pl)
            p.minimap.draw(p.buffer, pl)
            p.render_to_bytes("HUD")

        time_it(render_moved, iterations=100,
                label="渲染 迷宫中心位置")
    restore_strategy(saved)
    log()

    # ========================================================================
    # 阶段9: 事件总线与状态机压力测试
    # ========================================================================
    log("=" * 80)
    log("阶段9: 事件总线与状态机压力测试")
    log("=" * 80)
    eb2 = EventBus()
    handlers = []
    for i in range(10):
        def make_handler(idx):
            def h(data):
                pass
            return h
        hd = make_handler(i)
        handlers.append(hd)
        eb2.subscribe('stress.event', hd)
    time_it(lambda: eb2.publish('stress.event', {'value': 42}),
            iterations=50000, label="EventBus.publish() 10个handler")
    time_it(lambda: eb2.publish('nonexistent', None),
            iterations=100000, label="EventBus.publish() 无订阅者")

    sm2 = StateMachine()
    for i in range(10):
        sm2.add_state('s%d' % i, lambda: True)
    sm2.start('s0')
    time_it(lambda: sm2.transition('s1') and sm2.transition('s0'),
            iterations=50000, label="StateMachine 双状态切换")
    log()

    # ========================================================================
    # 汇总表
    # ========================================================================
    log("=" * 80)
    log("汇总: 各策略完整流水线性能对比")
    log("=" * 80)
    log("  %-24s  %8s  %8s  %8s  %8s  %8s" % (
        "策略", "场景us", "小地图us", "输出us", "总计us", "FPS"))
    log("  " + "-" * 76)
    for desc, r in strategy_summary.items():
        scene_us = r.get('scene', {}).get('avg_us', 0)
        minimap_us = r.get('minimap', {}).get('avg_us', 0)
        if 'render_to_bytes' in r:
            output_us = r['render_to_bytes']['avg_us']
        elif 'write_frame' in r:
            output_us = r['write_frame']['avg_us']
        else:
            output_us = 0
        total_us = r.get('full_pipeline', {}).get('avg_us', 0)
        fps = r.get('full_pipeline', {}).get('fps', 0)
        log("  %-24s  %8.1f  %8.1f  %8.1f  %8.1f  %8.1f" % (
            desc, scene_us, minimap_us, output_us, total_us, fps))
    log()

    log("=" * 80)
    log("汇总: 稳定性 (500帧 ansi)")
    log("=" * 80)
    log("  平均: %.1f us  标准差: %.1f us  CV: %.1f%%" % (
        avg_us, stdev_us, stdev_us / avg_us * 100 if avg_us > 0 else 0))
    log("  P50: %.1f us  P95: %.1f us  P99: %.1f us" % (p50, p95, p99))
    log("  FPS: %.1f (平均)  达标30FPS: %.1f%%  达标60FPS: %.1f%%" % (
        avg_fps, under_30 / N_STABLE * 100, under_60 / N_STABLE * 100))
    log()

    log("=" * 80)
    log("测试完成")
    log("=" * 80)

    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(_results))
    print("\n结果已写入: %s" % LOG_FILE)


if __name__ == '__main__':
    run_benchmark()
