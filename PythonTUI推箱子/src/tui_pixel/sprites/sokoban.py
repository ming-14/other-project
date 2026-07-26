"""推箱子贴图 - 16x16像素贴图定义，支持alpha通道

贴图列表:
- WALL: 砖墙，深灰色砖块纹理
- FLOOR: 地板，深色底
- TARGET: 目标点，红色菱形标记+半透明发光
- BOX: 箱子，棕色木箱+半透明阴影
- BOX_ON_TARGET: 箱子在目标上，绿色发光箱+发光晕
- PLAYER: 玩家，从图片提取的16×16像素画
- PLAYER_ON_TARGET: 玩家在目标上，小人+红色标记
"""

from __future__ import annotations

from ..color import Color, TRANSPARENT
from ..sprite import Sprite, SpriteSheet

_ = TRANSPARENT
C = Color
T = TRANSPARENT

# ── 颜色定义 ──
WALL_DARK = C(60, 60, 68)
WALL_MID = C(85, 85, 95)
WALL_LIGHT = C(105, 105, 115)
WALL_MORTAR = C(40, 40, 48)

FLOOR_COLOR = C(30, 30, 38)

TARGET_RED = C(200, 50, 50)
TARGET_DARK = C(120, 30, 30)
TARGET_GLOW = C(200, 50, 50, 80)

BOX_BROWN = C(160, 100, 50)
BOX_DARK = C(110, 70, 35)
BOX_LIGHT = C(190, 130, 70)
BOX_EDGE = C(80, 50, 25)
BOX_SHADOW = C(0, 0, 0, 60)

BOX_OK_GREEN = C(50, 180, 50)
BOX_OK_DARK = C(30, 120, 30)
BOX_OK_LIGHT = C(80, 210, 80)
BOX_OK_EDGE = C(20, 80, 20)
BOX_OK_GLOW = C(50, 255, 50, 50)

# ── WALL 16x16 ──
_WM = WALL_MORTAR
_WD = WALL_DARK
_WI = WALL_MID
_WL = WALL_LIGHT
_WALL: list[list[Color]] = [
    [_WI,_WI,_WI,_WM,_WD,_WD,_WD,_WM,_WI,_WI,_WI,_WM,_WD,_WD,_WD,_WM],
    [_WI,_WL,_WI,_WI,_WM,_WD,_WL,_WD,_WI,_WL,_WI,_WI,_WM,_WD,_WL,_WD],
    [_WM,_WD,_WD,_WD,_WM,_WI,_WI,_WI,_WM,_WD,_WD,_WD,_WM,_WI,_WI,_WI],
    [_WD,_WL,_WD,_WI,_WI,_WM,_WD,_WD,_WD,_WL,_WD,_WI,_WI,_WM,_WD,_WD],
    [_WM,_WI,_WI,_WI,_WM,_WD,_WD,_WD,_WM,_WI,_WI,_WI,_WM,_WD,_WD,_WD],
    [_WI,_WI,_WL,_WM,_WD,_WI,_WD,_WI,_WI,_WI,_WL,_WM,_WD,_WI,_WD,_WI],
    [_WM,_WD,_WD,_WD,_WI,_WI,_WM,_WI,_WM,_WD,_WD,_WD,_WI,_WI,_WM,_WI],
    [_WD,_WI,_WD,_WI,_WL,_WM,_WI,_WD,_WD,_WI,_WD,_WI,_WL,_WM,_WI,_WD],
    [_WM,_WI,_WI,_WI,_WM,_WD,_WD,_WD,_WM,_WI,_WI,_WI,_WM,_WD,_WD,_WD],
    [_WI,_WL,_WI,_WI,_WM,_WD,_WL,_WD,_WI,_WL,_WI,_WI,_WM,_WD,_WL,_WD],
    [_WM,_WD,_WD,_WD,_WM,_WI,_WI,_WI,_WM,_WD,_WD,_WD,_WM,_WI,_WI,_WI],
    [_WD,_WL,_WD,_WI,_WI,_WM,_WD,_WD,_WD,_WL,_WD,_WI,_WI,_WM,_WD,_WD],
    [_WM,_WI,_WI,_WI,_WM,_WD,_WD,_WD,_WM,_WI,_WI,_WI,_WM,_WD,_WD,_WD],
    [_WI,_WI,_WL,_WM,_WD,_WI,_WD,_WI,_WI,_WI,_WL,_WM,_WD,_WI,_WD,_WI],
    [_WM,_WD,_WD,_WD,_WI,_WI,_WM,_WI,_WM,_WD,_WD,_WD,_WI,_WI,_WM,_WI],
    [_WD,_WI,_WD,_WI,_WL,_WM,_WI,_WD,_WD,_WI,_WD,_WI,_WL,_WM,_WI,_WD],
]

# ── FLOOR 16x16 ──
_FLOOR: list[list[Color]] = [[FLOOR_COLOR] * 16] * 16

# ── TARGET 16x16 ──
_TR = TARGET_RED
_TD = TARGET_DARK
_TG = TARGET_GLOW
_TARGET: list[list[Color]] = [
    [T,T,T,T,T,T,T,_TG,_TD,_TG,T,T,T,T,T,T],
    [T,T,T,T,T,T,_TG,_TD,_TR,_TD,_TG,T,T,T,T,T],
    [T,T,T,T,T,_TG,_TD,_TR,_TR,_TR,_TD,_TG,T,T,T,T],
    [T,T,T,T,_TG,_TD,_TR,_TR,_TR,_TR,_TR,_TD,_TG,T,T,T],
    [T,T,T,_TG,_TD,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TD,_TG,T,T],
    [T,T,_TG,_TD,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TD,_TG,T],
    [T,T,_TG,_TD,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TD,_TG],
    [_TG,_TD,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TD,_TG],
    [_TG,_TD,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TD,_TG],
    [T,T,_TG,_TD,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TD,_TG],
    [T,T,_TG,_TD,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TD,_TG,T],
    [T,T,T,_TG,_TD,_TR,_TR,_TR,_TR,_TR,_TR,_TR,_TD,_TG,T,T],
    [T,T,T,T,_TG,_TD,_TR,_TR,_TR,_TR,_TR,_TD,_TG,T,T,T],
    [T,T,T,T,T,_TG,_TD,_TR,_TR,_TR,_TD,_TG,T,T,T,T],
    [T,T,T,T,T,T,_TG,_TD,_TR,_TD,_TG,T,T,T,T,T],
    [T,T,T,T,T,T,T,_TG,_TD,_TG,T,T,T,T,T,T],
]

# ── BOX 16x16 ──
_BE = BOX_EDGE
_BB = BOX_BROWN
_BL = BOX_LIGHT
_BS = BOX_SHADOW
_BOX: list[list[Color]] = [
    [_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE],
    [_BE,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BE],
    [_BE,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BE],
    [_BE,_BB,_BB,_BL,_BB,_BB,_BB,_BL,_BL,_BB,_BB,_BB,_BL,_BB,_BB,_BE],
    [_BE,_BB,_BB,_BB,_BL,_BB,_BB,_BB,_BB,_BB,_BB,_BL,_BB,_BB,_BB,_BE],
    [_BE,_BB,_BB,_BB,_BB,_BL,_BB,_BB,_BB,_BB,_BL,_BB,_BB,_BB,_BB,_BE],
    [_BE,_BB,_BB,_BB,_BB,_BB,_BL,_BB,_BB,_BL,_BB,_BB,_BB,_BB,_BB,_BE],
    [_BE,_BB,_BB,_BB,_BB,_BB,_BB,_BL,_BL,_BB,_BB,_BB,_BB,_BB,_BB,_BE],
    [_BE,_BB,_BB,_BB,_BB,_BB,_BB,_BL,_BL,_BB,_BB,_BB,_BB,_BB,_BB,_BE],
    [_BE,_BB,_BB,_BB,_BB,_BB,_BL,_BB,_BB,_BL,_BB,_BB,_BB,_BB,_BB,_BE],
    [_BE,_BB,_BB,_BB,_BB,_BL,_BB,_BB,_BB,_BB,_BL,_BB,_BB,_BB,_BB,_BE],
    [_BE,_BB,_BB,_BB,_BL,_BB,_BB,_BB,_BB,_BB,_BB,_BL,_BB,_BB,_BB,_BE],
    [_BE,_BB,_BB,_BL,_BB,_BB,_BB,_BL,_BL,_BB,_BB,_BB,_BL,_BB,_BB,_BE],
    [_BE,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BE],
    [_BE,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BB,_BE],
    [_BS,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BE,_BS],
]

# ── BOX_ON_TARGET 16x16 ──
_OE = BOX_OK_EDGE
_OG = BOX_OK_GREEN
_OL = BOX_OK_LIGHT
_OKG = BOX_OK_GLOW
_BOX_ON_TARGET: list[list[Color]] = [
    [_OKG,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OKG],
    [_OE,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OE],
    [_OE,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OE],
    [_OE,_OG,_OG,_OL,_OG,_OG,_OG,_OL,_OL,_OG,_OG,_OG,_OL,_OG,_OG,_OE],
    [_OE,_OG,_OG,_OG,_OL,_OG,_OG,_OG,_OG,_OG,_OG,_OL,_OG,_OG,_OG,_OE],
    [_OE,_OG,_OG,_OG,_OG,_OL,_OG,_OG,_OG,_OG,_OL,_OG,_OG,_OG,_OG,_OE],
    [_OE,_OG,_OG,_OG,_OG,_OG,_OL,_OG,_OG,_OL,_OG,_OG,_OG,_OG,_OG,_OE],
    [_OE,_OG,_OG,_OG,_OG,_OG,_OG,_OL,_OL,_OG,_OG,_OG,_OG,_OG,_OG,_OE],
    [_OE,_OG,_OG,_OG,_OG,_OG,_OG,_OL,_OL,_OG,_OG,_OG,_OG,_OG,_OG,_OE],
    [_OE,_OG,_OG,_OG,_OG,_OG,_OL,_OG,_OG,_OL,_OG,_OG,_OG,_OG,_OG,_OE],
    [_OE,_OG,_OG,_OG,_OG,_OL,_OG,_OG,_OG,_OG,_OL,_OG,_OG,_OG,_OG,_OE],
    [_OE,_OG,_OG,_OG,_OL,_OG,_OG,_OG,_OG,_OG,_OG,_OL,_OG,_OG,_OG,_OE],
    [_OE,_OG,_OG,_OL,_OG,_OG,_OG,_OL,_OL,_OG,_OG,_OG,_OL,_OG,_OG,_OE],
    [_OE,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OE],
    [_OE,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OG,_OE],
    [_OKG,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OE,_OKG],
]

# ── PLAYER 16x16 ── (从图片提取)
_PH = C(85,62,116)       # 紫色头发
_PHL = C(129,130,174)    # 浅紫头发
_PS = C(247,233,223)     # 肤色
_PE = C(179,174,168)     # 肤色暗面
_PBL = C(20,22,71)       # 眼睛
_PAC = C(113,167,177)    # 嘴巴/配件
_PY = C(255,235,88)      # 黄色装饰
_PYB = C(177,137,76)     # 黄色暗面
_PLAYER: list[list[Color]] = [
    [T, T, T, T, T, T, T, T, T, T, T, T, T, T, T, T],
    [T, T, T, _PH, _PH, _PH, _PH, _PH, _PH, _PH, _PH, T, _PY, T, T, T],
    [T, T, _PH, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PH, _PY, _PYB, _PY, T, T],
    [T, _PH, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PH, _PH, _PHL, _PY, T],
    [T, _PH, _PHL, _PHL, _PH, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PH, _PHL, _PHL, _PH],
    [_PH, _PHL, _PHL, _PHL, _PH, _PHL, _PHL, _PHL, _PHL, _PH, _PHL, _PHL, _PHL, _PH, T, _PHL],
    [_PH, _PHL, _PH, _PHL, _PH, _PHL, _PHL, _PHL, _PH, _PH, _PHL, _PHL, _PHL, _PH, T, _PHL],
    [_PH, _PHL, _PH, _PH, _PS, _PH, _PHL, _PH, _PS, _PS, _PH, _PHL, _PHL, _PH, T, _PH],
    [_PH, _PHL, _PH, _PS, _PS, _PS, _PH, _PS, _PS, _PBL, _PS, _PH, _PHL, _PH, T, T],
    [_PH, _PHL, _PH, _PE, _PE, _PE, _PS, _PS, _PS, _PAC, _PS, _PH, _PHL, _PH, T, T],
    [_PH, _PHL, _PH, _PE, _PS, _PS, _PS, _PS, _PS, _PS, _PE, _PH, _PHL, _PH, T, T],
    [_PH, _PHL, _PHL, _PH, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PH, _PHL, _PHL, _PH, T, T],
    [T, _PH, _PHL, _PH, T, T, T, T, T, T, _PH, _PHL, _PH, T, T, T],
    [T, T, _PH, T, T, T, T, T, T, T, T, _PH, T, T, T, T],
    [T, T, T, T, T, T, T, T, T, T, T, T, T, T, T, T],
    [T, T, T, T, T, T, T, T, T, T, T, T, T, T, T, T],
]

# ── PLAYER_ON_TARGET 16x16 ──
_PLAYER_ON_TARGET: list[list[Color]] = [
    [T, T, T, T, T, T, T, T, T, T, T, T, T, _TD, _TG, T],
    [T, T, T, _PH, _PH, _PH, _PH, _PH, _PH, _PH, _PH, _PH, _TR, _TD, _TR, T],
    [T, T, _PH, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PH, _PY, _PYB, _PY, _TD, T],
    [T, _PH, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PH, _PH, _PHL, _PY, T],
    [T, _PH, _PHL, _PHL, _PH, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PH, _PHL, _PHL, _PH],
    [_PH, _PHL, _PHL, _PHL, _PH, _PHL, _PHL, _PHL, _PHL, _PH, _PHL, _PHL, _PHL, _PH, T, _PHL],
    [_PH, _PHL, _PH, _PHL, _PH, _PHL, _PHL, _PHL, _PH, _PH, _PHL, _PHL, _PHL, _PH, T, _PHL],
    [_PH, _PHL, _PH, _PH, _PS, _PH, _PHL, _PH, _PS, _PS, _PH, _PHL, _PHL, _PH, T, _PH],
    [_PH, _PHL, _PH, _PS, _PS, _PS, _PH, _PS, _PS, _PBL, _PS, _PH, _PHL, _PH, T, T],
    [_PH, _PHL, _PH, _PE, _PE, _PE, _PS, _PS, _PS, _PAC, _PS, _PH, _PHL, _PH, T, T],
    [_TD, _TR, _PH, _PE, _PS, _PS, _PS, _PS, _PS, _PS, _PE, _PH, _PHL, _PH, _TR, _TD],
    [_TD, _PH, _PHL, _PH, _PHL, _PHL, _PHL, _PHL, _PHL, _PHL, _PH, _PHL, _PHL, _PH, _TR, _TD],
    [T, _PH, _PHL, _PH, T, T, T, T, T, T, _PH, _PHL, _PH, T, T, T],
    [T, T, _PH, T, T, T, T, T, T, T, T, _PH, T, T, T, T],
    [T, T, T, T, T, T, T, T, T, T, T, T, T, T, T, T],
    [T, T, T, T, T, T, T, T, T, T, T, T, T, T, T, T],
]


def _to_tuple(data: list[list[Color]]) -> tuple[tuple[Color, ...], ...]:
    return tuple(tuple(row) for row in data)


SPRITE_WALL = Sprite("wall", _to_tuple(_WALL))
SPRITE_FLOOR = Sprite("floor", _to_tuple(_FLOOR))
SPRITE_TARGET = Sprite("target", _to_tuple(_TARGET))
SPRITE_BOX = Sprite("box", _to_tuple(_BOX))
SPRITE_BOX_ON_TARGET = Sprite("box_on_target", _to_tuple(_BOX_ON_TARGET))
SPRITE_PLAYER = Sprite("player", _to_tuple(_PLAYER))
SPRITE_PLAYER_ON_TARGET = Sprite("player_on_target", _to_tuple(_PLAYER_ON_TARGET))


def create_sokoban_sheet() -> SpriteSheet:
    """创建推箱子贴图表"""
    sheet = SpriteSheet("sokoban")
    sheet.add(SPRITE_WALL)
    sheet.add(SPRITE_FLOOR)
    sheet.add(SPRITE_TARGET)
    sheet.add(SPRITE_BOX)
    sheet.add(SPRITE_BOX_ON_TARGET)
    sheet.add(SPRITE_PLAYER)
    sheet.add(SPRITE_PLAYER_ON_TARGET)
    return sheet
