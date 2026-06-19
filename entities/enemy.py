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
    BOSS_ENTER_DURATION, BOSS_PATROL_MARGIN, BOSS_BULLET_DAMAGE, BOSS_BULLET_SPEED,
    BOSS_EXPLOSION_COUNT,
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
        self._burst_index: int = 0  # ⭐ 连射第几发（用于散布递增）
        # 玩家引用（用于瞄准射击）
        self._player: pygame.sprite.Sprite | None = None
        # ⭐ 玩家速度追踪（预测瞄准）
        self._last_px: float = 0.0
        self._last_py: float = 0.0
        self._player_vx: float = 0.0
        self._player_vy: float = 0.0

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
        覆盖基类 fire() 以支持 burst + 预测瞄准：
        每次射击间隔触发连射（ENEMY_ELITE_BURST_COUNT 发）。
        第1发精确预测，后续散布递增封锁走位。
        """
        if self._fire_interval <= 0:
            return []

        self._fire_timer += dt

        # ⭐ 追踪玩家速度（用于预测瞄准）
        if self._player is not None:
            px, py = self._player.rect.centerx, self._player.rect.centery
            if self._last_px != 0:
                self._player_vx = (px - self._last_px) / max(dt, 0.001)
                self._player_vy = (py - self._last_py) / max(dt, 0.001)
            self._last_px, self._last_py = px, py

        # 处理连射中剩余子弹
        if self._burst_remaining > 0:
            self._burst_timer += dt
            bullets = []
            while self._burst_timer >= ENEMY_ELITE_BURST_INTERVAL and self._burst_remaining > 0:
                self._burst_timer -= ENEMY_ELITE_BURST_INTERVAL
                self._burst_remaining -= 1
                self._burst_index += 1
                b = self._do_fire_aimed(self._burst_index)
                if b:
                    bullets.extend(b)
            return bullets

        # 触发新的一轮射击
        if self._fire_timer >= self._fire_interval:
            self._fire_timer -= self._fire_interval
            self._burst_remaining = ENEMY_ELITE_BURST_COUNT - 1
            self._burst_timer = 0.0
            self._burst_index = 0
            return self._do_fire_aimed(0)  # 第1发精确瞄准

        return []

    def _do_fire_aimed(self, burst_index: int = 0) -> list:
        """发射一枚瞄准玩家的紫色子弹（⭐ 预测瞄准 + 散布递增）"""
        cx, cy = self.rect.centerx, self.rect.bottom

        if self._player is not None:
            px, py = float(self._player.rect.centerx), float(self._player.rect.centery)
            dx, dy = px - cx, py - cy
            dist = math.hypot(dx, dy)
            if dist < 1:
                dx, dy = 0.0, 1.0
                dist = 1.0
            # ⭐ 第一发精确预测，后续散布递增
            if burst_index == 0 and abs(self._player_vx) > 30:
                fly_time = dist / 220.0
                px += self._player_vx * fly_time * 0.6
                py += self._player_vy * fly_time * 0.6
                dx, dy = px - cx, py - cy
                dist = math.hypot(dx, dy)
                if dist < 1:
                    dx, dy = 0.0, 1.0
                    dist = 1.0
            # 散布偏移（burst_index越大散越开）
            spread = burst_index * 0.08  # 0, 0.08, 0.16 rad
            if spread > 0:
                cos_a, sin_a = math.cos(spread), math.sin(spread)
                ndx = dx * cos_a - dy * sin_a
                ndy = dx * sin_a + dy * cos_a
                dx, dy = ndx, ndy
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
        # ⭐ 预测拦截
        self._last_target: tuple[float, float] | None = None
        # ⭐ 编队包抄偏移（场上多架时自动分配左右）
        self._flank_offset: float = random.choice([-70, 70])

    def set_player(self, player_sprite: pygame.sprite.Sprite) -> None:
        """设置/更新玩家引用"""
        self._player = player_sprite

    def _move(self, dt: float) -> None:
        """
        追踪移动：预测拦截 + 编队包抄。
        ————————————————————————————————
        ① 估算玩家速度 → 预测未来位置
        ② 场上多架追踪敌机时自动左右包抄
        ③ 近身时切换直接追击
        """
        if self._player is None:
            self._y += self.speed * dt
            return

        target_x: float = float(self._player.rect.centerx)
        target_y: float = float(self._player.rect.centery)

        # ⭐ 预测拦截：根据玩家最近2帧速度估算提前量
        if self._last_target is not None:
            pvx = (target_x - self._last_target[0]) / max(dt, 0.001)
            pvy = (target_y - self._last_target[1]) / max(dt, 0.001)
            if abs(pvx) > 40 or abs(pvy) > 40:
                dx_pred = target_x - self._x
                dy_pred = target_y - self._y
                dist_pred = math.hypot(dx_pred, dy_pred)
                if dist_pred > 1:
                    fly_time = dist_pred / max(self.speed, 1)
                    target_x += pvx * fly_time * 0.5
                    target_y += pvy * fly_time * 0.5
        self._last_target = (float(self._player.rect.centerx),
                             float(self._player.rect.centery))

        # ⭐ 编队包抄：距玩家较远时左右散开，近身时合围
        dx = target_x - self._x
        dy = target_y - self._y
        distance = math.hypot(dx, dy)
        if distance > 150:
            target_x += self._flank_offset  # 远距走侧翼
        # 近身（< 120px）取消偏移，直接扑向玩家
        # 方向向量
        dx = target_x - self._x
        dy = target_y - self._y
        distance = math.hypot(dx, dy)
        if distance < 1.0:
            return

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
    Boss 敌机 — 多阶段战斗系统。

    行为：
      1. 进入阶段：从屏幕顶外缓慢下降至目标Y位置（约 1/5 屏高处）
      2. 巡逻阶段：左右往复移动，碰壁反弹
      3. 弹幕攻击：三种模式轮换
         — 圆形弹幕：以 Boss 为中心向 12 方向发射
         — 瞄准弹幕：向玩家当前位置发射 3 发
         — 螺旋弹幕：连续高速发射，角度持续旋转
      4. 战斗阶段（根据 HP 百分比自动切换）：
         — PHASE_1 (HP>70%): 标准速度，标准弹幕
         — PHASE_2 (70%≥HP>30%): 加速，新增交叉弹幕，屏幕震动
         — PHASE_3 (HP≤30%): 狂暴模式，所有弹幕大幅加速，高频射击
      5. 死亡：产生爆炸 + 大量得分 + 粒子特效

    draw_hp_bar() 在屏幕顶部居中绘制独立 Boss 血条，颜色随阶段变化。
    """

    # 弹幕模式
    MODE_FAN: str = "fan"        # 扇形弹幕
    MODE_CIRCLE: str = "circle"  # 圆形弹幕
    MODE_AIMED: str = "aimed"    # 瞄准弹幕
    MODE_SPIRAL: str = "spiral"  # 螺旋弹幕
    MODE_CROSS: str = "cross"    # 交叉弹幕
    MODE_WALL: str = "wall"      # ⭐ 弹幕墙

    # ⭐ 战斗阶段
    PHASE_1: str = "phase1"  # HP > 70%
    PHASE_2: str = "phase2"  # 70% ≥ HP > 30%
    PHASE_3: str = "phase3"  # HP ≤ 30%

    def __init__(
        self,
        player_sprite: pygame.sprite.Sprite | None = None,
        level: int = 3,
    ) -> None:
        x = SCREEN_WIDTH // 2
        y = -BOSS_HEIGHT  # 从屏幕上方外进入

        # Boss HP 随关卡缩放（⭐ 独立缩放公式：最终 Boss 更有压迫感）
        effective_level = max(0, level - 3)
        hp = int(BOSS_HP * (1.25 ** effective_level))

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

        # 弹幕计时器
        self._fire_mode: str = self.MODE_FAN
        self._fire_timer: float = 0.0
        self._spiral_angle: float = 0.0
        self._cross_angle: float = 0.0  # ⭐ 交叉弹幕旋转角

        # ⭐ 战斗阶段系统
        self._combat_phase: str = self.PHASE_1
        self._prev_combat_phase: str = self.PHASE_1
        self._phase_transition_timer: float = 0.0  # 阶段切换过渡计时
        self._phase_transitioning: bool = False     # 是否正在切换
        self._phase_flash_alpha: int = 0           # 切换时的闪屏alpha

        self.layer: int = LAYER_BOSS  # Boss 绘制在玩家层上方
        # Boss 专属颜色标记（血条使用）
        self.boss_color: tuple = (255, 60, 60)

        # ⭐ 魂式招式状态机
        self._atk_state: str = "idle"       # idle/telegraph/attack/cooldown
        self._atk_timer: float = 0.0
        self._atk_phase: int = 0            # 攻击进行到第几发
        self._atk_max: int = 1              # 攻击总共发几轮
        self._atk_next: str = ""            # 下一个招式
        self._telegraph_x: float = 0.0      # 起手势目标位置
        self._telegraph_y: float = 0.0
        self._telegraph_alpha: int = 0      # 起手势闪光

    def set_player(self, player_sprite: pygame.sprite.Sprite) -> None:
        self._player = player_sprite

    # ════════════════════════════════════════════════════════════════
    # ⭐ 战斗阶段系统
    # ════════════════════════════════════════════════════════════════

    @property
    def combat_phase(self) -> str:
        """基于当前 HP 百分比返回战斗阶段。"""
        ratio = self.hp / max(self.max_hp, 1)
        if ratio <= 0.3:
            return self.PHASE_3
        elif ratio <= 0.7:
            return self.PHASE_2
        return self.PHASE_1

    @property
    def combat_phase_changed(self) -> bool:
        """本轮帧是否有阶段切换（供外部检测）。"""
        return self._prev_combat_phase != self._combat_phase

    @property
    def phase_name(self) -> str:
        """战斗阶段的中文名称。"""
        names = {
            self.PHASE_1: "PHASE 1",
            self.PHASE_2: "PHASE 2",
            self.PHASE_3: "⚠ PHASE 3 ⚠",
        }
        return names.get(self._combat_phase, "PHASE 1")

    def _update_combat_phase(self) -> None:
        """每帧检测 HP 并更新战斗阶段，必要时触发过渡。"""
        new_phase = self.combat_phase
        if new_phase != self._combat_phase:
            self._prev_combat_phase = self._combat_phase
            self._combat_phase = new_phase
            self._phase_transitioning = True
            self._phase_transition_timer = 0.0
            self._phase_flash_alpha = 200
            # 战斗阶段切换：加速弹幕周期
            if new_phase == self.PHASE_2:
                self._fire_mode = self.MODE_CROSS  # 交叉弹幕起手
            elif new_phase == self.PHASE_3:
                self._fire_mode = self.MODE_SPIRAL  # 螺旋弹幕起手

    def _get_phase_speed_mult(self) -> float:
        """当前战斗阶段的速度倍率。"""
        mults = {
            self.PHASE_1: 1.0,
            self.PHASE_2: 1.35,
            self.PHASE_3: 1.8,
        }
        return mults.get(self._combat_phase, 1.0)

    def _get_phase_fire_rate_mult(self) -> float:
        """当前战斗阶段的射速倍率（越小越快）。"""
        mults = {
            self.PHASE_1: 1.0,
            self.PHASE_2: 0.65,
            self.PHASE_3: 0.4,
        }
        return mults.get(self._combat_phase, 1.0)

    @property
    def phase_color(self) -> tuple:
        """当前战斗阶段对应的血条/文字颜色。"""
        colors = {
            self.PHASE_1: (220, 50, 50),
            self.PHASE_2: (255, 160, 30),
            self.PHASE_3: (255, 0, 0),
        }
        c = colors.get(self._combat_phase, (220, 50, 50))
        # Phase 3 低血量闪烁
        if self._combat_phase == self.PHASE_3 and int(pygame.time.get_ticks() / 150) % 2 == 0:
            return (255, 255, 255)
        return c

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
        """巡逻阶段：左右往复移动，碰壁反弹（速度受战斗阶段影响）。"""
        speed = self.speed * self._get_phase_speed_mult()
        self._x += speed * self._patrol_dir * dt
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
    # ⭐ 弹幕系统（全面强化版）
    # ================================================================

    def fire(self, dt: float) -> list[Bullet]:
        try:
            return self._fire_impl(dt)
        except Exception as e:
            import traceback
            print(f"[BOSS CRASH] fire() error: {e}")
            traceback.print_exc()
            return []

    def _fire_impl(self, dt: float) -> list[Bullet]:
        if self._phase != "patrol":
            return []
        self._update_combat_phase()
        if self._phase_transitioning:
            self._phase_transition_timer += dt
            self._phase_flash_alpha = max(0, self._phase_flash_alpha - dt * 300)
            if self._phase_transition_timer > 0.8:
                self._phase_transitioning = False

        self._atk_timer += dt
        bullets: list[Bullet] = []

        # ════════════════════════════════════════════════════════════
        # ⭐ 魂式招式状态机
        # ════════════════════════════════════════════════════════════

        if self._atk_state == "idle":
            # 选下一个招式
            self._atk_next = self._choose_attack()
            # 起手势：移动到目标位置 + 蓄力闪光
            self._atk_state = "telegraph"
            self._atk_timer = 0.0
            self._atk_phase = 0
            self._atk_max = self._get_attack_rounds(self._atk_next)
            # 目标位置：中心或偏侧
            if random.random() < 0.4:
                self._telegraph_x = SCREEN_WIDTH // 2
                self._telegraph_y = SCREEN_HEIGHT * 0.25
            else:
                left = random.choice([True, False])
                self._telegraph_x = 100 if left else SCREEN_WIDTH - 100
                self._telegraph_y = SCREEN_HEIGHT * 0.2
            self._telegraph_alpha = 0

        elif self._atk_state == "telegraph":
            # 移向目标位置 + 蓄力
            t = self._atk_timer / 1.0  # 1秒起手势
            self._telegraph_alpha = int(150 * t)
            # 平滑移动
            self._x += (self._telegraph_x - self._x) * dt * 3.0
            self.rect.centerx = int(self._x)
            # 闪光
            if t >= 1.0:
                self._atk_state = "attack"
                self._atk_timer = 0.0
                self._atk_phase = 0
                self._telegraph_alpha = 0

        elif self._atk_state == "attack":
            # 执行招式
            bullets = self._fire_attack(self._atk_next, self._atk_phase)
            if bullets:
                self._atk_phase += 1
            if self._atk_phase >= self._atk_max:
                self._atk_state = "cooldown"
                self._atk_timer = 0.0

        elif self._atk_state == "cooldown":
            # 招式后间隙
            if self._atk_timer > 0.8:
                self._atk_state = "idle"

        return bullets

    # ════════════════════════════════════════════════════════════════
    # ⭐ 招式系统
    # ════════════════════════════════════════════════════════════════

    ATK_CROSS = "atk_cross"        # 十字：上下左右 4 道
    ATK_FAN = "atk_fan"            # 扇形：朝玩家
    ATK_CIRCLE = "atk_circle"      # 圆形：全方向
    ATK_WALL = "atk_wall"          # 弹幕墙：连射 3 排

    def _choose_attack(self) -> str:
        weights = {
            self.ATK_CROSS: 25, self.ATK_FAN: 25,
            self.ATK_CIRCLE: 25, self.ATK_WALL: 25,
        }
        return random.choices(list(weights.keys()), weights=list(weights.values()))[0]

    def _get_attack_rounds(self, atk_type: str) -> int:
        r = {self.ATK_CROSS: 2, self.ATK_FAN: 2, self.ATK_CIRCLE: 1, self.ATK_WALL: 3}
        return r.get(atk_type, 1)

    def _fire_attack(self, atk_type: str, phase: int) -> list[Bullet]:
        fn = {
            self.ATK_CROSS: self._atk_cross,
            self.ATK_FAN: self._atk_fan,
            self.ATK_CIRCLE: self._atk_circle,
            self.ATK_WALL: self._atk_wall,
        }
        return fn.get(atk_type, lambda: [])()

    # ════════════════════════════════════════════════════════════════
    # 十字扫射：上下左右各一道
    # ════════════════════════════════════════════════════════════════

    def _atk_cross(self) -> list[Bullet]:
        bullets = []
        cx, cy = self.rect.centerx, self.rect.bottom
        spd = BOSS_BULLET_SPEED * 0.8
        for angle in (0, math.pi, math.pi / 2, -math.pi / 2):
            for i in range(8):
                a = angle + (i - 3.5) * 0.03
                b = Bullet(cx, cy, BulletSource.ENEMY, direction=1,
                           speed=spd, damage=BOSS_BULLET_DAMAGE, style="elite")
                b._vx, b._vy = math.cos(a) * spd, math.sin(a) * spd
                b._custom_velocity = True
                bullets.append(b)
        return bullets

    # ════════════════════════════════════════════════════════════════
    # 扇形散射：朝玩家方向
    # ════════════════════════════════════════════════════════════════

    def _atk_fan(self) -> list[Bullet]:
        bullets = []
        cx, cy = self.rect.centerx, self.rect.bottom
        if self._player:
            dx = float(self._player.rect.centerx) - cx
            dy = float(self._player.rect.centery) - cy
            base = math.atan2(dy, dx) if dy > 0 else math.pi / 2
        else:
            base = math.pi / 2
        half = math.radians(50)
        n = 20
        step = (2 * half) / max(n - 1, 1)
        spd = BOSS_BULLET_SPEED * 0.7
        for i in range(n):
            a = base - half + step * i
            vy = max(math.sin(a), 0.15)
            vx = math.cos(a)
            b = Bullet(cx, cy, BulletSource.ENEMY, direction=1,
                       speed=spd, damage=BOSS_BULLET_DAMAGE, style="elite")
            b._vx, b._vy = vx * spd, vy * spd
            b._custom_velocity = True
            bullets.append(b)
        return bullets

    # ════════════════════════════════════════════════════════════════
    # 圆形散弹：全方向
    # ════════════════════════════════════════════════════════════════

    def _atk_circle(self) -> list[Bullet]:
        bullets = []
        cx, cy = self.rect.centerx, self.rect.bottom
        n = 24
        spd = BOSS_BULLET_SPEED * 0.6
        for i in range(n):
            a = 2 * math.pi * i / n
            b = Bullet(cx, cy, BulletSource.ENEMY, direction=1,
                       speed=spd, damage=BOSS_BULLET_DAMAGE, style="elite")
            b._vx, b._vy = math.cos(a) * spd, math.sin(a) * spd
            b._custom_velocity = True
            bullets.append(b)
        return bullets

    # ════════════════════════════════════════════════════════════════
    # 弹幕墙：水平连续排
    # ════════════════════════════════════════════════════════════════

    def _atk_wall(self) -> list[Bullet]:
        bullets = []
        cy = self.rect.bottom
        spd = BOSS_BULLET_SPEED * 0.5
        n = 18
        for i in range(n):
            x = (i + 0.5) * SCREEN_WIDTH / n
            b = Bullet(int(x), int(cy), BulletSource.ENEMY, direction=1,
                       speed=spd, damage=BOSS_BULLET_DAMAGE, style="normal")
            b._vx, b._vy = 0, spd
            b._custom_velocity = True
            bullets.append(b)
        return bullets

    def draw_hp_bar(self, screen: pygame.Surface) -> None:
        """在屏幕顶部居中绘制 Boss 血条，含战斗阶段标记和颜色变化。"""
        bar_w = 320
        bar_h = 14
        bar_x = (SCREEN_WIDTH - bar_w) // 2
        bar_y = 6

        hp_ratio = self.hp / max(self.max_hp, 1)

        # Boss 名称标签 + ⭐ 战斗阶段标记
        try:
            font = pygame.font.Font(UI_FONT_PATH, 14)
        except Exception:
            font = pygame.font.Font(None, 14)
        phase_label = self.phase_name
        name_text = f"BOSS  {phase_label}"
        name_surf = font.render(name_text, True, self.phase_color)
        name_rect = name_surf.get_rect(center=(bar_x + bar_w // 2, bar_y - 8))
        screen.blit(name_surf, name_rect)

        # ⭐ 阶段过渡闪屏 + ⭐ 起手势光芒
        if self._phase_transitioning and self._phase_flash_alpha > 0:
            flash_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            flash_surf.fill((255, 255, 255, min(255, int(self._phase_flash_alpha))))
            screen.blit(flash_surf, (0, 0))
        if self._telegraph_alpha > 0:
            r = self.rect.width
            glow = pygame.Surface((r * 3, r * 3), pygame.SRCALPHA)
            for i in range(5, 0, -1):
                a = max(1, self._telegraph_alpha // (i * 2))
                pygame.draw.circle(glow, (255, 100, 50, a), (r * 3 // 2, r * 3 // 2), r + i * 8, 2)
            screen.blit(glow, self.rect.move(-r, -r))

        # 背景（暗槽）
        pygame.draw.rect(screen, (20, 20, 20), (bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2))
        pygame.draw.rect(screen, (40, 40, 40), (bar_x, bar_y, bar_w, bar_h))

        # HP 填充（颜色随战斗阶段变化 + 低血量闪烁）
        if hp_ratio > 0:
            fill_color = self.phase_color
            fill_w = int(bar_w * hp_ratio)
            if fill_w > 0:
                pygame.draw.rect(screen, fill_color, (bar_x, bar_y, fill_w, bar_h))
                # 高亮顶部边缘（立体感）
                if fill_w > 2:
                    hl = tuple(min(255, c + 60) for c in fill_color)
                    pygame.draw.rect(screen, hl, (bar_x, bar_y, fill_w, 3))

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
