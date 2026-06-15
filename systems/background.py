"""
==============================================================================
飞机大战 — 无限滚动背景系统
==============================================================================
多层视差星空 + 关卡主题 + 动态元素（星云/流星/天体/脉冲）。
"""

import random
import math
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    BACKGROUND_BASE_SPEED, BACKGROUND_LAYERS,
    BLACK, WHITE,
)


# ==========================================================================
# 星星
# ==========================================================================

class Star:
    __slots__ = ("x", "y", "size", "speed", "color")

    def __init__(self, x, y, size, speed, brightness, color=(0, 0, 0)):
        self.x, self.y = x, y
        self.size, self.speed = size, speed
        self.color = (brightness, brightness, brightness) if color == (0, 0, 0) else color

    def update(self, dt):
        self.y += self.speed * dt
        if self.y > SCREEN_HEIGHT + self.size:
            self.y = -self.size
            self.x = random.uniform(0, SCREEN_WIDTH)

    def draw(self, screen):
        if self.size <= 1:
            screen.set_at((int(self.x), int(self.y)), self.color)
        else:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.size)


# ═══════════════════════════════════════════════════════════════════
# ⭐ 动态元素
# ═══════════════════════════════════════════════════════════════════

class NebulaCloud:
    """半透明星云云团 — 大块彩色光晕，缓慢漂移。"""

    def __init__(self):
        self.x = random.uniform(-100, SCREEN_WIDTH + 100)
        self.y = random.uniform(-100, SCREEN_HEIGHT + 100)
        self.radius = random.randint(80, 220)
        self.color = (
            random.randint(30, 120),
            random.randint(20, 80),
            random.randint(60, 150),
        )
        self.alpha = random.randint(8, 25)
        self.speed_x = random.uniform(-4, 4)
        self.speed_y = random.uniform(2, 6)
        self.pulse_speed = random.uniform(0.2, 0.5)
        self.pulse_offset = random.uniform(0, math.pi * 2)
        self._surf = None

    def update(self, dt, time_s):
        self.x += self.speed_x * dt
        self.y += self.speed_y * dt
        # 缠绕回另一边
        margin = -self.radius - 50
        if self.x > SCREEN_WIDTH + self.radius + 50:
            self.x = margin
        elif self.x < margin:
            self.x = SCREEN_WIDTH + self.radius + 50
        if self.y > SCREEN_HEIGHT + self.radius + 50:
            self.y = margin
        elif self.y < margin:
            self.y = SCREEN_HEIGHT + self.radius + 50
        # 脉冲呼吸
        self._surf = None  # 重建标记

    def draw(self, screen, time_s):
        pulse = 0.7 + 0.3 * math.sin(time_s * self.pulse_speed + self.pulse_offset)
        r = int(self.radius * pulse)
        alpha = int(self.alpha * pulse)
        if r <= 0 or alpha <= 0:
            return
        # 用缓存的 surface（逐帧重建性能也不差，因为数量少）
        surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for i in range(r, 0, -1):
            a = int(alpha * (1.0 - i / r))
            if a <= 0:
                continue
            ratio = i / r
            c = tuple(min(255, int(cv * (0.3 + 0.7 * ratio))) for cv in self.color)
            pygame.draw.circle(surf, (*c, a), (r, r), i)
        screen.blit(surf, (int(self.x) - r, int(self.y) - r))


class ShootingStar:
    """流星 — 快速划过屏幕的亮线。"""

    def __init__(self):
        self.reset()
        self.timer = random.uniform(2, 8)  # 出现间隔

    def reset(self):
        self.active = False
        self.timer = random.uniform(3, 10)
        self.x = random.uniform(0, SCREEN_WIDTH * 0.7)
        self.y = random.uniform(-30, SCREEN_HEIGHT * 0.3)
        self.speed = random.uniform(400, 700)
        self.angle = random.uniform(0.4, 0.9)  # 与水平夹角
        self.length = random.randint(40, 100)
        self.brightness = random.randint(180, 255)
        self.lifetime = random.uniform(0.15, 0.4)

    def update(self, dt):
        if not self.active:
            self.timer -= dt
            if self.timer <= 0:
                self.active = True
                self.start_x = self.x
                self.start_y = self.y
                self.age = 0.0
                # 重置位置
                self.x = random.uniform(0, SCREEN_WIDTH * 0.7)
                self.y = random.uniform(-30, SCREEN_HEIGHT * 0.3)
                self.angle = random.uniform(0.4, 0.9)
                self.speed = random.uniform(400, 700)
                self.length = random.randint(40, 100)
                self.brightness = random.randint(180, 255)
                self.lifetime = random.uniform(0.15, 0.4)
            return
        self.age += dt
        if self.age > self.lifetime:
            self.active = False
            self.timer = random.uniform(3, 10)
            return
        dx = math.cos(self.angle) * self.speed * dt
        dy = math.sin(self.angle) * self.speed * dt
        self.x += dx
        self.y += dy

    def draw(self, screen):
        if not self.active:
            return
        progress = self.age / self.lifetime
        alpha = int(self.brightness * (1.0 - progress))
        if alpha <= 0:
            return
        # 尾迹渐变：用 Surface 支持 alpha
        segments = 10
        for i in range(segments):
            t = i / segments
            seg_alpha = int(alpha * (1.0 - t))
            if seg_alpha <= 0:
                continue
            sx = int(self.x - math.cos(self.angle) * self.length * t)
            sy = int(self.y - math.sin(self.angle) * self.length * t)
            sw = max(1, int(2 * (1.0 - t)))
            # ⭐ 用 Surface 支持半透明
            dot = pygame.Surface((sw * 2, sw * 2), pygame.SRCALPHA)
            pygame.draw.circle(dot, (255, 255, 255, seg_alpha), (sw, sw), sw)
            screen.blit(dot, (sx - sw, sy - sw))


class CelestialBody:
    """天体（行星/恒星）— 缓慢横穿画面，带光晕。"""

    def __init__(self, theme_color):
        self.reset(theme_color)
        self.active = False
        self.appear_timer = random.uniform(5, 15)

    def reset(self, theme_color=None):
        side = random.choice(["left", "right", "top"])
        if side == "left":
            self.x = -80
            self.y = random.uniform(50, SCREEN_HEIGHT * 0.4)
            self.vx = random.uniform(3, 6)
            self.vy = random.uniform(0.2, 0.8)
        elif side == "right":
            self.x = SCREEN_WIDTH + 80
            self.y = random.uniform(50, SCREEN_HEIGHT * 0.4)
            self.vx = random.uniform(-6, -3)
            self.vy = random.uniform(0.2, 0.8)
        else:
            self.x = random.uniform(50, SCREEN_WIDTH - 50)
            self.y = -80
            self.vx = random.uniform(-1, 1)
            self.vy = random.uniform(2, 5)
        self.radius = random.randint(15, 35)
        # 颜色从主题色派生
        if theme_color:
            base = theme_color
        else:
            base = (200, 180, 150)
        self.color = (
            min(255, base[0] + random.randint(-30, 30)),
            min(255, base[1] + random.randint(-30, 30)),
            min(255, base[2] + random.randint(-30, 30)),
        )
        self.glow_color = (
            min(255, self.color[0] + 40),
            min(255, self.color[1] + 40),
            min(255, self.color[2] + 40),
        )
        self.glow_alpha = 30

    def update(self, dt):
        if not self.active:
            self.appear_timer -= dt
            if self.appear_timer <= 0:
                self.active = True
            return
        self.x += self.vx * dt
        self.y += self.vy * dt
        # 超出屏幕后重新计时
        if (self.x < -150 or self.x > SCREEN_WIDTH + 150
                or self.y < -150 or self.y > SCREEN_HEIGHT + 150):
            self.active = False
            self.appear_timer = random.uniform(8, 20)

    def draw(self, screen):
        if not self.active:
            return
        ix, iy = int(self.x), int(self.y)
        r = self.radius
        # 外层光晕（合并成一个大 surface）
        glow_r = r + 36
        glow = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
        for i in range(3):
            gr = r + (i + 1) * 12
            ga = self.glow_alpha // (i + 1)
            if ga > 0:
                pygame.draw.circle(glow, (*self.glow_color, ga), (glow_r, glow_r), gr)
        screen.blit(glow, (ix - glow_r, iy - glow_r))
        # 星体本身
        pygame.draw.circle(screen, self.color, (ix, iy), r)
        # 高光
        hl = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(hl, (255, 255, 255, 40), (r, r), r)
        screen.blit(hl, (ix - r, iy - r))


# ═══════════════════════════════════════════════════════════════════
# 主题定义
# ═══════════════════════════════════════════════════════════════════

class BackgroundTheme:
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


THEME_STARFIELD = BackgroundTheme(
    name="星空",
    layer_configs=[
        (40, 1, 1, 0.3, 60, 120, (180, 200, 255)),
        (25, 1, 2, 0.6, 100, 170, (200, 220, 255)),
        (15, 2, 3, 1.0, 150, 255, (255, 255, 255)),
    ],
    overlay_color=(0, 0, 20), overlay_alpha=12,
    accent_color=(100, 180, 255),
    nebula_count=2, celestial_chance=0.4,
)

THEME_NEBULA = BackgroundTheme(
    name="星云",
    layer_configs=[
        (50, 1, 2, 0.3, 40, 100, (200, 150, 255)),
        (30, 1, 3, 0.6, 60, 140, (255, 200, 150)),
        (20, 2, 4, 1.0, 100, 200, (255, 180, 100)),
    ],
    overlay_color=(30, 10, 40), overlay_alpha=20,
    accent_color=(200, 150, 255),
    nebula_count=4, celestial_chance=0.7,
)

THEME_RED_ALERT = BackgroundTheme(
    name="警戒",
    layer_configs=[
        (30, 1, 1, 0.3, 40, 80, (180, 60, 60)),
        (20, 1, 2, 0.6, 60, 120, (220, 80, 80)),
        (10, 2, 3, 1.0, 80, 180, (255, 100, 50)),
    ],
    overlay_color=(40, 0, 0), overlay_alpha=25,
    accent_color=(255, 80, 80),
    nebula_count=5, celestial_chance=0.2,
)

LEVEL_THEMES = [
    (1, THEME_STARFIELD),
    (4, THEME_NEBULA),
    (7, THEME_RED_ALERT),
]


def get_theme_for_level(level):
    theme = THEME_STARFIELD
    for threshold, t in LEVEL_THEMES:
        if level >= threshold:
            theme = t
    return theme


# ═══════════════════════════════════════════════════════════════════
# 主背景类
# ═══════════════════════════════════════════════════════════════════

class ScrollingBackground:
    """多层视差背景 + 关卡主题 + ⭐ 动态元素。"""

    def __init__(self):
        self._layers = []
        self._overlay = None
        self._current_theme = THEME_STARFIELD
        self._transition_progress = 1.0
        self._prev_layers = []
        self._prev_overlay = None
        self._time = 0.0  # 累计时间（用于动画）

        # ⭐ 动态元素
        self._nebula_clouds: list[NebulaCloud] = []
        self._shooting_stars: list[ShootingStar] = []
        self._celestial_body: CelestialBody | None = None

        self._layers = self._build_from_theme(THEME_STARFIELD)
        self._overlay = self._make_overlay(THEME_STARFIELD)
        self._init_dynamic(THEME_STARFIELD)

    def _init_dynamic(self, theme: BackgroundTheme):
        """根据主题初始化动态元素。"""
        self._nebula_clouds = [NebulaCloud() for _ in range(theme.nebula_count)]
        self._shooting_stars = [ShootingStar() for _ in range(2)]
        self._celestial_body = CelestialBody(theme.accent_color)

    def _build_from_theme(self, theme):
        layers = []
        for cfg in theme.layer_configs:
            count, min_size, max_size, speed_factor, min_bright, max_bright = cfg[:6]
            color_hint = cfg[6] if len(cfg) > 6 else None
            layer = []
            layer_speed = BACKGROUND_BASE_SPEED * speed_factor
            for _ in range(count):
                x = random.uniform(0, SCREEN_WIDTH)
                y = random.uniform(0, SCREEN_HEIGHT)
                size = random.randint(min_size, max_size)
                brightness = random.randint(min_bright, max_bright)
                star = Star(x, y, size, layer_speed, brightness)
                if color_hint:
                    br = brightness / 255.0
                    star.color = tuple(min(255, int(c * br)) for c in color_hint)
                layer.append(star)
            layers.append(layer)
        return layers

    def _make_overlay(self, theme):
        if theme.overlay_alpha <= 0:
            return None
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        surf.fill((*theme.overlay_color, theme.overlay_alpha))
        return surf

    def _pulse_overlay(self):
        """叠加层呼吸脉冲 — 随时间轻微变化透明度。"""
        if self._overlay is None:
            return None
        pulse = 0.85 + 0.15 * math.sin(self._time * 0.5)
        alpha = max(0, self._current_theme.overlay_alpha)
        pulsed = int(alpha * pulse)
        if pulsed == alpha:
            return self._overlay
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        surf.fill((*self._current_theme.overlay_color, pulsed))
        return surf

    def set_theme_by_level(self, level):
        new_theme = get_theme_for_level(level)
        if new_theme is self._current_theme:
            return False
        self._prev_layers = self._layers
        self._prev_overlay = self._overlay
        self._current_theme = new_theme
        self._layers = self._build_from_theme(new_theme)
        self._overlay = self._make_overlay(new_theme)
        self._transition_progress = 0.0
        # ⭐ 重新初始化动态元素
        self._init_dynamic(new_theme)
        return True

    def update(self, dt):
        self._time += dt

        # 主题过渡
        if self._transition_progress < 1.0:
            self._transition_progress = min(1.0, self._transition_progress + dt * 0.5)
            for layer in self._prev_layers:
                for star in layer:
                    star.update(dt)
        else:
            self._prev_layers.clear()

        # 星星
        for layer in self._layers:
            for star in layer:
                star.update(dt)

        # ⭐ 星云云团
        for cloud in self._nebula_clouds:
            cloud.update(dt, self._time)

        # ⭐ 流星
        for star in self._shooting_stars:
            star.update(dt)

        # ⭐ 天体
        if self._celestial_body:
            self._celestial_body.update(dt)

    def draw(self, screen):
        # 星星 — 过渡期混合绘制
        if self._transition_progress < 1.0 and self._prev_layers:
            for layer in self._prev_layers:
                for star in layer:
                    alpha = int(255 * (1.0 - self._transition_progress))
                    if alpha > 0:
                        orig = star.color
                        star.color = tuple(int(c * alpha / 255) for c in orig)
                        star.draw(screen)
                        star.color = orig
            for layer in self._layers:
                for star in layer:
                    alpha = int(255 * self._transition_progress)
                    if alpha > 0:
                        orig = star.color
                        star.color = tuple(int(c * alpha / 255) for c in orig)
                        star.draw(screen)
                        star.color = orig
        else:
            for layer in self._layers:
                for star in layer:
                    star.draw(screen)

        # ⭐ 星云云团（在星星之上、天体之下）
        for cloud in self._nebula_clouds:
            cloud.draw(screen, self._time)

        # ⭐ 天体
        if self._celestial_body:
            self._celestial_body.draw(screen)

        # ⭐ 流星（最上层）
        for star in self._shooting_stars:
            star.draw(screen)

        # ⭐ 呼吸脉冲叠加层
        pulsed = self._pulse_overlay()
        if pulsed:
            screen.blit(pulsed, (0, 0))

    def draw_rect(self, screen, rect):
        """脏矩形局部擦除 — 只画星星（动态元素由全屏渲染处理）。"""
        clip = rect.clip(screen.get_rect())
        if clip.width <= 0 or clip.height <= 0:
            return
        screen.fill(BLACK, clip)
        layers = []
        if self._transition_progress < 1.0 and self._prev_layers:
            layers.extend(self._prev_layers)
        layers.extend(self._layers)
        for layer in layers:
            for star in layer:
                sr = pygame.Rect(
                    int(star.x) - star.size, int(star.y) - star.size,
                    star.size * 2, star.size * 2,
                )
                if sr.colliderect(clip):
                    star.draw(screen)

    @property
    def current_theme(self):
        return self._current_theme


class BackgroundCallback:
    def __init__(self, bg: ScrollingBackground):
        self._bg = bg

    def __call__(self, surface, rect):
        self._bg.draw_rect(surface, rect)
