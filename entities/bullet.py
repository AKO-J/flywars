"""
==============================================================================
飞机大战 — 子弹精灵类（增强版：三种蓄力等级 + 四种敌机子弹样式）
==============================================================================
继承 pygame.sprite.Sprite，实现：
  1. 速度、伤害、来源（玩家/敌人）属性
  2. 子弹向上（玩家）或向下（敌人）移动
  3. 飞出屏幕边界后自动 kill() 回收
  4. 独立子弹精灵组管理
  5. ⭐ 蓄力等级视觉区分（单发/双发/三发不同子弹外观）
  6. ⭐ 敌机类型子弹不同颜色（普通/快速/精英/追踪）

设计原则：
  - 一个 Bullet 类同时服务玩家和敌人，通过 source 和 direction 区分
  - 子弹速度使用 Delta-Time 驱动（px/s），与帧率解耦
  - 所有子弹图像程序化生成（无需外部资源）
"""

from enum import Enum
import math
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    PLAYER_BULLET_SPEED, PLAYER_BULLET_DAMAGE,
    PLAYER_BULLET_WIDTH, PLAYER_BULLET_HEIGHT,
    ENEMY_BULLET_SPEED, ENEMY_BULLET_DAMAGE,
    ENEMY_BULLET_WIDTH, ENEMY_BULLET_HEIGHT,
    LAYER_BULLET,
    YELLOW, RED, ORANGE, WHITE, CYAN, BLUE, GREEN,
)


class BulletSource(Enum):
    """子弹来源枚举"""
    PLAYER = "player"   # 玩家发射（向上飞行）
    ENEMY = "enemy"     # 敌机发射（向下飞行）


# ==========================================================================
# 玩家子弹图像生成（三种蓄力等级）
# ==========================================================================

def _create_player_bullet_single() -> pygame.Surface:
    """
    单发子弹：蓝白能量尖晶
    ──────────────────────────
    菱形蓝色晶体，带白色高亮核心和淡蓝光晕
    """
    w, h = PLAYER_BULLET_WIDTH, PLAYER_BULLET_HEIGHT
    surf = pygame.Surface((w + 4, h + 4), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    cx, cy = (w + 4) // 2, (h + 4) // 2

    # 外层光晕
    for r in range(8, 4, -2):
        alpha = 30 // (9 - r) if r > 4 else 10
        pygame.draw.circle(surf, (60, 180, 255, alpha), (cx, cy), r)

    # 菱形主体
    pts = [(cx, cy - 7), (cx + 3, cy), (cx, cy + 7), (cx - 3, cy)]
    pygame.draw.polygon(surf, (80, 200, 255), pts)       # 外层
    pts2 = [(cx, cy - 5), (cx + 2, cy), (cx, cy + 5), (cx - 2, cy)]
    pygame.draw.polygon(surf, (180, 230, 255), pts2)     # 内层
    # 核心高亮
    pygame.draw.circle(surf, WHITE, (cx, cy - 1), 2)

    return surf


def _create_player_bullet_double() -> pygame.Surface:
    """
    双发子弹：金色双翼飞弹
    ──────────────────────────
    两枚金色菱形弹头，略向外倾斜，带橙色尾迹
    """
    w, h = PLAYER_BULLET_WIDTH, PLAYER_BULLET_HEIGHT
    surf = pygame.Surface((w + 8, h + 4), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    base_cx, cy = (w + 8) // 2, (h + 4) // 2

    offsets = [-5, 5]  # 左右弹头偏移
    for offset in offsets:
        cx = base_cx + offset
        # 光晕
        pygame.draw.circle(surf, (255, 180, 60, 25), (cx, cy), 6)
        # 菱形弹头
        pts = [(cx, cy - 6), (cx + 3, cy), (cx, cy + 6), (cx - 3, cy)]
        pygame.draw.polygon(surf, (255, 200, 50), pts)
        # 内层
        pts2 = [(cx, cy - 4), (cx + 2, cy), (cx, cy + 4), (cx - 2, cy)]
        pygame.draw.polygon(surf, (255, 240, 150), pts2)
        # 核心高亮
        pygame.draw.circle(surf, WHITE, (cx, cy - 1), 2)
        # 尾迹
        pygame.draw.circle(surf, (255, 120, 0, 100), (cx, cy + 5), 2)

    return surf


def _create_player_bullet_triple() -> pygame.Surface:
    """
    三发子弹：赤炎三叉戟
    ──────────────────────────
    三枚红橙色火球，中间略靠前，带动态火焰尾迹
    """
    w, h = 7, 9  # 略大于基础尺寸
    surf = pygame.Surface((w + 14, h + 6), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    base_cx, cy = (w + 14) // 2, (h + 6) // 2

    # 中间弹头（稍靠前）
    positions = [(base_cx, cy - 8), (base_cx - 6, cy), (base_cx + 6, cy)]
    sizes = [4, 3, 3]  # 中间大、两边小

    for (cx, cy_pos), size in zip(positions, sizes):
        # 外层火焰光晕（红橙渐变）
        for r in range(size + 4, size, -1):
            alpha = max(10, 35 - r * 3)
            pygame.draw.circle(surf, (255, 80, 20, alpha), (cx, cy_pos), r)
        # 主体火球
        pygame.draw.circle(surf, (255, 100, 30), (cx, cy_pos), size)
        pygame.draw.circle(surf, (255, 180, 60), (cx, cy_pos), size - 1)
        # 核心白热
        pygame.draw.circle(surf, (255, 255, 200), (cx - 1, cy_pos - 1), 2)
        # 尾焰
        for i in range(3):
            ty = cy_pos + size + 2 + i * 2
            ta = max(20, 60 - i * 15)
            tr = max(1, size - i)
            pygame.draw.circle(surf, (255, 60, 0, ta), (cx, ty), tr)

    return surf


# ==========================================================================
# 敌人子弹图像生成（四种敌机样式）
# ==========================================================================

def _create_enemy_normal_bullet() -> pygame.Surface:
    """普通敌机子弹：暗红小圆弹"""
    s = 8
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    c = s // 2
    pygame.draw.circle(surf, (180, 40, 40), (c, c), c)
    pygame.draw.circle(surf, (220, 60, 60), (c, c), c - 1)
    pygame.draw.circle(surf, (255, 100, 80), (c - 1, c - 1), 2)
    return surf


def _create_enemy_fast_bullet() -> pygame.Surface:
    """快速敌机子弹：橙色椭圆弹"""
    s = 10
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    c = s // 2
    pygame.draw.ellipse(surf, (200, 100, 30), (1, 2, s - 2, s - 4))
    pygame.draw.ellipse(surf, (255, 160, 50), (2, 3, s - 4, s - 6))
    pygame.draw.circle(surf, (255, 220, 120), (c, c - 1), 2)
    return surf


def _create_enemy_elite_bullet() -> pygame.Surface:
    """精英敌机子弹：紫色光环弹（稍大，带环）"""
    s = 12
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    c = s // 2
    # 外光环
    pygame.draw.circle(surf, (120, 40, 180, 60), (c, c), c, width=2)
    pygame.draw.circle(surf, (160, 60, 220, 80), (c, c), c - 2, width=1)
    # 核心
    pygame.draw.circle(surf, (180, 80, 240), (c, c), 3)
    pygame.draw.circle(surf, (220, 160, 255), (c - 1, c - 1), 2)
    return surf


def _create_enemy_tracking_bullet() -> pygame.Surface:
    """追踪敌机子弹：粉红追踪弹（带导向尾迹）"""
    s = 10
    surf = pygame.Surface((s, s), pygame.SRCALPHA)
    surf.fill((0, 0, 0, 0))
    c = s // 2
    # 外圈
    pygame.draw.circle(surf, (200, 50, 120), (c, c), c)
    pygame.draw.circle(surf, (255, 80, 160), (c, c), c - 1)
    # 核心
    pygame.draw.circle(surf, (255, 180, 220), (c - 1, c - 1), 2)
    # 尾迹星点
    for i in range(4):
        angle = math.pi * 2 * i / 4
        dx, dy = int(math.cos(angle) * 3), int(math.sin(angle) * 3)
        pygame.draw.circle(surf, (255, 100, 180, 80), (c + dx, c + dy), 1)
    return surf


# ==========================================================================
# 缓存与获取函数
# ==========================================================================

_PLAYER_BULLET_IMAGES: dict[str, pygame.Surface] | None = None
_ENEMY_BULLET_IMAGES: dict[str, pygame.Surface] | None = None


def _get_player_bullet_image(style: str = "single") -> pygame.Surface:
    """
    获取玩家子弹图像。
    style: "single" | "double" | "triple"
    """
    global _PLAYER_BULLET_IMAGES
    if _PLAYER_BULLET_IMAGES is None:
        _PLAYER_BULLET_IMAGES = {
            "single": _create_player_bullet_single(),
            "double": _create_player_bullet_double(),
            "triple": _create_player_bullet_triple(),
        }
    return _PLAYER_BULLET_IMAGES.get(style, _PLAYER_BULLET_IMAGES["single"])


def _get_enemy_bullet_image(style: str = "normal") -> pygame.Surface:
    """
    获取敌人子弹图像。
    style: "normal" | "fast" | "elite" | "tracking"
    """
    global _ENEMY_BULLET_IMAGES
    if _ENEMY_BULLET_IMAGES is None:
        _ENEMY_BULLET_IMAGES = {
            "normal": _create_enemy_normal_bullet(),
            "fast": _create_enemy_fast_bullet(),
            "elite": _create_enemy_elite_bullet(),
            "tracking": _create_enemy_tracking_bullet(),
        }
    return _ENEMY_BULLET_IMAGES.get(style, _ENEMY_BULLET_IMAGES["normal"])


# ==========================================================================
# Bullet 精灵类
# ==========================================================================

class Bullet(pygame.sprite.DirtySprite):
    """
    子弹精灵
    ————————————————————————————————
    属性：
      - speed      : 移动速度（像素/秒）
      - damage     : 造成的伤害值
      - source     : 来源（BulletSource.PLAYER 或 .ENEMY）
      - direction  : 飞行方向（-1=上, +1=下）
      - style      : 子弹样式名（决定图像外观）

    生命周期：
      创建 → 每帧 update() 移动 → 飞出屏幕 → 自动 kill() 从精灵组移除
    """

    def __init__(
        self,
        x: float,
        y: float,
        source: BulletSource,
        direction: int = -1,
        speed: float | None = None,
        damage: int | None = None,
        style: str | None = None,
    ) -> None:
        """
        创建子弹实例。
        ────────────────────────────────────────
        参数：
            x, y      : 发射起始坐标（子弹中心点）
            source    : 来源（PLAYER / ENEMY），自动选择图像和参数
            direction : 飞行方向，-1 向上（默认），+1 向下
            speed     : 自定义速度（None 则使用默认值）
            damage    : 自定义伤害（None 则使用默认值）
            style     : 子弹样式（玩家: single/double/triple, 敌机: normal/fast/elite/tracking）
                        None 则根据 source 自动选择默认样式
        """
        super().__init__()

        self.layer: int = LAYER_BULLET
        self.dirty: int = 2  # 子弹每帧都移动，始终重绘

        # ---- 来源与方向 ----
        self.source: BulletSource = source
        self.direction: int = direction  # -1 = 上, +1 = 下
        self.style: str = style or ("single" if source == BulletSource.PLAYER else "normal")

        # ---- 图像（按来源+样式选择） ----
        if source == BulletSource.PLAYER:
            self.image: pygame.Surface = _get_player_bullet_image(self.style)
            self.speed: float = speed if speed is not None else PLAYER_BULLET_SPEED
            self.damage: int = damage if damage is not None else PLAYER_BULLET_DAMAGE
        else:
            self.image = _get_enemy_bullet_image(self.style)
            self.speed = speed if speed is not None else ENEMY_BULLET_SPEED
            self.damage = damage if damage is not None else ENEMY_BULLET_DAMAGE

        # 碰撞矩形 ----
        self.rect: pygame.Rect = self.image.get_rect()
        # 使用 float 坐标支持亚像素精度（dt 驱动必需）
        self.rect.centerx = int(x)
        self.rect.centery = int(y)
        self._x: float = x
        self._y: float = y

        # 自定义速度（Boss 弹幕使用）
        self._vx: float = 0.0
        self._vy: float = 0.0
        self._custom_velocity: bool = False
        # 穿透弹：不因命中敌机而销毁（题18：PIERCE 道具）
        self.piercing: bool = False
        self._hit_enemies: set[int] = set()

    def update(self, dt: float = 0.0, *args, **kwargs) -> None:
        """
        每帧更新：按速度与方向移动子弹，检测越界自动清除。
        ────────────────────────────────────────
        dt : float — Delta-Time（秒），0 时降级为帧驱动（向后兼容）

        移动公式：
          - 普通子弹：y += speed × direction × dt
          - 自定义速度子弹（_custom_velocity=True）：x += _vx × dt, y += _vy × dt

        越界条件：完全离开屏幕四边即回收。
        """
        if dt <= 0:
            dt = 1.0 / 60.0

        if self._custom_velocity:
            self._x += self._vx * dt
            self._y += self._vy * dt
        else:
            self._y += self.speed * self.direction * dt

        self.rect.centerx = int(self._x)
        self.rect.centery = int(self._y)

        # 飞出屏幕 → 自动回收
        if (self.rect.bottom < 0 or self.rect.top > SCREEN_HEIGHT or
                self.rect.right < 0 or self.rect.left > SCREEN_WIDTH):
            self.kill()

    # ===================================================================
    # 便捷工厂方法
    # ===================================================================

    @classmethod
    def create_player_bullet(
        cls, x: float, y: float,
        damage: int | None = None,
        piercing: bool = False,
        style: str = "single",
    ) -> "Bullet":
        """
        创建玩家子弹（向上飞行）。
        ────────────────────────────────────────
        参数：
            x, y     : 发射起始坐标
            damage   : 自定义伤害（None=默认值）
            piercing : 是否穿透敌人
            style    : 子弹样式（single/double/triple）
        """
        bullet = cls(x=x, y=y, source=BulletSource.PLAYER, direction=-1,
                    damage=damage, style=style)
        bullet.piercing = piercing
        return bullet

    @classmethod
    def create_enemy_bullet(
        cls, x: float, y: float,
        style: str = "normal",
    ) -> "Bullet":
        """
        创建敌人子弹（向下飞行）。
        ────────────────────────────────────────
        参数：
            x, y  : 发射起始坐标（通常为敌机底部中心）
            style : 子弹样式（normal/fast/elite/tracking）
        """
        return cls(x=x, y=y, source=BulletSource.ENEMY, direction=+1, style=style)
