"""
==============================================================================
飞机大战 — 子弹精灵类（题6：子弹系统）
==============================================================================
继承 pygame.sprite.Sprite，实现：
  1. 速度、伤害、来源（玩家/敌人）属性
  2. 子弹向上（玩家）或向下（敌人）移动
  3. 飞出屏幕边界后自动 kill() 回收
  4. 独立子弹精灵组管理

设计原则：
  - 一个 Bullet 类同时服务玩家和敌人，通过 source 和 direction 区分
  - 子弹速度使用 Delta-Time 驱动（px/s），与帧率解耦
"""

from enum import Enum
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    PLAYER_BULLET_SPEED, PLAYER_BULLET_DAMAGE,
    PLAYER_BULLET_WIDTH, PLAYER_BULLET_HEIGHT,
    ENEMY_BULLET_SPEED, ENEMY_BULLET_DAMAGE,
    ENEMY_BULLET_WIDTH, ENEMY_BULLET_HEIGHT,
    LAYER_BULLET,
    YELLOW, RED, ORANGE, WHITE, CYAN,
)


class BulletSource(Enum):
    """子弹来源枚举"""
    PLAYER = "player"   # 玩家发射（向上飞行）
    ENEMY = "enemy"     # 敌机发射（向下飞行）


# ==========================================================================
# 子弹图像生成（程序化，无需外部资源）
# ==========================================================================

def _create_player_bullet_image() -> pygame.Surface:
    """
    生成玩家子弹图像。
    ————————————————————————————————
    外形：亮黄色细长光束（4×14像素）
    带有中央高亮核心和尾部渐变。
    """
    w, h = PLAYER_BULLET_WIDTH, PLAYER_BULLET_HEIGHT
    surface: pygame.Surface = pygame.Surface((w, h), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))

    # 主体：黄色矩形（略圆角效果用两个矩形叠加模拟）
    pygame.draw.rect(surface, YELLOW, (0, 0, w, h - 4))
    # 尾部：橙色小三角（子弹尾部火焰感）
    pygame.draw.polygon(
        surface, ORANGE,
        [(0, h - 4), (w, h - 4), (w // 2, h)]
    )
    # 中央高亮线（白色）
    pygame.draw.line(surface, WHITE, (w // 2, 1), (w // 2, h - 6), width=1)

    return surface


def _create_enemy_bullet_image() -> pygame.Surface:
    """
    生成敌人子弹图像。
    ————————————————————————————————
    外形：红色圆形（8×8像素），带有发光边缘。
    """
    w, h = ENEMY_BULLET_WIDTH, ENEMY_BULLET_HEIGHT
    surface: pygame.Surface = pygame.Surface((w, h), pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))

    center: tuple = (w // 2, h // 2)
    # 外发光（暗红）
    pygame.draw.circle(surface, (180, 30, 30), center, w // 2)
    # 主体（亮红）
    pygame.draw.circle(surface, RED, center, w // 2 - 1)
    # 高光核心（橙白）
    pygame.draw.circle(surface, ORANGE, center, w // 4)

    return surface


# 预生成图像（共用，避免每颗子弹重复创建 Surface）
_PLAYER_BULLET_IMAGE: pygame.Surface | None = None
_ENEMY_BULLET_IMAGE: pygame.Surface | None = None


def _get_player_bullet_image() -> pygame.Surface:
    """惰性获取玩家子弹图像（首次调用时生成并缓存）"""
    global _PLAYER_BULLET_IMAGE
    if _PLAYER_BULLET_IMAGE is None:
        _PLAYER_BULLET_IMAGE = _create_player_bullet_image()
    return _PLAYER_BULLET_IMAGE


def _get_enemy_bullet_image() -> pygame.Surface:
    """惰性获取敌人子弹图像（首次调用时生成并缓存）"""
    global _ENEMY_BULLET_IMAGE
    if _ENEMY_BULLET_IMAGE is None:
        _ENEMY_BULLET_IMAGE = _create_enemy_bullet_image()
    return _ENEMY_BULLET_IMAGE


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
    ) -> None:
        """
        创建子弹实例。
        ————————————————————————————————
        参数：
            x, y      : 发射起始坐标（子弹中心点）
            source    : 来源（PLAYER / ENEMY），自动选择图像和参数
            direction : 飞行方向，-1 向上（默认），+1 向下
            speed     : 自定义速度（None 则使用默认值）
            damage    : 自定义伤害（None 则使用默认值）
        """
        super().__init__()

        self.layer: int = LAYER_BULLET
        self.dirty: int = 2  # 子弹每帧都移动，始终重绘

        # ---- 来源与方向 ----
        self.source: BulletSource = source
        self.direction: int = direction  # -1 = 上, +1 = 下

        # ---- 图像（按来源选择） ----
        if source == BulletSource.PLAYER:
            self.image: pygame.Surface = _get_player_bullet_image()
            self.speed: float = speed if speed is not None else PLAYER_BULLET_SPEED
            self.damage: int = damage if damage is not None else PLAYER_BULLET_DAMAGE
        else:
            self.image = _get_enemy_bullet_image()
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
        ————————————————————————————————
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
    ) -> "Bullet":
        """
        创建玩家子弹（向上飞行）。
        ————————————————————————————————
        参数：
            x, y     : 发射起始坐标
            damage   : 自定义伤害（None=默认值）
            piercing : 是否穿透敌人
        """
        bullet = cls(x=x, y=y, source=BulletSource.PLAYER, direction=-1,
                    damage=damage)
        bullet.piercing = piercing
        return bullet

    @classmethod
    def create_enemy_bullet(cls, x: float, y: float) -> "Bullet":
        """
        创建敌人子弹（向下飞行）。
        ————————————————————————————————
        参数：
            x, y : 发射起始坐标（通常为敌机底部中心）
        """
        return cls(x=x, y=y, source=BulletSource.ENEMY, direction=+1)
