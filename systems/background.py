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


class Star:
    __slots__ = ("x", "y", "size", "speed", "color", "_base_color", "_phase", "_twinkle_speed")

    def __init__(self, x, y, size, speed, brightness, color=(0, 0, 0)):
        self.x, self.y = x, y
        self.size, self.speed = size, speed
        self.color = color if color != (0, 0, 0) else (brightness,) * 3
        self._base_color = self.color
        self._phase = random.uniform(0, math.pi * 2)  # 闪烁相位
        self._twinkle_speed = random.uniform(1.5, 4.0)  # 闪烁速度

    def update(self, dt):
        self.y += self.speed * dt
        if self.y > SCREEN_HEIGHT + self.size:
            self.y = -self.size
            self.x = random.uniform(0, SCREEN_WIDTH)
            # 重置时随机颜色（部分星星带色调）
            if random.random() < 0.15:
                hue = random.choice([
                    (180, 200, 255),  # 蓝白
                    (255, 200, 180),  # 橙黄
                    (200, 180, 255),  # 紫
                    (255, 180, 180),  # 红
                ])
                self._base_color = hue
            else:
                b = random.randint(100, 255)
                self._base_color = (b, b, b)

    def draw(self, screen):
        # 闪烁：大星星明显，小星星轻微
        if self.size >= 2:
            twinkle = 0.7 + 0.3 * math.sin(self._phase + pygame.time.get_ticks() * 0.001 * self._twinkle_speed)
            self.color = tuple(min(255, int(c * twinkle)) for c in self._base_color)
        else:
            self.color = self._base_color

        if self.size <= 1:
            screen.set_at((int(self.x), int(self.y)), self.color)
        else:
            pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), self.size)
            # ⭐ 大星星加柔光
            if self.size >= 3:
                glow_size = self.size * 4
                glow = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
                for i in range(self.size * 2, 0, -1):
                    a = max(1, int(18 - i * 1.5))
                    r2 = i // 2
                    if r2 > 0:
                        pygame.draw.circle(glow, (*self.color[:3], a),
                                         (self.size * 2, self.size * 2), r2)
                screen.blit(glow, (int(self.x) - self.size * 2, int(self.y) - self.size * 2))


# ═══════════════════════════════════════════════════════════════════
# 动态元素
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
        self._cached_surf = None
        self._build_surface()

    def _build_surface(self):
        r = self.radius
        surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        for i in range(r, 0, -1):
            a = int(self.alpha * (1.0 - i / r))
            if a <= 0:
                continue
            ratio = i / r
            c = tuple(min(255, int(cv * (0.3 + 0.7 * ratio))) for cv in self.color)
            pygame.draw.circle(surf, (*c, a), (r, r), i)
        self._cached_surf = surf
        self._cached_r = r

    def update(self, dt, time_s):
        self.x += self.speed_x * dt
        self.y += self.speed_y * dt
        m = -self.radius - 50
        if self.x > SCREEN_WIDTH + 50: self.x = m
        elif self.x < m: self.x = SCREEN_WIDTH + 50
        if self.y > SCREEN_HEIGHT + 50: self.y = m
        elif self.y < m: self.y = SCREEN_HEIGHT + 50

    def draw(self, screen, time_s):
        pulse = 0.7 + 0.3 * math.sin(time_s * self.pulse_speed + self.pulse_offset)
        r = int(self.radius * pulse)
        if r <= 0 or self._cached_surf is None:
            return
        scale = r / self._cached_r
        if abs(scale - 1.0) > 0.05:
            s = pygame.transform.scale(self._cached_surf,
                (int(self._cached_surf.get_width() * scale),
                 int(self._cached_surf.get_height() * scale)))
        else:
            s = self._cached_surf
        screen.blit(s, (int(self.x) - s.get_width() // 2, int(self.y) - s.get_height() // 2))


class ShootingStar:
    """流星 — 快速划过屏幕的亮线。"""

    def __init__(self):
        self.reset()
        self.timer = random.uniform(2, 8)

    def reset(self):
        self.active = False
        self.timer = random.uniform(3, 10)
        self.x = random.uniform(0, SCREEN_WIDTH * 0.7)
        self.y = random.uniform(-30, SCREEN_HEIGHT * 0.3)
        self.speed = random.uniform(400, 700)
        self.angle = random.uniform(0.4, 0.9)
        self.length = random.randint(40, 100)
        self.brightness = random.randint(180, 255)
        self.lifetime = random.uniform(0.15, 0.4)

    def update(self, dt):
        if not self.active:
            self.timer -= dt
            if self.timer <= 0:
                self.active = True
                self.age = 0.0
                self.x = random.uniform(0, SCREEN_WIDTH * 0.7)
                self.y = random.uniform(-30, SCREEN_HEIGHT * 0.3)
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
        for i in range(10):
            t = i / 10
            a = int(alpha * (1.0 - t))
            if a <= 0: continue
            sx = int(self.x - math.cos(self.angle) * self.length * t)
            sy = int(self.y - math.sin(self.angle) * self.length * t)
            sw = max(1, int(2 * (1.0 - t)))
            dot = pygame.Surface((sw * 2, sw * 2), pygame.SRCALPHA)
            pygame.draw.circle(dot, (255, 255, 255, a), (sw, sw), sw)
            screen.blit(dot, (sx - sw, sy - sw))


class CelestialBody:
    """天体 — 3种类型：气态巨行星/岩石卫星/带环行星，带自转和淡入淡出。"""

    TYPES = ("gas_giant", "rocky", "ringed")

    def __init__(self, theme_color):
        self.body_type = random.choice(self.TYPES)
        self.radius = random.randint(25, 50)
        self.active = False
        self.appear_timer = random.uniform(10, 25)
        self.rotation = 0.0
        self.rot_speed = random.uniform(0.3, 1.0)
        self.fade_in = 0.0
        self.fade_out = 0.0
        self._last_color = theme_color
        self._surf = None
        self._build(theme_color)

    def _build(self, base):
        r = self.radius
        s = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        cx, cy = r * 2, r * 2
        base = base or (200, 180, 150)

        if self.body_type == "gas_giant":
            # 气态巨行星：彩色条纹 + 极地暗区
            bands = [base,
                     (min(255, base[0]+50), max(0, base[1]-20), base[2]),
                     (max(0, base[0]-20), min(255, base[1]+50), base[2])]
            for y in range(-r, r):
                bw = int((r*r - y*y)**0.5) if abs(y) < r else 0
                if bw < 2: continue
                c = bands[(y + r) * len(bands) // (r * 2) % len(bands)]
                wob = random.randint(-1, 1)
                pygame.draw.line(s, c, (cx-bw+wob, cy+y), (cx+bw+wob, cy+y), 3)
            # 极地区域变暗
            for off, dr in [(0, -1), (r*2, 1)]:
                for i in range(r//3):
                    a = int(30 * (1 - i/(r//3)))
                    pygame.draw.circle(s, (0, 0, 0, a), (r, off + i*dr), r, 2)

        elif self.body_type == "rocky":
            gray = sum(base) // 3
            pygame.draw.circle(s, (gray,)*3, (cx, cy), r)
            random.seed(hash(tuple(base)) & 0xFFFF)
            for _ in range(random.randint(5, 10)):
                cx_ = random.randint(cx-r+6, cx+r-6)
                cy_ = random.randint(cy-r+6, cy+r-6)
                cr = random.randint(3, max(3, r//4))
                d = ((cx_-cx)**2 + (cy_-cy)**2)**0.5
                if d + cr > r: continue
                pygame.draw.circle(s, (max(0,gray-40),)*3, (cx_, cy_), cr)
                pygame.draw.circle(s, (min(255,gray+50),)*3, (cx_, cy_), cr, 1)

        elif self.body_type == "ringed":
            pygame.draw.circle(s, base, (cx, cy), r)
            for i in range(int(r*1.8), r, -1):
                a = max(1, int(22 * (1 - i/(r*1.8))))
                ew = int(i * 0.35)
                rs = pygame.Surface((i*2, ew*2), pygame.SRCALPHA)
                rc = (min(255, base[0]+70), min(255, base[1]+50),
                      min(255, base[2]+90), a)
                pygame.draw.ellipse(rs, rc, (0, 0, i*2, ew*2), 2)
                s.blit(rs, (cx-i, cy-ew))

        # 大气光晕
        for i in range(5, 0, -1):
            a = max(1, 18 - i*3)
            gc = (min(255, base[0]+30), min(255, base[1]+30),
                  min(255, base[2]+50), a)
            pygame.draw.circle(s, gc, (cx, cy), r + i*5, 2)

        # 高光
        hl = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(hl, (255, 255, 255, 30), (r, r), r)
        s.blit(hl, (cx-r, cy-r))
        self._surf = s

    def reset(self, color=None):
        side = random.choice(["left", "right", "top"])
        m = self.radius * 2
        if side == "left":
            self.x, self.y = -m, random.uniform(60, SCREEN_HEIGHT*0.3)
            self.vx, self.vy = random.uniform(4, 10), random.uniform(-0.5, 1.5)
        elif side == "right":
            self.x, self.y = SCREEN_WIDTH+m, random.uniform(60, SCREEN_HEIGHT*0.3)
            self.vx, self.vy = random.uniform(-10, -4), random.uniform(-0.5, 1.5)
        else:
            self.x, self.y = random.uniform(100, SCREEN_WIDTH-100), -m
            self.vx, self.vy = random.uniform(-2, 2), random.uniform(3, 8)
        self.rotation = 0.0
        self.fade_in = 0.0
        self.fade_out = 0.0
        self.rot_speed = random.uniform(0.3, 1.0)

    def update(self, dt):
        if not self.active:
            self.appear_timer -= dt
            if self.appear_timer <= 0:
                self.active = True
                self.body_type = random.choice(self.TYPES)
                self.radius = random.randint(25, 50)
                self._build(self._last_color)
                self.reset(self._last_color)
            return
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rotation += self.rot_speed * dt
        if self.fade_in < 1.0:
            self.fade_in = min(1.0, self.fade_in + dt * 1.2)
        m = self.radius * 3
        if self.x < -m+40 or self.x > SCREEN_WIDTH+m-40 or self.y < -m+40 or self.y > SCREEN_HEIGHT+m-40:
            self.fade_out = min(1.0, self.fade_out + dt * 2)
        if self.x < -m*2 or self.x > SCREEN_WIDTH+m*2 or self.y < -m*2 or self.y > SCREEN_HEIGHT+m*2:
            self.active = False
            self.appear_timer = random.uniform(15, 35)

    def draw(self, screen):
        if not self.active or self._surf is None:
            return
        a = 255
        if self.fade_in < 1.0: a = int(self.fade_in * 255)
        if self.fade_out > 0: a = int(a * (1.0 - self.fade_out))
        if a <= 0: return
        rotated = pygame.transform.rotate(self._surf, self.rotation * 57.3)
        rotated.set_alpha(a)
        screen.blit(rotated, rotated.get_rect(center=(int(self.x), int(self.y))))


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
        (60, 1, 2, 0.3, 60, 120, (180, 200, 255)),   # 原40→60
        (35, 2, 4, 0.6, 100, 170, (200, 220, 255)),   # 原25→35
        (20, 3, 6, 1.0, 150, 255, (255, 255, 255)),   # 原15→20
    ],
    overlay_color=(0, 0, 20), overlay_alpha=12,
    accent_color=(100, 180, 255),
    nebula_count=3, celestial_chance=0.5,  # 原2→3
)

THEME_NEBULA = BackgroundTheme(
    name="星云",
    layer_configs=[
        (70, 1, 3, 0.3, 40, 100, (200, 150, 255)),   # 原50→70
        (40, 2, 5, 0.6, 60, 140, (255, 200, 150)),   # 原30→40
        (25, 3, 7, 1.0, 100, 200, (255, 180, 100)),  # 原20→25
    ],
    overlay_color=(30, 10, 40), overlay_alpha=20,
    accent_color=(200, 150, 255),
    nebula_count=5, celestial_chance=0.8,  # 原4→5
)

THEME_RED_ALERT = BackgroundTheme(
    name="警戒",
    layer_configs=[
        (50, 1, 2, 0.3, 40, 80, (180, 60, 60)),     # 原30→50
        (30, 2, 4, 0.6, 60, 120, (220, 80, 80)),    # 原20→30
        (15, 3, 6, 1.0, 80, 180, (255, 100, 50)),   # 原10→15
    ],
    overlay_color=(40, 0, 0), overlay_alpha=25,
    accent_color=(255, 80, 80),
    nebula_count=6, celestial_chance=0.3,  # 原5→6
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
    def __init__(self):
        self._layers = []
        self._overlay = None
        self._current_theme = THEME_STARFIELD
        self._transition_progress = 1.0
        self._prev_layers = []
        self._prev_overlay = None
        self._time = 0.0

        self._nebula_clouds: list[NebulaCloud] = []
        self._shooting_stars: list[ShootingStar] = []
        self._celestial_body: CelestialBody | None = None

        self._layers = self._build_from_theme(THEME_STARFIELD)
        self._overlay = self._make_overlay(THEME_STARFIELD)
        self._init_dynamic(THEME_STARFIELD)

    def _init_dynamic(self, theme):
        self._nebula_clouds = [NebulaCloud() for _ in range(theme.nebula_count)]
        self._shooting_stars = [ShootingStar() for _ in range(2)]
        self._celestial_body = CelestialBody(theme.accent_color)

    def _build_from_theme(self, theme):
        layers = []
        for cfg in theme.layer_configs:
            count, min_size, max_size, sf, mb, Mb = cfg[:6]
            hint = cfg[6] if len(cfg) > 6 else None
            layer = []
            spd = BACKGROUND_BASE_SPEED * sf
            for _ in range(count):
                s = Star(random.uniform(0, SCREEN_WIDTH),
                         random.uniform(0, SCREEN_HEIGHT),
                         random.randint(min_size, max_size), spd,
                         random.randint(mb, Mb))
                if hint:
                    br = s.color[0] / 255.0
                    s.color = tuple(min(255, int(c * br)) for c in hint)
                layer.append(s)
            layers.append(layer)
        return layers

    def _make_overlay(self, theme):
        if theme.overlay_alpha <= 0:
            return None
        s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        s.fill((*theme.overlay_color, theme.overlay_alpha))
        return s

    def _pulse_overlay(self):
        if self._overlay is None:
            return None
        pulse = 0.85 + 0.15 * math.sin(self._time * 0.5)
        a = int(self._current_theme.overlay_alpha * pulse)
        if a == self._current_theme.overlay_alpha:
            return self._overlay
        s = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        s.fill((*self._current_theme.overlay_color, a))
        return s

    def set_theme_by_level(self, level):
        new = get_theme_for_level(level)
        if new is self._current_theme:
            return False
        self._prev_layers = self._layers
        self._prev_overlay = self._overlay
        self._current_theme = new
        self._layers = self._build_from_theme(new)
        self._overlay = self._make_overlay(new)
        self._transition_progress = 0.0
        self._init_dynamic(new)
        return True

    def update(self, dt):
        self._time += dt
        if self._transition_progress < 1.0:
            self._transition_progress = min(1.0, self._transition_progress + dt * 0.5)
            for layer in self._prev_layers:
                for star in layer:
                    star.update(dt)
        else:
            self._prev_layers.clear()
        for layer in self._layers:
            for star in layer:
                star.update(dt)
        for c in self._nebula_clouds:
            c.update(dt, self._time)
        for s in self._shooting_stars:
            s.update(dt)
        if self._celestial_body:
            self._celestial_body.update(dt)

    def draw(self, screen):
        # 星星 + 过渡
        if self._transition_progress < 1.0 and self._prev_layers:
            for layer in self._prev_layers:
                for star in layer:
                    a = int(255 * (1.0 - self._transition_progress))
                    if a <= 0: continue
                    orig = star.color
                    star.color = tuple(int(c * a / 255) for c in orig)
                    star.draw(screen)
                    star.color = orig
            for layer in self._layers:
                for star in layer:
                    a = int(255 * self._transition_progress)
                    if a <= 0: continue
                    orig = star.color
                    star.color = tuple(int(c * a / 255) for c in orig)
                    star.draw(screen)
                    star.color = orig
        else:
            for layer in self._layers:
                for star in layer:
                    star.draw(screen)

        # 星云
        for c in self._nebula_clouds:
            c.draw(screen, self._time)

        # 天体
        if self._celestial_body:
            self._celestial_body.draw(screen)

        # 流星
        for s in self._shooting_stars:
            s.draw(screen)

        # 呼吸叠加
        pulsed = self._pulse_overlay()
        if pulsed:
            screen.blit(pulsed, (0, 0))

    def draw_rect(self, screen, rect):
        clip = rect.clip(screen.get_rect())
        if clip.width <= 0 or clip.height <= 0:
            return
        screen.fill(BLACK, clip)
        layers = []
        if self._transition_progress < 1.0 and self._prev_layers:
            layers.extend(self._prev_layers)
        layers.extend(self._layers)
        for layer in layers:
            for s in layer:
                sr = pygame.Rect(int(s.x)-s.size, int(s.y)-s.size, s.size*2, s.size*2)
                if sr.colliderect(clip):
                    s.draw(screen)

    @property
    def current_theme(self):
        return self._current_theme


class BackgroundCallback:
    def __init__(self, bg):
        self._bg = bg
    def __call__(self, surface, rect):
        self._bg.draw_rect(surface, rect)
