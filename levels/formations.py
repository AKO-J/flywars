"""
==============================================================================
levels/formations.py — 敌机编队阵型定义
==============================================================================
定义各种编队阵型的默认参数（排列方式、间距、角度等）。
"""

from enum import Enum, auto


class FormationType(Enum):
    """编队阵型枚举"""
    NONE = auto()      # 无阵型，随机位置
    LINE = auto()      # 一字横排
    VSHAPE = auto()    # V字楔形
    TRIANGLE = auto()  # 正三角/倒三角
    ARC = auto()       # 弧线排列
    CROSS = auto()     # X形交叉
    SURROUND = auto()  # 两侧包围


# 编队阵型默认参数
FORMATION_DEFAULTS: dict[str, dict] = {
    "line": {
        "spacing": 60,
        "width": 450,
        "entry_y": -80,
        "angle": 0,
    },
    "vshape": {
        "spacing": 55,
        "width": 400,
        "entry_y": -80,
        "angle": 30,
    },
    "triangle": {
        "spacing": 60,
        "width": 400,
        "entry_y": -100,
        "angle": 0,
    },
    "arc": {
        "spacing": 45,
        "width": 380,
        "entry_y": -80,
        "angle": 150,
    },
    "cross": {
        "spacing": 55,
        "width": 400,
        "entry_y": -80,
        "angle": 35,
    },
    "surround": {
        "spacing": 60,
        "width": 500,
        "entry_y": -60,
        "angle": 25,
    },
}

# 阵型波次敌机生成间隔（秒）
FORMATION_SPAWN_INTERVAL: float = 0.12
