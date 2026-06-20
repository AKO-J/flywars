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
    BACKGROUND_BASE_SPEED,
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
            # ⭐ 大星星加柔光（缓存，不每帧重建）
            if self.size >= 5:
                if not hasattr(self, '_glow_surf'):
                    gs = self.size * 3
                    self._glow_surf = pygame.Surface((gs, gs), pygame.SRCALPHA)
                    for i in range(gs // 2, 0, -1):
                        a = max(1, 15 - i)
                        if a > 0:
                            pygame.draw.circle(self._glow_surf, (*self.color[:3], a),
                                             (gs // 2, gs // 2), i // 2)
                screen.blit(self._glow_surf, (int(self.x) - self._glow_surf.get_width() // 2,
                                              int(self.y) - self._glow_surf.get_height() // 2))


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
    """天体 — 3种类型，不同深度，带弧度轨迹，从各个方向掠过。"""

    TYPES = ("gas_giant", "rocky", "ringed")

    def __init__(self, theme_color, depth=0):
        """depth: 0=近(大/快), 1=中, 2=远(小/慢)"""
        self.depth = depth
        depth_factor = {0: 1.0, 1: 0.65, 2: 0.4}[depth]
        self.body_type = random.choice(self.TYPES)
        self.radius = int(random.randint(25, 55) * depth_factor)
        self.radius = max(self.radius, 12)
        self.active = False
        self.appear_timer = random.uniform(3, 12) * (1 + depth * 0.5)
        self.rotation = 0.0
        self.rot_speed = random.uniform(0.2, 0.8) * (1.5 - depth * 0.3)
        self.fade_in = 0.0
        self.fade_out = 0.0
        self._last_color = theme_color
        self._surf = None
        self._build(theme_color)
        # ⭐ 弧度轨迹参数
        self._curve_amp = 0.0       # 弧度振幅
        self._curve_freq = 0.0      # 弧度频率
        self._travel_dist = 0.0     # 累计行进距离

    def _build(self, base):
        r = self.radius
        s = pygame.Surface((r * 4, r * 4), pygame.SRCALPHA)
        cx, cy = r * 2, r * 2
        base = base or (200, 180, 150)

        if self.body_type == "gas_giant":
            bands = [base,
                     (min(255, base[0]+50), max(0, base[1]-20), base[2]),
                     (max(0, base[0]-20), min(255, base[1]+50), base[2])]
            for y in range(-r, r):
                bw = int((r*r - y*y)**0.5) if abs(y) < r else 0
                if bw < 2: continue
                c = bands[(y + r) * len(bands) // (r * 2) % len(bands)]
                wob = random.randint(-1, 1)
                pygame.draw.line(s, c, (cx-bw+wob, cy+y), (cx+bw+wob, cy+y), max(2, r//10))
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

        for i in range(5, 0, -1):
            a = max(1, 18 - i*3)
            gc = (min(255, base[0]+30), min(255, base[1]+30),
                  min(255, base[2]+50), a)
            pygame.draw.circle(s, gc, (cx, cy), r + i*5, 2)

        hl = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(hl, (255, 255, 255, 30), (r, r), r)
        s.blit(hl, (cx-r, cy-r))
        self._surf = s

    def reset(self, color=None):
        """从随机方向进入，带随机弧度。"""
        dirs = ["left", "right", "top", "bottom",
                "topleft", "topright", "bottomleft", "bottomright"]
        entry = random.choice(dirs)
        m = self.radius * 3
        margin = random.uniform(-m, m)

        if entry == "left":
            self.x, self.y = -m, random.uniform(0, SCREEN_HEIGHT)
            self.vx, self.vy = random.uniform(30, 80), random.uniform(-20, 20)
        elif entry == "right":
            self.x, self.y = SCREEN_WIDTH+m, random.uniform(0, SCREEN_HEIGHT)
            self.vx, self.vy = random.uniform(-80, -30), random.uniform(-20, 20)
        elif entry == "top":
            self.x, self.y = random.uniform(0, SCREEN_WIDTH), -m
            self.vx, self.vy = random.uniform(-15, 15), random.uniform(30, 80)
        elif entry == "bottom":
            self.x, self.y = random.uniform(0, SCREEN_WIDTH), SCREEN_HEIGHT+m
            self.vx, self.vy = random.uniform(-15, 15), random.uniform(-80, -30)
        elif "left" in entry:
            self.x, self.y = -m, -m if "top" in entry else SCREEN_HEIGHT+m
            self.vx, self.vy = random.uniform(40, 100), random.uniform(30, 60) * (1 if "top" in entry else -1)
        else:  # right variants
            self.x, self.y = SCREEN_WIDTH+m, -m if "top" in entry else SCREEN_HEIGHT+m
            self.vx, self.vy = random.uniform(-100, -40), random.uniform(30, 60) * (1 if "top" in entry else -1)

        # ⭐ 根据不同深度缩放速度
        depth_speed = {0: 1.0, 1: 0.7, 2: 0.45}[self.depth]
        self.vx *= depth_speed
        self.vy *= depth_speed

        # ⭐ 弧度轨迹：小幅正弦摆动
        self._curve_amp = random.uniform(10, 40) * depth_speed
        self._curve_freq = random.uniform(0.5, 2.0)
        self._travel_dist = 0.0

        self.rotation = 0.0
        self.fade_in = 0.0
        self.fade_out = 0.0

    def update(self, dt):
        if not self.active:
            self.appear_timer -= dt
            if self.appear_timer <= 0:
                self.active = True
                self.body_type = random.choice(self.TYPES)
                self.radius = int(random.uniform(20, 50) * {0:1.0, 1:0.65, 2:0.4}[self.depth])
                self.radius = max(self.radius, 10)
                self._build(self._last_color)
                self.reset(self._last_color)
            return

        # ⭐ 弧度轨迹
        speed = (self.vx**2 + self.vy**2)**0.5
        self._travel_dist += speed * dt
        curve_offset = math.sin(self._travel_dist * self._curve_freq * 0.01) * self._curve_amp
        angle = math.atan2(self.vy, self.vx)
        perp_x = -math.sin(angle) * curve_offset * dt
        perp_y = math.cos(angle) * curve_offset * dt

        self.x += (self.vx + perp_x) * dt
        self.y += (self.vy + perp_y) * dt
        self.rotation += self.rot_speed * dt

        # 淡入
        if self.fade_in < 1.0:
            self.fade_in = min(1.0, self.fade_in + dt * 1.5)
        # 接近边缘时淡出
        m = self.radius * 3
        edge_dist = min(
            self.x + m if self.vx < 0 else SCREEN_WIDTH + m - self.x,
            self.y + m if self.vy < 0 else SCREEN_HEIGHT + m - self.y,
        )
        if edge_dist < 100:
            self.fade_out = min(1.0, self.fade_out + dt * 2.5)
        # 完全出屏后重置
        if (self.x < -m*3 or self.x > SCREEN_WIDTH+m*3
                or self.y < -m*3 or self.y > SCREEN_HEIGHT+m*3):
            self.active = False
            self.appear_timer = random.uniform(4, 15) * (1 + self.depth * 0.5)

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
# 主题定义 → levels/themes.py
# ═══════════════════════════════════════════════════════════════════

from levels.themes import (
    BackgroundTheme,
    THEME_STARFIELD, THEME_NEBULA, THEME_RED_ALERT,
    LEVEL_THEMES, get_theme_for_level,
)

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
        self._celestial_bodies: list[CelestialBody] = []

        self._layers = self._build_from_theme(THEME_STARFIELD)
        self._overlay = self._make_overlay(THEME_STARFIELD)
        self._init_dynamic(THEME_STARFIELD)

    def _init_dynamic(self, theme):
        self._nebula_clouds = [NebulaCloud() for _ in range(theme.nebula_count)]
        self._shooting_stars = [ShootingStar() for _ in range(2)]
        # ⭐ 多天体：3-4 个不同深度
        self._celestial_bodies = [
            CelestialBody(theme.accent_color, depth=0)
        ]  # ⭐ 只1个天体，省性能

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
        for body in self._celestial_bodies:
            body.update(dt)

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
        for body in self._celestial_bodies:
            body.draw(screen)

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
