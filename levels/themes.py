"""
==============================================================================
levels/themes.py — 背景关卡主题定义
==============================================================================
每个主题包括：星星层配置、叠加色调、星云数量、天体出现率等。
"""


class BackgroundTheme:
    """单个背景主题配置。"""

    def __init__(self, name, layer_configs, overlay_color=(0, 0, 0),
                 overlay_alpha=0, accent_color=(255, 255, 255),
                 nebula_count=2, celestial_chance=0.5):
        self.name = name
        self.layer_configs = layer_configs
        self.overlay_color = overlay_color
        self.overlay_alpha = overlay_alpha
        self.accent_color = accent_color
        self.nebula_count = nebula_count
        self.celestial_chance = celestial_chance


# ═══════════════════════════════════════════════════════════════════
# 预定义主题
# ═══════════════════════════════════════════════════════════════════

THEME_STARFIELD = BackgroundTheme(
    name="星空",
    layer_configs=[
        (60, 1, 2, 0.3, 60, 120, (180, 200, 255)),
        (35, 2, 4, 0.6, 100, 170, (200, 220, 255)),
        (20, 3, 6, 1.0, 150, 255, (255, 255, 255)),
    ],
    overlay_color=(0, 0, 20), overlay_alpha=12,
    accent_color=(100, 180, 255),
    nebula_count=3, celestial_chance=0.5,
)

THEME_NEBULA = BackgroundTheme(
    name="星云",
    layer_configs=[
        (70, 1, 3, 0.3, 40, 100, (200, 150, 255)),
        (40, 2, 5, 0.6, 60, 140, (255, 200, 150)),
        (25, 3, 7, 1.0, 100, 200, (255, 180, 100)),
    ],
    overlay_color=(30, 10, 40), overlay_alpha=20,
    accent_color=(200, 150, 255),
    nebula_count=5, celestial_chance=0.8,
)

THEME_RED_ALERT = BackgroundTheme(
    name="警戒",
    layer_configs=[
        (50, 1, 2, 0.3, 40, 80, (180, 60, 60)),
        (30, 2, 4, 0.6, 60, 120, (220, 80, 80)),
        (15, 3, 6, 1.0, 80, 180, (255, 100, 50)),
    ],
    overlay_color=(40, 0, 0), overlay_alpha=25,
    accent_color=(255, 80, 80),
    nebula_count=6, celestial_chance=0.3,
)

# ═══════════════════════════════════════════════════════════════════
# 关卡 → 主题映射
# ═══════════════════════════════════════════════════════════════════

LEVEL_THEMES = [
    (1, THEME_STARFIELD),
    (4, THEME_NEBULA),
    (7, THEME_RED_ALERT),
]


def get_theme_for_level(level: int) -> BackgroundTheme:
    """根据关卡返回对应的背景主题。"""
    theme = THEME_STARFIELD
    for threshold, t in LEVEL_THEMES:
        if level >= threshold:
            theme = t
    return theme
