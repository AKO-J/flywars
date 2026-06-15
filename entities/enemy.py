"""
==============================================================================
飞机大战 — 敌机精灵类（题9：多态移动模式）
==============================================================================
继承 pygame.sprite.Sprite，通过方法重写实现四种移动模式：

  移动模式          敌机类型        实现方式
  ──────────────── ─────────────── ──────────────────────────────
  直线下落          NormalEnemy     _move(): y += speed × dt
  斜向折返          FastEnemy       _move(): x±= diag_speed, 碰壁反弹
  正弦波            EliteEnemy      _move(): x = center + A·sin(f·y + φ)
  追踪玩家          TrackingEnemy   _move(): 向 player 位置线性插值

设计原则：
  - Enemy 基类定义 update() 流程，子类只重写 _move(dt)
  - 越界回收、rect 同步等公共逻辑在基类中统一处理
  - 追踪敌机通过构造函数接收玩家引用
"""

import random
import math
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    ENEMY_NORMAL_SPEED, ENEMY_NORMAL_HP, ENEMY_NORMAL_SCORE,
    ENEMY_NORMAL_WIDTH, ENEMY_NORMAL_HEIGHT,
    ENEMY_NORMAL_FIRE_INTERVAL,
    ENEMY_FAST_SPEED, ENEMY_FAST_HP, ENEMY_FAST_SCORE,
    ENEMY_FAST_WIDTH, ENEMY_FAST_HEIGHT, ENEMY_FAST_DIAGONAL_SPEED,
    ENEMY_FAST_FIRE_INTERVAL,
    ENEMY_ELITE_SPEED, ENEMY_ELITE_HP, ENEMY_ELITE_SCORE,
    ENEMY_ELITE_WIDTH, ENEMY_ELITE_HEIGHT,
    ENEMY_ELITE_WAVE_AMPLITUDE, ENEMY_ELITE_WAVE_FREQUENCY,
    ENEMY_ELITE_FIRE_INTERVAL, ENEMY_ELITE_BURST_COUNT, ENEMY_ELITE_BURST_INTERVAL,
    ENEMY_TRACKING_SPEED, ENEMY_TRACKING_HP, ENEMY_TRACKING_SCORE,
    ENEMY_TRACKING_WIDTH, ENEMY_TRACKING_HEIGHT,
    ENEMY_TRACKING_FIRE_INTERVAL,
    BOSS_HP, BOSS_SPEED, BOSS_SCORE, BOSS_WIDTH, BOSS_HEIGHT,
    BOSS_FIRE_INTERVAL_CIRCLE, BOSS_FIRE_INTERVAL_AIMED, BOSS_FIRE_INTERVAL_SPIRAL,
    BOSS_ENTER_DURATION, BOSS_PATROL_MARGIN, BOSS_BULLET_DAMAGE, BOSS_BULLET_SPEED,
    BOSS_FAN_COUNT, BOSS_FAN_ANGLE, BOSS_FAN_INTERVAL, BOSS_EXPLOSION_COUNT,
    DIFFICULTY_HP_SCALE, DIFFICULTY_FIRE_RATE_SCALE,
    LAYER_ENEMY, LAYER_BOSS, UI_FONT_PATH,
    ENEMY_NORMAL_IMAGE_PATH, ENEMY_FAST_IMAGE_PATH,
    ENEMY_ELITE_IMAGE_PATH, ENEMY_TRACKING_IMAGE_PATH,
    BOSS_IMAGE_PATH,
    RED, ORANGE, YELLOW, WHITE, DARK_GRAY, BLUE, CYAN, GREEN,
)
from utils.resource_manager import load_image
from entities.bullet import Bullet, BulletSource


# ==========================================================================
# 敌机图像加载（真实素材，惰性缓存）
# ==========================================================================

_cache: dict[str, pygame.Surface] = {}


def _cached_image(key: str, path: str, w: int, h: int) -> pygame.Surface:
    """加载并缓存敌机图像，自动缩放到目标尺寸。"""
    if key not in _cache:
        _cache[key] = load_image(path, width=w, height=h)
    return _cache[key]


def _get_normal_image() -> pygame.Surface:
    return _cached_image("normal", ENEMY_NORMAL_IMAGE_PATH,
                        ENEMY_NORMAL_WIDTH, ENEMY_NORMAL_HEIGHT)

def _get_fast_image() -> pygame.Surface:
    return _cached_image("fast", ENEMY_FAST_IMAGE_PATH,
                        ENEMY_FAST_WIDTH, ENEMY_FAST_HEIGHT)

def _get_elite_image() -> pygame.Surface:
    return _cached_image("elite", ENEMY_ELITE_IMAGE_PATH,
                        ENEMY_ELITE_WIDTH, ENEMY_ELITE_HEIGHT)

def _get_tracking_image() -> pygame.Surface:
    return _cached_image("tracking", ENEMY_TRACKING_IMAGE_PATH,
                        ENEMY_TRACKING_WIDTH, ENEMY_TRACKING_HEIGHT)


# ==========================================================================
# Enemy 抽象基类（题9 重构：多态移动）
# ==========================================================================

class Enemy(pygame.sprite.DirtySprite):
    """
    敌机抽象基类。
    ————————————————————————————————

    公共流程（update）：
      ① _move(dt)           — 子类重写，实现不同移动模式
      ② rect 同步            — float → int 坐标
      ③ 越界检测             — 超出屏幕底部自动 kill()
      ④ dirty = 1            — 标记脏矩形

    子类只需重写 _move(dt)，无需关心其他逻辑。
    """

    def __init__(
        self,
        image: pygame.Surface,
        x: float,
        y: float,
        speed: float,
        hp: int,
        score_value: int,
        fire_interval: float = 0.0,  # ⭐ 新增：射击间隔（0=不射击）
    ) -> None:
        super().__init__()
        self.image = image
        self.rect = image.get_rect()
        self.rect.centerx = int(x)
        self.rect.top = int(y)
        self._x: float = x
        self._y: float = y
        self.speed: float = speed
        self.hp: int = hp
        self.max_hp: int = hp
        self.score_value: int = score_value
        self.layer: int = LAYER_ENEMY
        self.dirty: int = 2  # 敌机每帧移动，始终重绘
        # ⭐ 射击系统
        self._fire_timer: float = 0.0
        self._fire_interval: float = fire_interval

    # ================================================================
    # 公共更新流程
    # ================================================================

    def update(self, dt: float = 0.0, *args, **kwargs) -> None:
        """
        每帧更新流程（模板方法）。
        """
        # ① 多态：调用子类的具体移动实现
        self._move(dt if dt > 0 else 1.0 / 60.0)

        # ② 同步 rect
        self.rect.centerx = int(self._x)
        self.rect.centery = int(self._y)

        # ③ 越界回收
        if self.rect.top > SCREEN_HEIGHT + 10:
            self.kill()

    # ================================================================
    # 移动钩子（子类重写）
    # ================================================================

    def _move(self, dt: float) -> None:
        """
        移动逻辑 — 子类必须重写。
        ————————————————————————————————
        参数：
            dt : float — Delta-Time（已保证 > 0）
        """
        raise NotImplementedError("子类必须重写 _move(dt)")

    # ================================================================
    # 伤害系统
    # ================================================================

    def take_damage(self, damage: int) -> bool:
        self.hp -= damage
        if self.hp <= 0:
            self.kill()
            return True
        return False

    # ================================================================
    # 射击系统（⭐ 新增：小怪也能发射弹幕）
    # ================================================================

    def fire(self, dt: float) -> list:
        """
        每帧更新射击计时器，返回本帧需要发射的子弹列表。
        ────────────────────────────────────────
        基类返回空列表（不射击），子类重写以实现具体弹幕。
        """
        if self._fire_interval <= 0:
            return []
        self._fire_timer += dt
        if self._fire_timer >= self._fire_interval:
            self._fire_timer -= self._fire_interval
            return self._do_fire()
        return []

    def _do_fire(self) -> list:
        """子类重写：生成子弹列表。"""
        return []


# ==========================================================================
# 具体敌机类型（四种移动模式）
# ==========================================================================

class NormalEnemy(Enemy):
    """
    普通敌机 — 直线下落 + 向下射击
    ————————————————————————————————
    模式：垂直向下匀速移动
    属性：150px/s | HP 2 | 得分 100
    射击：每 2.8 秒发射一枚向下子弹
    """

    def __init__(self, x: float | None = None, y: float | None = None,
                 fire_interval: float | None = None) -> None:
        if x is None:
            x = random.uniform(40, SCREEN_WIDTH - 40)
        if y is None:
            y = random.uniform(-80, -20)
        super().__init__(_get_normal_image(), x, y,
                         ENEMY_NORMAL_SPEED, ENEMY_NORMAL_HP, ENEMY_NORMAL_SCORE,
                         fire_interval=fire_interval or ENEMY_NORMAL_FIRE_INTERVAL)

    def _move(self, dt: float) -> None:
        """直线下落：仅 y 增加"""
        self._y += self.speed * dt

    def _do_fire(self) -> list:
        """发射一枚向下的普通子弹"""

        return [Bullet(
            self.rect.centerx, self.rect.bottom,
            BulletSource.ENEMY, direction=1,
            style="normal",
        )]


class FastEnemy(Enemy):
    """
    快速敌机 — 斜向折返 + 斜向射击
    ————————————————————————————————
    模式：水平方向匀速 + 垂直下落，碰壁反弹
    属性：280px/s ↓ | 120px/s ↔ | HP 1 | 得分 150
    射击：每 2.2 秒发射两枚斜向子弹
    """

    def __init__(self, x: float | None = None, y: float | None = None,
                 fire_interval: float | None = None) -> None:
        if x is None:
            x = random.uniform(30, SCREEN_WIDTH - 30)
        if y is None:
            y = random.uniform(-60, -15)
        super().__init__(_get_fast_image(), x, y,
                         ENEMY_FAST_SPEED, ENEMY_FAST_HP, ENEMY_FAST_SCORE,
                         fire_interval=fire_interval or ENEMY_FAST_FIRE_INTERVAL)
        # 斜向水平速度（随机左右方向）
        self._diag_speed: float = ENEMY_FAST_DIAGONAL_SPEED * random.choice((-1, 1))

    def _move(self, dt: float) -> None:
        """斜向下落 + 左右碰壁反弹"""
        # 水平移动
        self._x += self._diag_speed * dt
        # 碰壁反弹
        half_w: float = self.rect.width / 2.0
        if self._x - half_w < 0:
            self._x = half_w
            self._diag_speed = abs(self._diag_speed)
        elif self._x + half_w > SCREEN_WIDTH:
            self._x = SCREEN_WIDTH - half_w
            self._diag_speed = -abs(self._diag_speed)
        # 垂直下落
        self._y += self.speed * dt

    def _do_fire(self) -> list:
        """发射两枚斜向橙色子弹（←↙ 和 ↘→）"""


        cx, cy = self.rect.centerx, self.rect.bottom
        bullets = []
        for angle_offset in (-0.3, 0.3):  # 左右斜射
            b = Bullet(cx, cy, BulletSource.ENEMY, direction=1,
                       speed=200.0, style="fast")
            b._vx = math.sin(angle_offset) * 200.0
            b._vy = math.cos(angle_offset) * 200.0
            b._custom_velocity = True
            bullets.append(b)
        return bullets


class EliteEnemy(Enemy):
    """
    精英敌机 — 正弦波移动 + 连射弹幕
    ————————————————————————————————
    模式：垂直下落 + 水平正弦摆动
    公式：x = center_x + A × sin(2π × f × y / SCREEN_H)
    属性：100px/s | HP 4 | 得分 300 | 振幅 80px | 频率 2.5Hz
    射击：每 1.5 秒 3 连射，瞄准玩家位置
    """

    def __init__(self, x: float | None = None, y: float | None = None,
                 fire_interval: float | None = None) -> None:
        if x is None:
            x = SCREEN_WIDTH // 2  # 从屏幕中央开始
        if y is None:
            y = random.uniform(-100, -30)
        super().__init__(_get_elite_image(), x, y,
                         ENEMY_ELITE_SPEED, ENEMY_ELITE_HP, ENEMY_ELITE_SCORE,
                         fire_interval=fire_interval or ENEMY_ELITE_FIRE_INTERVAL)
        # 正弦波参数
        self._wave_center_x: float = x
        self._wave_amplitude: float = ENEMY_ELITE_WAVE_AMPLITUDE
        self._wave_frequency: float = ENEMY_ELITE_WAVE_FREQUENCY
        self._total_distance: float = 0.0  # 累计下落距离（用于相位计算）
        # 连射状态
        self._burst_remaining: int = 0
        self._burst_timer: float = 0.0
        # 玩家引用（用于瞄准射击）
        self._player: pygame.sprite.Sprite | None = None

    def set_player(self, player_sprite: pygame.sprite.Sprite) -> None:
        """设置玩家引用（用于瞄准射击）"""
        self._player = player_sprite

    def _move(self, dt: float) -> None:
        """正弦波移动：y 匀速下落，x 按正弦函数摆动"""
        # 垂直移动
        self._y += self.speed * dt
        self._total_distance += self.speed * dt

        # 水平正弦摆动
        # 相位 = 频率 × 已下落距离 / 屏幕高度 × 2π
        phase: float = (self._wave_frequency
                        * self._total_distance / SCREEN_HEIGHT
                        * 2.0 * math.pi)
        self._x = self._wave_center_x + self._wave_amplitude * math.sin(phase)

    def fire(self, dt: float) -> list:
        """
        精英敌机连射：一次触发发射多枚子弹（burst）。
        ────────────────────────────────────────
        覆盖基类 fire() 以支持 burst：
        每次射击间隔触发连射（ENEMY_ELITE_BURST_COUNT 发）。
        """
        if self._fire_interval <= 0:
            return []

        self._fire_timer += dt

        # 处理连射中剩余子弹
        if self._burst_remaining > 0:
            self._burst_timer += dt
            bullets = []
            while self._burst_timer >= ENEMY_ELITE_BURST_INTERVAL and self._burst_remaining > 0:
                self._burst_timer -= ENEMY_ELITE_BURST_INTERVAL
                self._burst_remaining -= 1
                b = self._do_fire_aimed()
                if b:
                    bullets.extend(b)
            return bullets

        # 触发新的一轮射击
        if self._fire_timer >= self._fire_interval:
            self._fire_timer -= self._fire_interval
            # 开始连射
            self._burst_remaining = ENEMY_ELITE_BURST_COUNT - 1
            self._burst_timer = 0.0
            return self._do_fire_aimed()  # 第一发立即发射

        return []

    def _do_fire_aimed(self) -> list:
        """发射一枚瞄准玩家的紫色子弹"""


        cx, cy = self.rect.centerx, self.rect.bottom

        if self._player is not None:
            dx = float(self._player.rect.centerx) - cx
            dy = float(self._player.rect.centery) - cy
            dist = math.hypot(dx, dy)
            if dist < 1:
                dx, dy = 0.0, 1.0
                dist = 1.0
            nx, ny = dx / dist, dy / dist
        else:
            nx, ny = 0.0, 1.0

        b = Bullet(cx, cy, BulletSource.ENEMY, direction=1,
                   speed=220.0, style="elite")
        b._vx = nx * 220.0
        b._vy = ny * 220.0
        b._custom_velocity = True
        return [b]


class TrackingEnemy(Enemy):
    """
    追踪敌机 — 追踪玩家 + 追踪射击
    ————————————————————————————————
    模式：每帧向玩家当前位置移动（线性插值逼近）
    属性：180px/s | HP 3 | 得分 250
    射击：每 1.8 秒发射两枚粉红追踪弹（略散开）
    """

    def __init__(
        self,
        player_sprite: pygame.sprite.Sprite | None = None,
        x: float | None = None,
        y: float | None = None,
        fire_interval: float | None = None,
    ) -> None:
        if x is None:
            x = random.uniform(30, SCREEN_WIDTH - 30)
        if y is None:
            y = random.uniform(-80, -20)
        super().__init__(_get_tracking_image(), x, y,
                         ENEMY_TRACKING_SPEED, ENEMY_TRACKING_HP,
                         ENEMY_TRACKING_SCORE,
                         fire_interval=fire_interval or ENEMY_TRACKING_FIRE_INTERVAL)
        # 玩家引用（用于获取当前位置）
        self._player: pygame.sprite.Sprite | None = player_sprite

    def set_player(self, player_sprite: pygame.sprite.Sprite) -> None:
        """设置/更新玩家引用"""
        self._player = player_sprite

    def _move(self, dt: float) -> None:
        """
        追踪移动：向玩家当前位置移动。
        ————————————————————————————————
        每帧计算从自身到玩家的方向向量，
        以固定速度沿该方向移动。

        如果玩家不存在，则直线下落。
        """
        if self._player is None:
            # 无目标 → 直线下落
            self._y += self.speed * dt
            return

        # 目标位置（玩家 rect 中心）
        target_x: float = float(self._player.rect.centerx)
        target_y: float = float(self._player.rect.centery)

        # 方向向量
        dx: float = target_x - self._x
        dy: float = target_y - self._y
        distance: float = math.sqrt(dx * dx + dy * dy)

        if distance < 1.0:
            return  # 已到达，停止移动

        # 归一化方向 × 速度 × dt
        move_x: float = (dx / distance) * self.speed * dt
        move_y: float = (dy / distance) * self.speed * dt

        self._x += move_x
        self._y += move_y

    def _do_fire(self) -> list:
        """发射两枚粉红子弹向玩家方向"""


        cx, cy = self.rect.centerx, self.rect.bottom

        if self._player is not None:
            dx = float(self._player.rect.centerx) - cx
            dy = float(self._player.rect.centery) - cy
            dist = math.hypot(dx, dy)
            if dist < 1:
                dx, dy = 0.0, 1.0
                dist = 1.0
            nx, ny = dx / dist, dy / dist
        else:
            nx, ny = 0.0, 1.0

        bullets = []
        for spread in (-0.2, 0.2):
            cos_a, sin_a = math.cos(spread), math.sin(spread)
            vx = (nx * cos_a - ny * sin_a) * 230.0
            vy = (nx * sin_a + ny * cos_a) * 230.0
            b = Bullet(cx, cy, BulletSource.ENEMY, direction=1,
                       speed=230.0, style="tracking")
            b._vx = vx
            b._vy = vy
            b._custom_velocity = True
            bullets.append(b)
        return bullets


# ==========================================================================
# Boss 敌机（题15：关卡3触发，大量HP + 弹幕攻击 + 独立血条）
# ==========================================================================

class BossEnemy(Enemy):
    """
    Boss 敌机。

    行为：
      1. 进入阶段：从屏幕顶外缓慢下降至目标Y位置（约 1/5 屏高处）
      2. 巡逻阶段：左右往复移动，碰壁反弹
      3. 弹幕攻击：三种模式轮换
         — 圆形弹幕：以 Boss 为中心向 12 方向发射
         — 瞄准弹幕：向玩家当前位置发射 3 发
         — 螺旋弹幕：连续高速发射，角度持续旋转
      4. 死亡：产生爆炸 + 大量得分

    draw_hp_bar() 在屏幕顶部居中绘制独立 Boss 血条。
    """

    # 弹幕模式
    MODE_FAN: str = "fan"        # 扇形弹幕（题19）
    MODE_CIRCLE: str = "circle"
    MODE_AIMED: str = "aimed"
    MODE_SPIRAL: str = "spiral"

    def __init__(
        self,
        player_sprite: pygame.sprite.Sprite | None = None,
        level: int = 3,
    ) -> None:
        x = SCREEN_WIDTH // 2
        y = -BOSS_HEIGHT  # 从屏幕上方外进入

        # Boss HP 随关卡缩放
        hp = int(BOSS_HP * (DIFFICULTY_HP_SCALE ** (level - 3)))

        super().__init__(
            _get_boss_image(), x, y,
            BOSS_SPEED, hp, BOSS_SCORE
        )

        # 玩家引用
        self._player: pygame.sprite.Sprite | None = player_sprite

        # 移动阶段
        self._phase: str = "enter"  # "enter" | "patrol"
        self._enter_elapsed: float = 0.0
        self._target_y: float = 80.0  # 巡逻目标Y坐标
        self._patrol_dir: float = 1.0  # 巡逻方向（1=右, -1=左）

        # 弹幕计时器（题19：扇形弹幕作为起手模式）
        self._fire_mode: str = self.MODE_FAN
        self._fire_timer: float = 0.0
        self._spiral_angle: float = 0.0

        self.layer: int = LAYER_BOSS  # Boss 绘制在玩家层上方
        # Boss 专属颜色标记（血条使用）
        self.boss_color: tuple = (255, 60, 60)

    def set_player(self, player_sprite: pygame.sprite.Sprite) -> None:
        self._player = player_sprite

    # ================================================================
    # 移动
    # ================================================================

    def _move(self, dt: float) -> None:
        if self._phase == "enter":
            self._move_enter(dt)
        else:
            self._move_patrol(dt)

    def _move_enter(self, dt: float) -> None:
        """进入阶段：从顶部缓慢下降至目标Y。"""
        self._enter_elapsed += dt
        if self._enter_elapsed >= BOSS_ENTER_DURATION:
            self._y = self._target_y
            self._phase = "patrol"
            return
        progress = self._enter_elapsed / BOSS_ENTER_DURATION
        start_y = -BOSS_HEIGHT
        self._y = start_y + (self._target_y - start_y) * progress

    def _move_patrol(self, dt: float) -> None:
        """巡逻阶段：左右往复移动，碰壁反弹。"""
        self._x += self.speed * self._patrol_dir * dt
        half_w = self.rect.width / 2.0
        left_bound = BOSS_PATROL_MARGIN + half_w
        right_bound = SCREEN_WIDTH - BOSS_PATROL_MARGIN - half_w
        if self._x <= left_bound:
            self._x = left_bound
            self._patrol_dir = 1.0
        elif self._x >= right_bound:
            self._x = right_bound
            self._patrol_dir = -1.0

    # ================================================================
    # 弹幕系统
    # ================================================================

    def fire(self, dt: float) -> list[Bullet]:
        """
        每帧调用，返回本帧需要发射的子弹列表。
        ————————————————————————————————
        主游戏循环将返回的子弹加入 bullets 组。
        """
        if self._phase != "patrol":
            return []  # 进入阶段不攻击

        self._fire_timer += dt
        bullets: list[Bullet] = []

        if self._fire_mode == self.MODE_FAN:
            bullets = self._fire_fan()
        elif self._fire_mode == self.MODE_CIRCLE:
            bullets = self._fire_circle()
        elif self._fire_mode == self.MODE_AIMED:
            bullets = self._fire_aimed()
        elif self._fire_mode == self.MODE_SPIRAL:
            bullets = self._fire_spiral()

        return bullets

    # ================================================================
    # 扇形弹幕（题19：向玩家方向扇形散射）
    # ================================================================

    def _fire_fan(self) -> list[Bullet]:
        """扇形弹幕：向玩家方向发射扇形散射弹。"""
        if self._fire_timer < BOSS_FAN_INTERVAL:
            return []
        self._fire_timer = 0.0
        self._fire_mode = self.MODE_AIMED  # 下一轮切换为瞄准弹幕

        bullets: list[Bullet] = []
        cx = self.rect.centerx
        cy = self.rect.bottom

        # 计算朝向玩家的基准角度
        if self._player is not None:
            dx = float(self._player.rect.centerx) - cx
            dy = float(self._player.rect.centery) - cy
            base_angle = math.atan2(dy, dx) if dy > 0 else math.pi / 2
        else:
            base_angle = math.pi / 2  # 默认正下方

        # 扇形范围
        half_fan = math.radians(BOSS_FAN_ANGLE / 2.0)
        start_angle = base_angle - half_fan
        n = BOSS_FAN_COUNT
        angle_step = (2.0 * half_fan) / (n - 1) if n > 1 else 0.0

        for i in range(n):
            angle = start_angle + angle_step * i
            # 确保子弹有向下的分量
            vy = max(math.sin(angle), 0.15)
            vx = math.cos(angle)
            speed = BOSS_BULLET_SPEED * (0.55 + 0.15 * (i % 3))
            b = Bullet(cx, cy, BulletSource.ENEMY, direction=1,
                       speed=speed, damage=BOSS_BULLET_DAMAGE, style="normal")
            b._vx = vx * speed
            b._vy = vy * speed
            b._custom_velocity = True
            bullets.append(b)
        return bullets

    def _fire_circle(self) -> list[Bullet]:
        """圆形弹幕：12方向散弹。"""
        if self._fire_timer < BOSS_FIRE_INTERVAL_CIRCLE:
            return []
        self._fire_timer = 0.0
        self._fire_mode = self.MODE_FAN  # 下一轮切回扇形弹幕

        bullets: list[Bullet] = []
        cx = self.rect.centerx
        cy = self.rect.bottom
        n = 12
        for i in range(n):
            angle = 2.0 * math.pi * i / n
            vx = math.cos(angle) * BOSS_BULLET_SPEED * 0.6
            vy = math.sin(angle) * BOSS_BULLET_SPEED * 0.6
            # 排除正上方（i≈9），避免背向玩家
            b = Bullet(cx, cy, BulletSource.ENEMY, direction=1,
                       speed=BOSS_BULLET_SPEED * 0.7, damage=BOSS_BULLET_DAMAGE,
                       style="elite")
            b._vx = vx
            b._vy = vy
            b._custom_velocity = True
            bullets.append(b)
        return bullets

    def _fire_aimed(self) -> list[Bullet]:
        """瞄准弹幕：向玩家位置发射 3 发。"""
        if self._fire_timer < BOSS_FIRE_INTERVAL_AIMED:
            return []
        self._fire_timer = 0.0
        self._fire_mode = self.MODE_SPIRAL

        bullets: list[Bullet] = []
        if self._player is None:
            return bullets

        cx = self.rect.centerx
        cy = self.rect.bottom
        tx = float(self._player.rect.centerx)
        ty = float(self._player.rect.centery)

        base_dx = tx - cx
        base_dy = ty - cy
        base_dist = math.sqrt(base_dx * base_dx + base_dy * base_dy)
        if base_dist < 1.0:
            base_dx, base_dy = 0.0, 1.0
            base_dist = 1.0
        base_dx /= base_dist
        base_dy /= base_dist

        for angle_offset in (-0.15, 0.0, 0.15):
            cos_a = math.cos(angle_offset)
            sin_a = math.sin(angle_offset)
            dx = base_dx * cos_a - base_dy * sin_a
            dy = base_dx * sin_a + base_dy * cos_a
            b = Bullet(cx, cy, BulletSource.ENEMY, direction=1,
                       speed=BOSS_BULLET_SPEED * 0.8, damage=BOSS_BULLET_DAMAGE,
                       style="tracking")
            b._vx = dx * BOSS_BULLET_SPEED * 0.8
            b._vy = dy * BOSS_BULLET_SPEED * 0.8
            b._custom_velocity = True
            bullets.append(b)
        return bullets

    def _fire_spiral(self) -> list[Bullet]:
        """螺旋弹幕：连续发射，角度持续旋转。"""
        if self._fire_timer < BOSS_FIRE_INTERVAL_SPIRAL:
            return []
        self._fire_timer = 0.0

        # 螺旋持续一段时间后切回圆形弹幕
        self._spiral_angle += 0.3
        if self._spiral_angle > 4.0 * math.pi:
            self._spiral_angle = 0.0
            self._fire_mode = self.MODE_CIRCLE

        cx = self.rect.centerx
        cy = self.rect.bottom
        b = Bullet(cx, cy, BulletSource.ENEMY, direction=1,
                   speed=BOSS_BULLET_SPEED * 0.5, damage=BOSS_BULLET_DAMAGE,
                   style="fast")
        b._vx = math.cos(self._spiral_angle) * BOSS_BULLET_SPEED * 0.6
        b._vy = abs(math.sin(self._spiral_angle)) * BOSS_BULLET_SPEED * 0.6 + BOSS_BULLET_SPEED * 0.2
        b._custom_velocity = True
        return [b]

    # ================================================================
    # Boss 血条绘制
    # ================================================================

    def draw_hp_bar(self, screen: pygame.Surface) -> None:
        """在屏幕顶部居中绘制 Boss 血条（题19：带名称标签和HP数值）。"""
        bar_w = 320
        bar_h = 14
        bar_x = (SCREEN_WIDTH - bar_w) // 2
        bar_y = 6

        hp_ratio = self.hp / max(self.max_hp, 1)

        # Boss 名称标签
        try:
            font = pygame.font.Font(UI_FONT_PATH, 14)
        except Exception:
            font = pygame.font.Font(None, 14)
        name_surf = font.render("BOSS", True, (255, 80, 80))
        name_rect = name_surf.get_rect(center=(bar_x + bar_w // 2, bar_y - 8))
        screen.blit(name_surf, name_rect)

        # 背景（暗槽）
        pygame.draw.rect(screen, (20, 20, 20), (bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2))
        pygame.draw.rect(screen, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h))

        # HP 填充（颜色随血量变化 + 低血量闪烁）
        if hp_ratio > 0:
            if hp_ratio > 0.6:
                color = (220, 50, 50)
            elif hp_ratio > 0.3:
                color = (255, 140, 30)
            else:
                # 低于30%血量红闪烁
                color = (255, 30, 30) if int(pygame.time.get_ticks() / 120) % 2 == 0 else (255, 80, 80)
            fill_w = int(bar_w * hp_ratio)
            if fill_w > 0:
                pygame.draw.rect(screen, color, (bar_x, bar_y, fill_w, bar_h))
                # 高亮顶部边缘（立体感）
                if fill_w > 2:
                    pygame.draw.rect(screen, (255, 160, 140),
                                   (bar_x, bar_y, fill_w, 3))

        # 边框
        pygame.draw.rect(screen, (200, 200, 200),
                        (bar_x, bar_y, bar_w, bar_h), width=2)

        # HP 数值文字
        hp_text = f"{max(0, self.hp)} / {self.max_hp}"
        try:
            hp_font = pygame.font.Font(UI_FONT_PATH, 13)
        except Exception:
            hp_font = pygame.font.Font(None, 13)
        hp_surf = hp_font.render(hp_text, True, (255, 255, 255))
        hp_surf.set_alpha(230)
        hp_text_rect = hp_surf.get_rect(center=(bar_x + bar_w // 2, bar_y + bar_h // 2 + 1))
        screen.blit(hp_surf, hp_text_rect)

    # ================================================================
    # Boss 死亡爆炸位置（题19：特殊爆炸动画 — 多点连续爆炸）
    # ================================================================

    def get_death_explosion_positions(self) -> list[tuple[int, int]]:
        """返回 Boss 死亡时的多处爆炸位置，供主循环生成连续爆炸。"""
        positions: list[tuple[int, int]] = []
        cx, cy = self.rect.center
        w, h = self.rect.width, self.rect.height

        # 中心主爆炸
        positions.append((cx, cy))
        # 四角爆炸
        positions.append((cx - w // 3, cy - h // 3))
        positions.append((cx + w // 3, cy - h // 3))
        positions.append((cx - w // 3, cy + h // 3))
        positions.append((cx + w // 3, cy + h // 3))
        # 四边爆炸
        positions.append((cx, cy - h // 2 + 5))
        positions.append((cx - w // 2 + 5, cy))
        positions.append((cx + w // 2 - 5, cy))
        positions.append((cx, cy + h // 2 - 5))
        # 随机偏移位置（增加视觉层次）
        import random
        for _ in range(BOSS_EXPLOSION_COUNT - 9):
            positions.append((
                cx + random.randint(-w // 2 + 5, w // 2 - 5),
                cy + random.randint(-h // 2 + 5, h // 2 - 5),
            ))

        return positions


# ==========================================================================
# Boss 图像加载（题19：真实素材）
# ==========================================================================

_boss_image_cache: pygame.Surface | None = None


def _get_boss_image() -> pygame.Surface:
    global _boss_image_cache
    if _boss_image_cache is None:
        _boss_image_cache = load_image(BOSS_IMAGE_PATH, width=BOSS_WIDTH, height=BOSS_HEIGHT)
    return _boss_image_cache
