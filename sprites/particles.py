"""
==============================================================================
飞机大战 — 粒子特效系统
==============================================================================
轻量级粒子引擎，不依赖 pygame.Sprite，纯数学更新 + 直接渲染。

粒子类型预设：
  - engine_trail   : 玩家引擎尾焰（持续喷射）
  - burst          : 爆炸迸溅碎片（一次性爆发）
  - hit_spark      : 子弹命中火花（微型爆发）
  - boss_death     : Boss 死亡大爆发
  - pickup_glow    : 道具拾取光晕
  - level_up_ring  : 升级扩散环
"""

import math
import random
import pygame
from settings import SCREEN_WIDTH, SCREEN_HEIGHT


# ==========================================================================
# 粒子数据类
# ==========================================================================

class Particle:
    """单颗粒子 — 纯数据，不继承 Sprite。"""

    __slots__ = (
        "x", "y", "vx", "vy",
        "lifetime", "max_lifetime",
        "size", "start_size",
        "color", "end_color",
        "gravity", "friction",
        "rotation", "rot_speed",
        "shape",  # "circle" | "rect" | "spark"
    )

    def __init__(
        self,
        x: float, y: float,
        vx: float, vy: float,
        lifetime: float,
        size: int = 3,
        color: tuple = (255, 255, 255),
        end_color: tuple | None = None,
        gravity: float = 0.0,
        friction: float = 1.0,
        rotation: float = 0.0,
        rot_speed: float = 0.0,
        shape: str = "circle",
    ) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.lifetime = lifetime
        self.max_lifetime = lifetime
        self.size = size
        self.start_size = size
        self.color = color
        self.end_color = end_color or color
        self.gravity = gravity
        self.friction = friction
        self.rotation = rotation
        self.rot_speed = rot_speed
        self.shape = shape

    @property
    def alive(self) -> bool:
        return self.lifetime > 0

    @property
    def progress(self) -> float:
        """0.0 = 刚出生, 1.0 = 即将消亡"""
        if self.max_lifetime <= 0:
            return 1.0
        return 1.0 - self.lifetime / self.max_lifetime

    @property
    def current_color(self) -> tuple:
        """在 start_color → end_color 之间插值。"""
        p = self.progress
        # 支持 RGBA
        ca = self.color + (255,) * (4 - len(self.color))
        cb = self.end_color + (255,) * (4 - len(self.end_color))
        return (
            int(ca[0] + (cb[0] - ca[0]) * p),
            int(ca[1] + (cb[1] - ca[1]) * p),
            int(ca[2] + (cb[2] - ca[2]) * p),
            int(ca[3] + (cb[3] - ca[3]) * p),
        )

    @property
    def current_size(self) -> float:
        """粒子大小随生命衰减（线性缩小）。"""
        return self.start_size * (1.0 - self.progress * 0.7)

    def update(self, dt: float) -> None:
        """更新一帧的位置与状态。"""
        self.lifetime -= dt
        if self.lifetime <= 0:
            return
        self.vx *= self.friction
        self.vy *= self.friction
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.rotation += self.rot_speed * dt

    def draw(self, screen: pygame.Surface) -> None:
        """渲染粒子到屏幕上。"""
        if not self.alive:
            return
        screen_x = int(self.x)
        screen_y = int(self.y)
        size = max(1, int(self.current_size))

        # 屏幕裁剪
        if (screen_x < -size * 2 or screen_x > SCREEN_WIDTH + size * 2
                or screen_y < -size * 2 or screen_y > SCREEN_HEIGHT + size * 2):
            return

        color = self.current_color
        alpha = color[3] if len(color) >= 4 else 255
        if alpha <= 0:
            return

        if self.shape == "spark" and size >= 2:
            # 细长火花的旋转矩形
            # 用一条线段替代
            cos_a = math.cos(self.rotation)
            sin_a = math.sin(self.rotation)
            length = size * 3
            sx = int(screen_x - cos_a * length)
            sy = int(screen_y - sin_a * length)
            pygame.draw.line(
                screen, color[:3], (sx, sy),
                (screen_x, screen_y), max(1, size // 2)
            )
        elif self.shape == "rect":
            r = pygame.Rect(0, 0, size, size)
            r.center = (screen_x, screen_y)
            s = pygame.Surface((size, size), pygame.SRCALPHA)
            s.fill(color)
            screen.blit(s, r)
        else:
            # 圆形（默认）
            pygame.draw.circle(screen, color[:3], (screen_x, screen_y), size)


# ==========================================================================
# 粒子发射器
# ==========================================================================

class ParticleEmitter:
    """
    粒子发射器 — 管理粒子池，支持持续喷射和一次性爆发。

    用法:
      emitter = ParticleEmitter()
      # 一次性爆发
      emitter.burst(x, y, count=20, ...)
      # 持续喷射（开关控制）
      emitter.set_engine(state=True, x, y)
      # 每帧调用
      emitter.update(dt)
      emitter.draw(screen)
    """

    MAX_PARTICLES: int = 500  # 粒子池上限

    def __init__(self) -> None:
        self._particles: list[Particle] = []
        # 引擎尾焰状态
        self._engine_active: bool = False
        self._engine_x: float = 0.0
        self._engine_y: float = 0.0
        self._engine_timer: float = 0.0

    # ================================================================
    # 爆发预设
    # ================================================================

    def burst(
        self,
        x: float, y: float,
        count: int = 15,
        speed: float = 150.0,
        colors: list[tuple] | None = None,
        lifetime: float = 0.6,
        size_range: tuple[int, int] = (2, 5),
        gravity: float = 30.0,
        spread: float = 2 * math.pi,  # 全方向
    ) -> None:
        """通用爆发 — 从 (x,y) 向各方向喷射粒子。"""
        if colors is None:
            colors = [(255, 200, 50), (255, 120, 20), (255, 60, 10)]
        for _ in range(count):
            if len(self._particles) >= self.MAX_PARTICLES:
                break
            angle = random.uniform(0, spread)
            spd = random.uniform(speed * 0.3, speed)
            sz = random.randint(*size_range)
            color = random.choice(colors)
            end_c = (color[0] // 3, color[1] // 4, color[2] // 2)
            self._particles.append(Particle(
                x, y,
                math.cos(angle) * spd,
                math.sin(angle) * spd,
                random.uniform(lifetime * 0.5, lifetime),
                size=sz, color=color, end_color=end_c,
                gravity=gravity, friction=0.96,
                rotation=random.uniform(0, math.pi * 2),
                rot_speed=random.uniform(-4, 4),
            ))

    def burst_explosion(self, x: float, y: float, size: str = "normal") -> None:
        """敌机爆炸 — 根据尺寸决定粒子数量和速度。"""
        params = {
            "spark":  {"count": 8,  "speed": 100, "size": (1, 3), "lt": 0.4},
            "normal": {"count": 20, "speed": 160, "size": (2, 4), "lt": 0.6},
            "big":    {"count": 35, "speed": 220, "size": (2, 6), "lt": 0.8},
            "huge":   {"count": 60, "speed": 300, "size": (3, 8), "lt": 1.2},
        }
        p = params.get(size, params["normal"])
        colors = [(255, 230, 80), (255, 150, 30), (255, 80, 20),
                   (255, 50, 10), (255, 200, 150)]
        self.burst(x, y, count=p["count"], speed=p["speed"],
                   colors=colors, lifetime=p["lt"],
                   size_range=p["size"], gravity=20)
        # 少量火星（更亮、更快、无重力）
        spark_colors = [(255, 255, 200), (255, 255, 255)]
        self.burst(x, y, count=int(p["count"] * 0.3), speed=p["speed"] * 1.5,
                   colors=spark_colors, lifetime=p["lt"] * 0.4,
                   size_range=(1, 2), gravity=0, spread=math.pi * 2)

    def hit_spark(self, x: float, y: float, intensity: str = "normal") -> None:
        """子弹命中火花 — 微型爆发。"""
        count = 5 if intensity == "normal" else 10
        self.burst(x, y, count=count, speed=80, gravity=0, lifetime=0.25,
                   colors=[(255, 255, 180), (255, 200, 100), (200, 200, 255)],
                   size_range=(1, 2), spread=math.pi * 2)

    def boss_death(self, x: float, y: float) -> None:
        """Boss 死亡大爆发 — 大量彩色粒子 + 烟雾。"""
        # 主爆发 1：橘红色
        self.burst(x, y, count=40, speed=350, gravity=15, lifetime=1.0,
                   colors=[(255, 180, 30), (255, 100, 20), (255, 50, 10)],
                   size_range=(3, 8))
        # 主爆发 2：白色亮星
        self.burst(x, y, count=20, speed=400, gravity=0, lifetime=0.5,
                   colors=[(255, 255, 255), (255, 255, 200)],
                   size_range=(1, 3), spread=math.pi * 2)
        # 烟雾：灰黑色、慢速、大颗
        self.burst(x, y, count=15, speed=60, gravity=-10, lifetime=1.5,
                   colors=[(60, 60, 60), (40, 40, 40), (80, 80, 80)],
                   size_range=(5, 12), spread=math.pi * 2)

    def pickup_glow(self, x: float, y: float, color: tuple = (100, 255, 100)) -> None:
        """道具拾取光晕 — 环形扩散。"""
        self.burst(x, y, count=12, speed=120, gravity=0, lifetime=0.4,
                   colors=[color, (255, 255, 255)],
                   size_range=(2, 4), spread=math.pi * 2)

    def level_up_ring(self, x: float, y: float) -> None:
        """升级光环 — 向四周扩散的环形粒子。"""
        n = 24
        colors = [(0, 200, 255), (100, 255, 255), (255, 255, 255)]
        for i in range(n):
            if len(self._particles) >= self.MAX_PARTICLES:
                break
            angle = 2 * math.pi * i / n
            spd = random.uniform(100, 180)
            self._particles.append(Particle(
                x, y,
                math.cos(angle) * spd,
                math.sin(angle) * spd,
                lifetime=0.7,
                size=random.randint(2, 4),
                color=random.choice(colors),
                end_color=(0, 100, 180, 0),
                gravity=0, friction=0.95,
                shape="rect",
            ))

    # ================================================================
    # 持续引擎尾焰
    # ================================================================

    def set_engine(self, active: bool, x: float = 0, y: float = 0) -> None:
        """开启/关闭引擎尾焰，并更新喷射口位置。"""
        self._engine_active = active
        if active:
            self._engine_x = x
            self._engine_y = y

    def _update_engine(self, dt: float) -> None:
        """每帧生成引擎尾焰粒子。"""
        if not self._engine_active:
            return
        self._engine_timer += dt
        # 每帧产生 2-3 颗粒子
        spawn_rate = 25  # 粒子/秒
        to_spawn = int(self._engine_timer * spawn_rate)
        if to_spawn <= 0:
            return
        self._engine_timer -= to_spawn / spawn_rate

        for _ in range(min(to_spawn, 5)):
            if len(self._particles) >= self.MAX_PARTICLES:
                break
            vx = random.uniform(-20, 20)
            vy = random.uniform(80, 180)  # 向下喷射
            sz = random.randint(2, 5)
            self._particles.append(Particle(
                self._engine_x + random.uniform(-10, 10),
                self._engine_y + random.uniform(-5, 5),
                vx, vy,
                lifetime=random.uniform(0.2, 0.5),
                size=sz,
                color=(100, 180, 255, 200),
                end_color=(0, 50, 150, 0),
                gravity=-10,  # 微微上升（反重力）
                friction=0.95,
            ))

    # ================================================================
    # 每帧更新 & 渲染
    # ================================================================

    def update(self, dt: float) -> None:
        """更新所有粒子 + 引擎尾焰生成。"""
        self._update_engine(dt)
        for p in self._particles:
            p.update(dt)
        self._particles = [p for p in self._particles if p.alive]

    def draw(self, screen: pygame.Surface) -> None:
        """渲染所有粒子。"""
        for p in self._particles:
            p.draw(screen)

    @property
    def count(self) -> int:
        return len(self._particles)
