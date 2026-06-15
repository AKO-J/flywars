"""
==============================================================================
levels/__init__.py — 关卡数据包
==============================================================================
导出声明的关卡数据，供 settings / spawner / 其他模块引用。
"""

from .waves import (
    LEVEL_WAVES,
    WAVE_REST_DURATION,
    WAVE_ANNOUNCE_DURATION,
    EnemyWaveType,
    FINAL_BOSS_LEVEL,
)
from .formations import (
    FormationType,
    FORMATION_DEFAULTS,
    FORMATION_SPAWN_INTERVAL,
)
from .themes import (
    BackgroundTheme,
    THEME_STARFIELD,
    THEME_NEBULA,
    THEME_RED_ALERT,
    LEVEL_THEMES,
    get_theme_for_level,
)

__all__ = [
    "LEVEL_WAVES", "WAVE_REST_DURATION", "WAVE_ANNOUNCE_DURATION",
    "EnemyWaveType", "FINAL_BOSS_LEVEL",
    "FormationType", "FORMATION_DEFAULTS", "FORMATION_SPAWN_INTERVAL",
    "BackgroundTheme",
    "THEME_STARFIELD", "THEME_NEBULA", "THEME_RED_ALERT",
    "LEVEL_THEMES", "get_theme_for_level",
]
