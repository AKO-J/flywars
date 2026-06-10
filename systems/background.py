"""
==============================================================================
飞机大战 — 无限滚动背景系统（题5：背景动画）
==============================================================================
实现多层视差星空背景，营造飞机持续前进的视觉效果。

技术要点：
  1. 视差滚动（Parallax Scrolling）：3层星星以不同速度移动，营造深度感
  2. Delta-Time 驱动：所有速度单位 = 像素/秒，乘以 dt 后与 FPS 解耦
  3. 无限循环：星星移出屏幕底部 → 回收至顶部，随机重置 x 坐标
  4. 程序化生成：随机大小/亮度/位置，无需美术资源
"""

import random
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
    ) -> None:
        """
        参数：
            x, y       : 初始坐标（float 支持亚像素精度）
            size       : 半径（像素）
            speed      : 滚动速度（像素/秒）
            brightness : 亮度（0-255），用于灰度颜色
        """
        self.x: float = x
        self.y: float = y
        self.size: int = size
        self.speed: float = speed
        # 灰度颜色 = (b, b, b)，亮度决定深浅
        self.color: tuple[int, int, int] = (brightness, brightness, brightness)

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
        # 小星星（size=1）直接用单点，性能更好
        if self.size <= 1:
            screen.set_at((int(self.x), int(self.y)), self.color)
        else:
            pygame.draw.circle(
                screen, self.color, (int(self.x), int(self.y)), self.size
            )


class ScrollingBackground:
    """
    多层视差滚动星空背景。
    ————————————————————————————————
    管理多个星层，每层有独立的：
      - 星星数量
      - 尺寸范围（决定圆半径）
      - 滚动速度系数（×基准速度 = 实际速度 px/s）
      - 亮度范围（决定灰度值）

    调用流程：
      bg = ScrollingBackground()
      while running:
          dt = clock.tick(FPS) / 1000.0
          bg.update(dt)
          bg.draw(screen)
    """

    def __init__(self) -> None:
        """根据配置生成所有星层"""
        self._layers: list[list[Star]] = []

        for count, min_size, max_size, speed_factor, min_bright, max_bright in BACKGROUND_LAYERS:
            layer: list[Star] = []
            # 该层的实际速度 = 基准速度 × 速度系数
            layer_speed: float = BACKGROUND_BASE_SPEED * speed_factor

            for _ in range(count):
                x: float = random.uniform(0, SCREEN_WIDTH)
                y: float = random.uniform(0, SCREEN_HEIGHT)
                size: int = random.randint(min_size, max_size)
                brightness: int = random.randint(min_bright, max_bright)
                layer.append(Star(x, y, size, layer_speed, brightness))

            self._layers.append(layer)

    def update(self, dt: float) -> None:
        """
        更新所有星层。
        ————————————————————————————————
        dt : float — 距上一帧的时间间隔（秒）

        每层所有星星以各自 speed × dt 向下移动。
        由于每层的 speed 不同（远层慢、近层快），
        自然产生视差（parallax）深度效果。
        """
        for layer in self._layers:
            for star in layer:
                star.update(dt)

    def draw(self, screen: pygame.Surface) -> None:
        """绘制所有星层到屏幕上"""
        for layer in self._layers:
            for star in layer:
                star.draw(screen)

    def draw_rect(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        """仅绘制与指定 rect 相交的星星（用于脏矩形局部擦除）。

        对于小 rect（精灵擦除），先 fill black 再重绘相交星星。
        由于星星每帧全局滚动，clip rect 保证不写到 rect 外部。
        """
        clip = rect.clip(screen.get_rect())
        if clip.width <= 0 or clip.height <= 0:
            return
        screen.fill(BLACK, clip)
        for layer in self._layers:
            for star in layer:
                sr = pygame.Rect(
                    int(star.x) - star.size,
                    int(star.y) - star.size,
                    star.size * 2,
                    star.size * 2,
                )
                if sr.colliderect(clip):
                    star.draw(screen)


class BackgroundCallback:
    """可调用包装器，供 LayeredDirty.clear() 的 bgd 参数使用。"""

    def __init__(self, bg: ScrollingBackground) -> None:
        self._bg = bg

    def __call__(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        self._bg.draw_rect(surface, rect)
