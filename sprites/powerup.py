"""
==============================================================================
飞机大战 — 道具精灵类（题18：道具系统）
==============================================================================
从被击毁敌机位置随机掉落，缓慢下落，玩家拾取后触发对应效果。

道具类型：
  - 即时型：HEALTH（+1HP）、BOMB（清屏爆炸）
  - 持续型：DOUBLE_DAMAGE / TRIPLE_SPREAD / PIERCE / RAPID_FIRE（8秒）
"""
import math
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    POWERUP_SIZE, POWERUP_FALL_SPEED, POWERUP_PULSE_SPEED,
    POWERUP_LIFETIME, POWERUP_COLORS,
    LAYER_POWERUP,
    WHITE, BLACK,
    PowerUpType,
)


# ==========================================================================
# 程序化道具图像（惰性缓存，所有实例共享）
# ==========================================================================
_cache: dict[PowerUpType, pygame.Surface] = {}


def _get_powerup_image(ptype: PowerUpType) -> pygame.Surface:
    if ptype not in _cache:
        _cache[ptype] = _create_powerup_image(ptype)
    return _cache[ptype]


def _create_powerup_image(ptype: PowerUpType) -> pygame.Surface:
    s = POWERUP_SIZE
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    cx = cy = s // 2
    r = s // 2 - 3
    color = POWERUP_COLORS.get(ptype, (255, 255, 255))

    if ptype == PowerUpType.HEALTH:
        # 绿色圆形背景 + 白色十字
        pygame.draw.circle(surf, (0, 150, 40), (cx, cy), r)
        pygame.draw.circle(surf, color, (cx, cy), r - 2)
        cw = 3
        pygame.draw.rect(surf, WHITE, (cx - 7, cy - cw // 2, 14, cw))
        pygame.draw.rect(surf, WHITE, (cx - cw // 2, cy - 7, cw, 14))

    elif ptype == PowerUpType.BOMB:
        # 金色菱形 + 内嵌星形
        diamond = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
        pygame.draw.polygon(surf, (180, 130, 0), diamond)
        inner_r = r - 5
        inner = [(cx, cy - inner_r), (cx + inner_r, cy), (cx, cy + inner_r), (cx - inner_r, cy)]
        pygame.draw.polygon(surf, color, inner)
        # 中心亮点
        pygame.draw.circle(surf, WHITE, (cx, cy), 4)

    elif ptype == PowerUpType.DOUBLE_DAMAGE:
        # 红色向上箭头/三角形
        tri = [(cx, cy - r + 2), (cx - r + 2, cy + r - 2), (cx + r - 2, cy + r - 2)]
        pygame.draw.polygon(surf, (150, 30, 30), tri)
        inner_tri = [(cx, cy - r + 7), (cx - r + 7, cy + r - 7), (cx + r - 7, cy + r - 7)]
        pygame.draw.polygon(surf, color, inner_tri)
        # x2 文字（白色短线模拟，因为中文ttf渲染英文数字较小）
        pygame.draw.line(surf, WHITE, (cx - r // 2, cy + r // 2 - 2), (cx - r // 2 + 4, cy + r // 2 + 3), 2)
        pygame.draw.line(surf, WHITE, (cx + r // 2 - 4, cy + r // 2 - 2), (cx + r // 2, cy + r // 2 + 3), 2)

    elif ptype == PowerUpType.TRIPLE_SPREAD:
        # 青色扇形三线
        pygame.draw.circle(surf, (0, 120, 160), (cx, cy), r)
        pygame.draw.circle(surf, color, (cx, cy), r - 2)
        # 三条发散线
        for angle_deg in (-25, 0, 25):
            rad = math.radians(angle_deg - 90)  # 从圆心向上发散
            ex = cx + (r - 5) * math.cos(rad)
            ey = cy + (r - 5) * math.sin(rad)
            pygame.draw.line(surf, WHITE, (cx, cy), (ex, ey), 2)

    elif ptype == PowerUpType.PIERCE:
        # 蓝色箭矢穿透效果
        pygame.draw.circle(surf, (60, 60, 160), (cx, cy), r)
        pygame.draw.circle(surf, color, (cx, cy), r - 2)
        # 水平穿透箭头
        arrow_y = cy
        pygame.draw.line(surf, WHITE, (cx - r + 4, arrow_y), (cx + r - 4, arrow_y), 3)
        # 箭头尖端
        tip_x = cx + r - 4
        pygame.draw.polygon(surf, WHITE,
                           [(tip_x, arrow_y), (tip_x - 6, arrow_y - 5), (tip_x - 6, arrow_y + 5)])

    elif ptype == PowerUpType.RAPID_FIRE:
        # 橙色闪电/加速符号
        pygame.draw.circle(surf, (180, 90, 0), (cx, cy), r)
        pygame.draw.circle(surf, color, (cx, cy), r - 2)
        # 双闪电符号
        pts = [
            (cx + 2, cy - r + 4),
            (cx - 6, cy - 2),
            (cx - 1, cy - 2),
            (cx - 6, cy + r - 4),
            (cx + 4, cy + 1),
            (cx - 2, cy + 1),
        ]
        pygame.draw.polygon(surf, WHITE, pts)


    return surf


# ==========================================================================
# PowerUp 精灵类
# ==========================================================================

class PowerUp(pygame.sprite.DirtySprite):
    """
    道具精灵。
    ————————————————————————————————
    从敌机死亡位置生成，缓慢下落，带脉冲动画。
    玩家拾取后触发对应效果并 kill()。
    """

    def __init__(self, x: float, y: float, ptype: PowerUpType) -> None:
        super().__init__()
        self.powerup_type: PowerUpType = ptype
        self._x: float = x
        self._y: float = y
        self._age: float = 0.0

        self._base_image: pygame.Surface = _get_powerup_image(ptype)
        self.image: pygame.Surface = self._base_image
        self.rect: pygame.Rect = self.image.get_rect(center=(int(x), int(y)))

        self.layer: int = LAYER_POWERUP
        self.dirty: int = 1

    def update(self, dt: float = 0.0, *args, **kwargs) -> None:
        if dt <= 0:
            dt = 1.0 / 60.0
        self._age += dt

        # 下落
        self._y += POWERUP_FALL_SPEED * dt
        self.rect.centery = int(self._y)

        # 脉冲动画：大小在 ±10% 间波动
        scale = 1.0 + 0.10 * math.sin(self._age * POWERUP_PULSE_SPEED * 2.0 * math.pi)
        w = max(4, int(POWERUP_SIZE * scale))
        h = max(4, int(POWERUP_SIZE * scale))
        self.image = pygame.transform.scale(self._base_image, (w, h))
        center = self.rect.center
        self.rect = self.image.get_rect()
        self.rect.center = center
        self.dirty = 1  # 图像变了，标记脏矩形（否则 LayeredDirty 第二帧起跳过绘制）

        # 越界/超时回收
        if self.rect.top > SCREEN_HEIGHT + 20 or self._age > POWERUP_LIFETIME:
            self.kill()
