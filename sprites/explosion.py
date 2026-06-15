"""
==============================================================================
飞机大战 — 爆炸特效精灵类（题11：爆炸特效与帧动画）
==============================================================================
帧动画驱动的爆炸效果，子弹命中或玩家撞击时触发。

设计：
  - 16帧逐帧动画，每帧持续3个游戏tick（60fps下约50ms）
  - 帧图像类级别惰性缓存，所有实例共享，避免重复生成
  - 动画播放完毕自动 kill()，从精灵组移除
  - 独立精灵组管理，不参与子弹/敌机碰撞检测
  - 支持三种尺寸：normal(48px)、big(72px)、huge(100px)
"""

import math
import random
import pygame
from settings import (
    EXPLOSION_FRAME_COUNT, EXPLOSION_FRAME_TICKS,
    LAYER_EXPLOSION,
)


class Explosion(pygame.sprite.DirtySprite):
    """
    爆炸帧动画精灵。
    ————————————————————————————————
    生成流程：
      1. 在命中/撞击位置创建 Explosion 实例
      2. 每帧 update() 推进动画帧
      3. 最后一帧播放完毕后自动 kill()

    不影响碰撞逻辑：爆炸只存在于 all_sprites，不在 bullets/enemies 组中。

    尺寸等级：
      "normal" (48px) — 普通/快速敌机
      "big"    (72px) — 精英/追踪敌机
      "huge"   (100px) — Boss
    """

    # 类级别帧缓存（按尺寸分别缓存）
    _frame_cache: dict[str, list[pygame.Surface]] = {}

    def __init__(self, center_x: float, center_y: float, size: str = "normal") -> None:
        super().__init__()
        self._size = size
        if size not in Explosion._frame_cache:
            Explosion._frame_cache[size] = self._generate_frames(size)

        self._frames: list[pygame.Surface] = Explosion._frame_cache[size]
        self._frame_index: int = 0
        self._tick_counter: int = 0
        self.image: pygame.Surface = self._frames[0]
        self.rect: pygame.Rect = self.image.get_rect()
        self.rect.center = (int(center_x), int(center_y))
        self.layer: int = LAYER_EXPLOSION
        self.dirty: int = 1

    def update(self, dt: float = 0.0, *args, **kwargs) -> None:
        """每帧推进动画，播放完毕后自动移除。"""
        self._tick_counter += 1
        if self._tick_counter >= EXPLOSION_FRAME_TICKS:
            self._tick_counter = 0
            self._frame_index += 1
            if self._frame_index >= len(self._frames):
                self.kill()
                return
            self.image = self._frames[self._frame_index]
            self.dirty = 1  # 帧切换 → 标记脏矩形

    # ==================================================================
    # 帧图像生成（程序化，分别缓存不同尺寸）
    # ==================================================================

    @staticmethod
    def _generate_frames(size_name: str) -> list[pygame.Surface]:
        """
        生成16帧爆炸动画。
        ————————————————————————————————
        size_name: "normal"(48), "big"(72), "huge"(100)
        动画阶段：
          帧 0-3   : 中心白/黄色闪光，快速扩大
          帧 2-10  : 橙红色扩展环
          帧 2-15  : 多色散射粒子向外飞溅
          帧 8-15  : 暗色尾烟消散
        """
        size_map = {"spark": 20, "normal": 48, "big": 72, "huge": 100}
        render_size: int = size_map.get(size_name, 48)
        half: float = render_size / 2.0
        n: int = EXPLOSION_FRAME_COUNT

        frames: list[pygame.Surface] = []
        for i in range(n):
            surf: pygame.Surface = pygame.Surface((render_size, render_size), pygame.SRCALPHA)
            progress: float = i / (n - 1)  # 0.0 → 1.0

            # ---- 阶段1：中心闪光（前25%帧） ----
            if progress < 0.25:
                fp: float = progress / 0.25
                flash_alpha: int = int(255 * (1.0 - fp))
                flash_radius: int = int(half * 0.35 * (0.2 + 0.8 * fp))
                pygame.draw.circle(
                    surf, (255, 255, 200, flash_alpha),
                    (int(half), int(half)), flash_radius + 5
                )
                pygame.draw.circle(
                    surf, (255, 255, 255, min(255, flash_alpha + 80)),
                    (int(half), int(half)), max(2, flash_radius)
                )

            # ---- 阶段2：扩展环（10%-65%帧） ----
            if 0.1 < progress < 0.65:
                rp: float = (progress - 0.1) / 0.55
                ring_r: int = int(half * 0.08 + half * 0.48 * rp)
                ring_alpha: int = int(220 * (1.0 - rp))
                if ring_alpha > 0 and ring_r > 2:
                    pygame.draw.circle(
                        surf, (255, 160, 30, ring_alpha),
                        (int(half), int(half)), ring_r, width=max(3, int(render_size / 16))
                    )
                    if ring_r > 10:
                        pygame.draw.circle(
                            surf, (255, 210, 100, ring_alpha // 2),
                            (int(half), int(half)), ring_r - 5, width=1
                        )

            # ---- 阶段3：散射粒子（全程，含颜色变化） ----
            num_particles: int = 18 if render_size >= 72 else (12 if render_size >= 48 else 8)
            for j in range(num_particles):
                angle: float = j * 2.0 * math.pi / num_particles + progress * 1.3
                dist: float = progress * half * 0.92
                px: float = half + math.cos(angle) * dist
                py: float = half + math.sin(angle) * dist
                pa: int = int(255 * (1.0 - progress * 0.85))
                pr: int = max(1, int(4.5 * (1.0 - progress * 0.6))) if render_size >= 72 else max(1, int(3.5 * (1.0 - progress * 0.6)))
                if j % 3 == 0:
                    color = (255, 210, 70, pa)
                elif j % 3 == 1:
                    color = (255, 110, 40, pa)
                else:
                    color = (255, 255, 190, pa)
                pygame.draw.circle(surf, color, (int(px), int(py)), pr)

            # ---- 阶段4：尾烟消散（50%-100%帧） ----
            if progress > 0.5:
                sp: float = (progress - 0.5) / 0.5
                smoke_alpha: int = int(70 * (1.0 - sp))
                if smoke_alpha > 0:
                    rng = random.Random(i * 37 + 1)
                    for _ in range(8 if render_size >= 72 else 6):
                        sx: float = half + rng.uniform(-0.55, 0.55) * half * sp * 1.3
                        sy: float = half + rng.uniform(-0.55, 0.55) * half * sp * 1.3
                        sr: float = rng.uniform(1.5, 5.0) * (1.0 - sp * 0.5)
                        pygame.draw.circle(
                            surf, (50, 50, 50, smoke_alpha),
                            (int(sx), int(sy)), int(sr)
                        )

            frames.append(surf)

        return frames
