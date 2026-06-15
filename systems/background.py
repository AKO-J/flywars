"""
==============================================================================
飞机大战 — 无限滚动背景系统（题5：背景动画）
==============================================================================
实现多层视差星空背景 + 关卡主题变化系统。

技术要点：
  1. 视差滚动（Parallax Scrolling）：3层星星以不同速度移动，营造深度感
  2. Delta-Time 驱动：所有速度单位 = 像素/秒，乘以 dt 后与 FPS 解耦
  3. 无限循环：星星移出屏幕底部 → 回收至顶部，随机重置 x 坐标
  4. 程序化生成：随机大小/亮度/位置，无需美术资源
  5. ⭐ 关卡主题：随关卡范围自动切换背景风格（星云/星空/警戒）
"""

import random
import math
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    BACKGROUND_BASE_SPEED, BACKGROUND_LAYERS,
    BLACK, WHITE,
)


class Star:
    """单颗星星粒子"""

    __slots__ = ("x", "y", "size", "speed", "color")

    def __init__(
        self,
        x: float,
        y: float,
        size: int,
        speed: float,
        brightness: int,
        color: tuple = (0, 0, 0),
    ) -> None:
        """
        参数：
            x, y       : 初始坐标（float 支持亚像素精度）
            size       : 半径（像素）
            speed      : 滚动速度（像素/秒）
            brightness : 亮度（0-255），用于灰度颜色
            color      : 颜色（灰度时用 brightness 覆盖）
        """
        self.x: float = x
        self.y: float = y
        self.size: int = size
        self.speed: float = speed
        # 如果传入了彩色，保留色调；否则灰度
        if color != (0, 0, 0):
            self.color: tuple = color
        else:
            self.color: tuple = (brightness, brightness, brightness)

    def update(self, dt: float) -> None:
        """
        根据 Delta-Time 更新位置。
        ————————————————————————————————
        dt 单位：秒
        移动量 = speed(px/s) × dt(s) = 像素
        """
        self.y += self.speed * dt

        # 移出屏幕底部 → 回收到顶部
        if self.y > SCREEN_HEIGHT + self.size:
            self.y = -self.size
            self.x = random.uniform(0, SCREEN_WIDTH)

    def draw(self, screen: pygame.Surface) -> None:
        """在屏幕上绘制该星星（使用圆形）"""
        if self.size <= 1:
            screen.set_at((int(self.x), int(self.y)), self.color)
        else:
            pygame.draw.circle(
                screen, self.color, (int(self.x), int(self.y)), self.size
            )


# ═══════════════════════════════════════════════════════════════════
# ⭐ 关卡主题定义
# ═══════════════════════════════════════════════════════════════════

class BackgroundTheme:
    """单个背景主题配置。"""

    def __init__(
        self,
        name: str,
        layer_configs: list[tuple],
        overlay_color: tuple = (0, 0, 0),
        overlay_alpha: int = 0,
        accent_color: tuple = (255, 255, 255),
    ) -> None:
        self.name = name
        # layer_configs: [(count, min_size, max_size, speed_factor, min_bright, max_bright, color?)]
        self.layer_configs = layer_configs
        self.overlay_color = overlay_color      # 半透明叠加色（营造氛围）
        self.overlay_alpha = overlay_alpha      # 叠加透明度
        self.accent_color = accent_color        # UI 点缀色


# 预定义主题
THEME_STARFIELD = BackgroundTheme(
    name="星空",
    layer_configs=[
        (40, 1, 1, 0.3, 60, 120, (180, 200, 255)),   # 远层：淡蓝
        (25, 1, 2, 0.6, 100, 170, (200, 220, 255)),   # 中层：白蓝
        (15, 2, 3, 1.0, 150, 255, (255, 255, 255)),   # 近层：白
    ],
    overlay_color=(0, 0, 20),
    overlay_alpha=15,
    accent_color=(100, 180, 255),
)

THEME_NEBULA = BackgroundTheme(
    name="星云",
    layer_configs=[
        (50, 1, 2, 0.3, 40, 100, (200, 150, 255)),    # 远层：紫色
        (30, 1, 3, 0.6, 60, 140, (255, 200, 150)),    # 中层：橙黄
        (20, 2, 4, 1.0, 100, 200, (255, 180, 100)),   # 近层：暖橙
    ],
    overlay_color=(30, 10, 40),
    overlay_alpha=25,
    accent_color=(200, 150, 255),
)

THEME_RED_ALERT = BackgroundTheme(
    name="警戒",
    layer_configs=[
        (30, 1, 1, 0.3, 40, 80, (180, 60, 60)),       # 远层：暗红
        (20, 1, 2, 0.6, 60, 120, (220, 80, 80)),       # 中层：红
        (10, 2, 3, 1.0, 80, 180, (255, 100, 50)),      # 近层：亮橙红
    ],
    overlay_color=(40, 0, 0),
    overlay_alpha=30,
    accent_color=(255, 80, 80),
)

# 关卡 → 主题映射
LEVEL_THEMES = [
    (1, THEME_STARFIELD),     # 第 1-3 关：蓝色星空
    (4, THEME_NEBULA),        # 第 4-6 关：紫色星云
    (7, THEME_RED_ALERT),     # 第 7-9 关：红色警戒
]


def get_theme_for_level(level: int) -> BackgroundTheme:
    """根据关卡返回对应的背景主题。"""
    theme = THEME_STARFIELD
    for threshold, t in LEVEL_THEMES:
        if level >= threshold:
            theme = t
    return theme


# ═══════════════════════════════════════════════════════════════════
# 关卡主题背景
# ═══════════════════════════════════════════════════════════════════

class ScrollingBackground:
    """
    多层视差滚动背景 — 支持关卡主题切换。
    ————————————————————————————————
    管理多个星层，每层有独立的配置。

    调用流程：
      bg = ScrollingBackground()
      bg.set_theme(level=1)    # 根据关卡设置主题
      while running:
          dt = clock.tick(FPS) / 1000.0
          bg.update(dt)
          bg.draw(screen)
    """

    def __init__(self) -> None:
        """初始化为默认星空主题"""
        self._layers: list[list[Star]] = []
        self._overlay: pygame.Surface | None = None
        self._current_theme: BackgroundTheme = THEME_STARFIELD
        # ⭐ 主题过渡
        self._transition_progress: float = 1.0  # 0.0=过渡中, 1.0=完成
        self._prev_layers: list[list[Star]] = []
        self._prev_overlay: pygame.Surface | None = None
        # 初始化
        self._build_from_theme(THEME_STARFIELD)

    def _build_from_theme(self, theme: BackgroundTheme) -> list[list[Star]]:
        """根据主题配置生成星层，返回层列表。"""
        layers: list[list[Star]] = []
        for cfg in theme.layer_configs:
            count, min_size, max_size, speed_factor, min_bright, max_bright = cfg[:6]
            color_hint = cfg[6] if len(cfg) > 6 else None
            layer: list[Star] = []
            layer_speed: float = BACKGROUND_BASE_SPEED * speed_factor
            for _ in range(count):
                x: float = random.uniform(0, SCREEN_WIDTH)
                y: float = random.uniform(0, SCREEN_HEIGHT)
                size: int = random.randint(min_size, max_size)
                brightness: int = random.randint(min_bright, max_bright)
                star = Star(x, y, size, layer_speed, brightness)
                # 彩色
                if color_hint:
                    bright_ratio = brightness / 255.0
                    star.color = tuple(min(255, int(c * bright_ratio)) for c in color_hint)
                layer.append(star)
            layers.append(layer)
        return layers

    def _make_overlay(self, theme: BackgroundTheme) -> pygame.Surface | None:
        """为主题创建半透明叠加层。"""
        if theme.overlay_alpha <= 0:
            return None
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        surf.fill((*theme.overlay_color, theme.overlay_alpha))
        return surf

    def set_theme_by_level(self, level: int) -> bool:
        """根据关卡设置主题。返回 True 表示主题有变化。"""
        new_theme = get_theme_for_level(level)
        if new_theme is self._current_theme:
            return False
        # 保存旧层用于过渡
        self._prev_layers = self._layers
        self._prev_overlay = self._overlay
        # 生成新层
        self._current_theme = new_theme
        self._layers = self._build_from_theme(new_theme)
        self._overlay = self._make_overlay(new_theme)
        self._transition_progress = 0.0
        return True

    def update(self, dt: float) -> None:
        """
        更新所有星层 + 主题过渡。
        ————————————————————————————————
        dt : float — 距上一帧的时间间隔（秒）
        """
        # 主题过渡推进
        if self._transition_progress < 1.0:
            self._transition_progress = min(1.0, self._transition_progress + dt * 0.5)
            # 过渡期间旧层继续滚动
            for layer in self._prev_layers:
                for star in layer:
                    star.update(dt)
        else:
            self._prev_layers.clear()

        for layer in self._layers:
            for star in layer:
                star.update(dt)

    def draw(self, screen: pygame.Surface) -> None:
        """绘制所有星层到屏幕上"""
        # 过渡期：同时绘制旧层（渐隐）和新层（渐显）
        if self._transition_progress < 1.0 and self._prev_layers:
            # 绘制旧层（逐渐淡出）
            for layer in self._prev_layers:
                for star in layer:
                    alpha = int(255 * (1.0 - self._transition_progress))
                    if alpha > 0:
                        old_color = star.color
                        dimmed = tuple(int(c * alpha / 255) for c in old_color)
                        orig_color = star.color
                        star.color = dimmed
                        star.draw(screen)
                        star.color = orig_color
            # 新层（逐渐淡入）
            for layer in self._layers:
                for star in layer:
                    alpha = int(255 * self._transition_progress)
                    if alpha > 0:
                        old_color = star.color
                        dimmed = tuple(int(c * alpha / 255) for c in old_color)
                        orig_color = star.color
                        star.color = dimmed
                        star.draw(screen)
                        star.color = orig_color
        else:
            for layer in self._layers:
                for star in layer:
                    star.draw(screen)

        # 叠加色调
        if self._overlay:
            screen.blit(self._overlay, (0, 0))

    def draw_rect(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        """仅绘制与指定 rect 相交的星星（用于脏矩形局部擦除）。"""
        clip = rect.clip(screen.get_rect())
        if clip.width <= 0 or clip.height <= 0:
            return
        screen.fill(BLACK, clip)
        # 过渡期两者都画
        layers_to_draw = []
        if self._transition_progress < 1.0 and self._prev_layers:
            layers_to_draw.extend(self._prev_layers)
        layers_to_draw.extend(self._layers)
        for layer in layers_to_draw:
            for star in layer:
                sr = pygame.Rect(
                    int(star.x) - star.size,
                    int(star.y) - star.size,
                    star.size * 2,
                    star.size * 2,
                )
                if sr.colliderect(clip):
                    star.draw(screen)

    @property
    def current_theme(self) -> BackgroundTheme:
        return self._current_theme


class BackgroundCallback:
    """可调用包装器，供 LayeredDirty.clear() 的 bgd 参数使用。"""

    def __init__(self, bg: ScrollingBackground) -> None:
        self._bg = bg

    def __call__(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        self._bg.draw_rect(surface, rect)
