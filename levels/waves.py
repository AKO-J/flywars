"""
==============================================================================
levels/waves.py — 关卡波次定义
==============================================================================
每关的波次列表、敌机编队、Boss 标记和波次节奏参数。
"""

from typing import Literal

# 敌机类型别名
EnemyWaveType = Literal["normal", "fast", "elite", "tracking"]

# 最终 Boss 所在关卡（击败该关 Boss 通关）
FINAL_BOSS_LEVEL: int = 9

# 波次间休息时间（秒）
WAVE_REST_DURATION: float = 0.6      # 原1.2→加快波间节奏
# 波次推进提示显示时间
WAVE_ANNOUNCE_DURATION: float = 0.5   # 原1.0→缩短提示

# ═══════════════════════════════════════════════════════════════════
# 关卡波次定义
# ═══════════════════════════════════════════════════════════════════

LEVEL_WAVES: dict[int, dict] = {
    1: {  # 入门关 — 2波快速入门
        "waves": [
            {"units": [("normal", 4)], "formation": "line"},
            {"units": [("normal", 3), ("fast", 2)], "formation": "vshape"},
        ],
        "spawn_interval": 0.48,  # 原0.9 → 更快
        "has_boss": False,
    },
    2: {  # 快速敌机 — 2波
        "waves": [
            {"units": [("normal", 4), ("fast", 2)], "formation": "vshape"},
            {"units": [("normal", 3), ("fast", 3)], "formation": "triangle"},
        ],
        "spawn_interval": 0.42,  # 原0.8 → 更快
        "has_boss": False,
    },
    3: {  # 引入精英敌机
        "waves": [
            {"units": [("normal", 4), ("fast", 1)], "formation": "line"},
            {"units": [("normal", 3), ("elite", 1)], "formation": "triangle"},
            {"units": [("normal", 4), ("fast", 3)], "formation": "vshape"},
            {"units": [("normal", 5), ("fast", 2), ("elite", 1)], "formation": "cross"},
        ],
        "spawn_interval": 0.45,
        "has_boss": False,
    },
    4: {  # 引入追踪敌机
        "waves": [
            {"units": [("normal", 4), ("fast", 2)], "formation": "line"},
            {"units": [("normal", 3), ("fast", 2), ("tracking", 1)], "formation": "vshape"},
            {"units": [("normal", 4), ("fast", 3), ("elite", 1)], "formation": "arc"},
            {"units": [("normal", 5), ("fast", 3), ("tracking", 1)], "formation": "cross"},
        ],
        "spawn_interval": 0.42,
        "has_boss": False,
    },
    5: {  # ⭐ 首个 Boss 战
        "waves": [
            {"units": [("normal", 5), ("fast", 2)], "formation": "line"},
            {"units": [("normal", 3), ("fast", 3), ("elite", 1)], "formation": "vshape"},
            {"units": [("normal", 4), ("fast", 3), ("elite", 2)], "formation": "triangle"},
            {"units": [("normal", 6), ("fast", 3), ("tracking", 1)], "formation": "surround"},
        ],
        "spawn_interval": 0.39,
        "has_boss": True,
    },
    6: {  # 战间期 — 混合编队
        "waves": [
            {"units": [("normal", 4), ("fast", 3), ("tracking", 1)], "formation": "vshape"},
            {"units": [("normal", 3), ("fast", 2), ("elite", 2)], "formation": "cross"},
            {"units": [("normal", 4), ("fast", 3), ("elite", 2)], "formation": "triangle"},
            {"units": [("normal", 5), ("fast", 3), ("tracking", 2)], "formation": "arc"},
            {"units": [("normal", 6), ("fast", 4), ("elite", 1), ("tracking", 1)], "formation": "surround"},
        ],
        "spawn_interval": 0.36,
        "has_boss": False,
    },
    7: {  # 高密度 — 全阵型展示
        "waves": [
            {"units": [("normal", 6), ("fast", 3), ("tracking", 1)], "formation": "line"},
            {"units": [("normal", 5), ("fast", 4), ("elite", 2)], "formation": "vshape"},
            {"units": [("normal", 6), ("fast", 3), ("tracking", 2)], "formation": "triangle"},
            {"units": [("normal", 5), ("fast", 4), ("elite", 2), ("tracking", 2)], "formation": "cross"},
            {"units": [("normal", 8), ("fast", 5), ("elite", 2)], "formation": "surround"},
        ],
        "spawn_interval": 0.32,
        "has_boss": False,
    },
    8: {  # 最终关前哨
        "waves": [
            {"units": [("normal", 6), ("fast", 4), ("tracking", 2)], "formation": "vshape"},
            {"units": [("normal", 5), ("fast", 4), ("elite", 3)], "formation": "cross"},
            {"units": [("normal", 6), ("fast", 5), ("tracking", 3)], "formation": "triangle"},
            {"units": [("normal", 8), ("fast", 4), ("elite", 3), ("tracking", 2)], "formation": "arc"},
            {"units": [("normal", 10), ("fast", 5), ("elite", 3), ("tracking", 2)], "formation": "surround"},
        ],
        "spawn_interval": 0.30,
        "has_boss": False,
    },
    9: {  # ⭐ 最终 Boss 战
        "waves": [
            {"units": [("normal", 8), ("fast", 5), ("tracking", 2)], "formation": "vshape"},
            {"units": [("normal", 6), ("fast", 5), ("elite", 3), ("tracking", 2)], "formation": "cross"},
            {"units": [("normal", 10), ("fast", 4), ("elite", 3)], "formation": "triangle"},
            {"units": [("normal", 8), ("fast", 5), ("tracking", 3), ("elite", 2)], "formation": "arc"},
            {"units": [("normal", 10), ("fast", 6), ("elite", 4), ("tracking", 3)], "formation": "surround"},
            {"units": [("normal", 8), ("fast", 6), ("elite", 4), ("tracking", 3)], "formation": "cross"},
        ],
        "spawn_interval": 0.26,
        "has_boss": True,
        "final": True,
    },
}
