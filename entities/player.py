"""
==============================================================================
飞机大战 — 玩家飞机精灵类（题7：蓄力射击机制）
==============================================================================
继承 pygame.sprite.Sprite，实现：
  1. 图像加载/缩放/旋转（前题累积）
  2. 双输入系统协同（get_pressed + KEYDOWN/KEYUP）
  3. Shift 加速 + 边界限制
  4. 蓄力射击：进度条随时间填充（1.5秒满），SPACE释放
  5. 蓄力等级决定弹数：<40%单发, 40-80%双发, ≥80%三发
  6. 蓄力条常驻 + 颜色分区 + 满蓄闪烁提示
"""

import time
import math
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    PLAYER_WIDTH, PLAYER_HEIGHT,
    PLAYER_SPEED, PLAYER_TILT_ANGLE, PLAYER_BOOST_MULTIPLIER,
    PLAYER_MAX_HP, PLAYER_INVINCIBLE_TIME,
    PLAYER_CHARGE_TIME, PLAYER_AUTO_FIRE_INTERVAL,
    CHARGE_THRESHOLD_DOUBLE, CHARGE_THRESHOLD_TRIPLE,
    DOUBLE_SHOT_SPACING,
    PLAYER_BULLET_DAMAGE,
    LAYER_PLAYER,
    GRAY, YELLOW, GREEN, CYAN, WHITE, RED, BLACK,
    UI_FONT_PATH,
    POWERUP_DURATION, PLAYER_MAX_BOMBS,
    PowerUpType,
    PLAYER_IMAGE_PATH,
)
from utils.resource_manager import load_image, rotate_image
from entities.bullet import Bullet, BulletSource


class Player(pygame.sprite.DirtySprite):
    """
    玩家飞机精灵
    ————————————————————————————————
    输入系统设计说明：

    ┌─────────────────┬────────────────────┬──────────────────┐
    │ 方式             │ 适用场景            │ 键盘延迟         │
    ├─────────────────┼────────────────────┼──────────────────┤
    │ get_pressed()   │ 持续按住（移动）     │ 无延迟，每帧轮询  │
    │ KEYDOWN/KEYUP   │ 单次触发（射击/技能）│ 受OS重复率影响    │
    └─────────────────┴────────────────────┴──────────────────┘

    本类同时实现两种方式：
      - 移动：使用 get_pressed() 获取瞬时状态 → 无延迟平滑移动
      - 动作标记：使用 KEYDOWN/KEYUP 设置布尔标记位（为后续射击等功能预留）
    """

    def __init__(self) -> None:
        """初始化玩家飞机：加载图像、预计算旋转、设置初始位置与输入状态"""
        super().__init__()

        self.layer: int = LAYER_PLAYER
        self.dirty: int = 2  # 玩家每帧都可能移动，始终重绘

        # ================================================================
        # 图像初始化
        # ================================================================

        # ① load_image() → pygame.image.load() + convert_alpha() + transform.scale()
        self._image_straight: pygame.Surface = load_image(
            PLAYER_IMAGE_PATH, width=PLAYER_WIDTH, height=PLAYER_HEIGHT
        )

        # ② 预计算倾斜变体（避免每帧 rotate）
        self._image_left: pygame.Surface = rotate_image(
            self._image_straight, PLAYER_TILT_ANGLE
        )
        self._image_right: pygame.Surface = rotate_image(
            self._image_straight, -PLAYER_TILT_ANGLE
        )

        # ③ 当前显示的图像
        self.image: pygame.Surface = self._image_straight

        # ④ 碰撞矩形与初始位置
        self.rect: pygame.Rect = self.image.get_rect()
        self.rect.centerx = SCREEN_WIDTH // 2
        self.rect.bottom = SCREEN_HEIGHT - 30

        # ================================================================
        # 移动参数
        # ================================================================
        self.base_speed: int = PLAYER_SPEED
        self.boost_multiplier: float = PLAYER_BOOST_MULTIPLIER

        # ================================================================
        # 蓄力射击参数
        # ================================================================
        # 蓄力值：0.0（空）→ 1.0（满），随时间自动增长
        self._charge_level: float = 0.0
        # 充满所需时间（秒），值越大蓄力越慢
        self._charge_time: float = PLAYER_CHARGE_TIME

        # ================================================================
        # HP 与受伤系统（题10）
        # ================================================================
        self.hp: int = PLAYER_MAX_HP
        self.max_hp: int = PLAYER_MAX_HP
        # 无敌计时器：受伤后短暂无敌，防止连续扣血
        self._invincible_timer: float = 0.0
        self._invincible_duration: float = PLAYER_INVINCIBLE_TIME

        # 道具 Buff 状态（题18）— 多个 Buff 可叠加，各自独立计时
        self._active_powerups: dict[PowerUpType, float] = {}

        # ⭐ 炸弹系统
        self.bomb_count: int = 0
        self.max_bombs: int = PLAYER_MAX_BOMBS
        # ⭐ 复活命（击败Boss奖励）
        self.extra_lives: int = 0
        self._just_revived: bool = False
        self._extra_damage: int = 0       # 额外伤害
        self._spread_upgrade: int = 0     # 额外弹幕扩散数

        # ⭐ 自动连射系统
        self._auto_fire_timer: float = 0.0
        self._auto_fire_interval: float = PLAYER_AUTO_FIRE_INTERVAL
        self._is_firing: bool = False     # 是否按住射击键

        # ⭐ 自机判定点（4×4 超小 hitbox，经典 STG 手感）
        self._hitbox: pygame.Rect = pygame.Rect(0, 0, 4, 4)
        self._hitbox.center = self.rect.center
        self._show_hitbox: bool = False   # F1 切换显示

        # ================================================================
        # 输入状态标记位（KEYDOWN/KEYUP 方案）
        # ================================================================
        # 用于一次性触发的动作（后续射击、技能等使用）
        # 移动不依赖这些标记位，而是用 get_pressed() 直接读取
        self._move_left_flag: bool = False
        self._move_right_flag: bool = False
        self._move_up_flag: bool = False
        self._move_down_flag: bool = False
        self._boost_flag: bool = False

    # ====================================================================
    # 公共输入接口（由 Game.handle_events 调用）
    # ====================================================================

    def handle_keydown(self, event: pygame.event.Event) -> None:
        """
        处理 KEYDOWN 事件。
        ————————————————————————————————
        设置方向标记位，同时响应单次触发的动作。
        移动本身由 get_pressed() 驱动，此处标记位作为辅助状态记录。
        """
        if event.key == pygame.K_a or event.key == pygame.K_LEFT:
            self._move_left_flag = True
        elif event.key == pygame.K_d or event.key == pygame.K_RIGHT:
            self._move_right_flag = True
        elif event.key == pygame.K_w or event.key == pygame.K_UP:
            self._move_up_flag = True
        elif event.key == pygame.K_s or event.key == pygame.K_DOWN:
            self._move_down_flag = True
        elif event.key == pygame.K_LSHIFT or event.key == pygame.K_RSHIFT:
            self._boost_flag = True
        elif event.key == pygame.K_SPACE:
            self._is_firing = True  # ⭐ 开始射击

    def handle_keyup(self, event: pygame.event.Event) -> None:
        """
        处理 KEYUP 事件。
        ————————————————————————————————
        清除对应的方向标记位。
        """
        if event.key == pygame.K_a or event.key == pygame.K_LEFT:
            self._move_left_flag = False
        elif event.key == pygame.K_d or event.key == pygame.K_RIGHT:
            self._move_right_flag = False
        elif event.key == pygame.K_w or event.key == pygame.K_UP:
            self._move_up_flag = False
        elif event.key == pygame.K_s or event.key == pygame.K_DOWN:
            self._move_down_flag = False
        elif event.key == pygame.K_LSHIFT or event.key == pygame.K_RSHIFT:
            self._boost_flag = False
        elif event.key == pygame.K_SPACE:
            self._is_firing = False  # ⭐ 停止射击
            # 松开空格时若有蓄力 → 发射蓄力强击
            # (由 Game 层读取 charge_level 触发 fire_charged)

    # ====================================================================
    # 每帧更新
    # ====================================================================

    def update(self, dt: float = 0.0, *args, **kwargs) -> None:
        """
        每帧调用：读取键盘输入、计算移动增量、更新位置、切换朝向。
        ————————————————————————————————
        流程：
          ① _update_cooldown(dt) → 更新射击冷却计时器
          ② _read_input()       → 读取键盘状态，计算本帧速度与方向
          ③ 更新 rect 坐标       → 应用移动增量
          ④ _clamp_to_screen()  → 边界钳制
          ⑤ _update_orientation() → 切换倾斜图像
        """
        # ① 更新蓄力值
        self._update_charge(dt)
        # ①.⑤ 更新无敌计时器
        self._update_invincible(dt)
        # ①.⑥ 更新道具 Buff 计时器
        self._update_powerup(dt)

        # ② 读取输入 → 获取 (dx, dy) 移动增量
        dx, dy, move_left, move_right = self._read_input()

        # ③ 更新位置
        self.rect.x += dx
        self.rect.y += dy

        # ④ 边界钳制
        self._clamp_to_screen()

        # ⑤ 朝向切换
        self._update_orientation(move_left, move_right)

        # ⭐ 同步判定点位置
        self._hitbox.center = self.rect.center

    def _update_charge(self, dt: float) -> None:
        """
        更新蓄力值（随时间自动增长）。
        ————————————————————————————————
        RAPID_FIRE 道具：蓄力速度加倍。
        """
        multiplier = 2.0 if PowerUpType.RAPID_FIRE in self._active_powerups else 1.0
        self._charge_level += dt / self._charge_time * multiplier
        if self._charge_level > 1.0:
            self._charge_level = 1.0

    # ====================================================================
    # 输入读取（核心：方案对比）
    # ====================================================================

    def _read_input(self) -> tuple[int, int, bool, bool]:
        """
        读取本帧键盘输入，返回移动增量与方向标记。
        ————————————————————————————————

        【方案A】pygame.key.get_pressed() — 用于连续移动
          - 返回所有按键的瞬时状态数组
          - 每帧轮询，无 OS 键盘重复延迟
          - 按住键时每帧都返回 True → 移动完全平滑
          - ⚠ 适合：持续按住不放的移动操作

        【方案B】KEYDOWN / KEYUP 事件 — 用于单次触发
          - KEYDOWN 在按下瞬间触发一次，然后 OS 开始重复发送
          - 重复发送有初始延迟（~400ms）和重复间隔（~30ms）
          - 移动会有"卡顿-突然连续"的不自然手感
          - ✅ 适合：射击、技能、菜单选择等"按下一次执行一次"的动作

        返回值：
            (dx, dy, move_left, move_right)
            - dx, dy          : int  — 本帧 x/y 方向位移量（像素）
            - move_left/right : bool — 水平方向标记（用于朝向切换）
        """
        # ----【方案A】get_pressed()：无延迟连续移动 ----
        keys: pygame.key.ScancodeWrapper = pygame.key.get_pressed()

        # 方向判断
        move_left: bool = keys[pygame.K_a] or keys[pygame.K_LEFT]
        move_right: bool = keys[pygame.K_d] or keys[pygame.K_RIGHT]
        move_up: bool = keys[pygame.K_w] or keys[pygame.K_UP]
        move_down: bool = keys[pygame.K_s] or keys[pygame.K_DOWN]

        # Shift 加速判断（左右 Shift 都支持）
        boost: bool = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]

        # ---- 计算本帧速度 ----
        current_speed: float = (
            self.base_speed * self.boost_multiplier if boost else self.base_speed
        )
        # 斜向移动时保持速度一致（归一化：dx² + dy² = speed²）
        if (move_left or move_right) and (move_up or move_down):
            current_speed *= 0.707  # ≈ 1/√2

        # ---- 计算移动增量 ----
        dx: int = 0
        dy: int = 0
        if move_left:
            dx -= int(current_speed)
        if move_right:
            dx += int(current_speed)
        if move_up:
            dy -= int(current_speed)
        if move_down:
            dy += int(current_speed)

        # ----【方案B】同步 KEYDOWN/KEYUP 标记位 ----
        # 确保标记位与 get_pressed() 状态一致
        # （如果只用了 get_pressed() 可以不需要这段，这里是为了演示两套系统协同）
        self._move_left_flag = move_left
        self._move_right_flag = move_right
        self._move_up_flag = move_up
        self._move_down_flag = move_down
        self._boost_flag = boost

        return dx, dy, move_left, move_right

    # ====================================================================
    # 朝向控制
    # ====================================================================

    def _update_orientation(self, move_left: bool, move_right: bool) -> None:
        """
        根据水平移动方向切换飞机倾斜图像。
        ————————————————————————————————
        - 仅左移 → 左倾 (逆时针 +20°)
        - 仅右移 → 右倾 (顺时针 -20°)
        - 其他   → 直飞 (0°)

        保存并恢复 rect.center 以避免图像尺寸变化导致飞机"跳动"。
        """
        center: tuple = self.rect.center

        if move_left and not move_right:
            self.image = self._image_left
        elif move_right and not move_left:
            self.image = self._image_right
        else:
            self.image = self._image_straight

        self.rect = self.image.get_rect()
        self.rect.center = center

    # ====================================================================
    # 边界限制
    # ====================================================================

    def _clamp_to_screen(self) -> None:
        """
        将飞机位置钳制到屏幕边界内。
        ————————————————————————————————
        四个方向独立检查，逐边修正：
          - left   < 0           → left   = 0
          - right  > SCREEN_W    → right  = SCREEN_W
          - top    < 0           → top    = 0
          - bottom > SCREEN_H    → bottom = SCREEN_H
        """
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > SCREEN_WIDTH:
            self.rect.right = SCREEN_WIDTH
        if self.rect.top < 0:
            self.rect.top = 0
        if self.rect.bottom > SCREEN_HEIGHT:
            self.rect.bottom = SCREEN_HEIGHT

    # ====================================================================
    # 蓄力射击系统（题7：时间换火力）
    # ====================================================================

    def fire(self) -> list[Bullet]:
        """
        释放蓄力，按当前蓄力等级 + 道具 Buff 发射子弹（⭐ 增强版：不同蓄力等级不同子弹外观）。
        ————————————————————————————————
        基础蓄力等级 → 发射数（子弹样式自动匹配）：
          _charge_level < 40%  → 单发（蓝白能量尖晶 · single）
          _charge_level 40-80% → 双发并排（金色双翼飞弹 · double）
          _charge_level ≥ 80%  → 三发扇形（赤炎三叉戟 · triple）

        道具叠加效果：
          DOUBLE_DAMAGE → 子弹伤害 ×2
          TRIPLE_SPREAD → 始终三发起步，满蓄五发
          PIERCE        → 子弹穿透敌人
          RAPID_FIRE    → 蓄力加速（在 _update_charge 中处理）

        返回值：
            list[Bullet] — 子弹列表
        """
        charge: float = self._charge_level
        self._charge_level = 0.0

        # ---- 道具修饰（可叠加：穿透 + 双倍 + 散射 可同时生效） ----
        active = self._active_powerups
        pierce: bool = PowerUpType.PIERCE in active
        dmg_mult: int = 2 if PowerUpType.DOUBLE_DAMAGE in active else 1
        is_spread: bool = PowerUpType.TRIPLE_SPREAD in active

        damage: int = (PLAYER_BULLET_DAMAGE + self._extra_damage) * dmg_mult
        base_x: float = float(self.rect.centerx)
        base_y: float = float(self.rect.top)

        # 确定子弹样式（基于蓄力等级）
        if charge >= CHARGE_THRESHOLD_TRIPLE:
            bullet_style = "triple"
        elif charge >= CHARGE_THRESHOLD_DOUBLE:
            bullet_style = "double"
        else:
            bullet_style = "single"

        # 弹幕扩散加成（永久升级）
        spread_extra = self._spread_upgrade

        def mkbullet(x, y, style=None):
            return Bullet.create_player_bullet(
                x=x, y=y, damage=damage, piercing=pierce,
                style=style or bullet_style,
            )

        if is_spread:
            base_count = 5 if charge >= CHARGE_THRESHOLD_TRIPLE else 3
            return self._spread_bullets(base_count + spread_extra, base_x, base_y, mkbullet)

        if charge < CHARGE_THRESHOLD_DOUBLE:
            return self._spread_bullets(1 + spread_extra, base_x, base_y, mkbullet)
        elif charge < CHARGE_THRESHOLD_TRIPLE:
            return self._spread_bullets(2 + spread_extra, base_x, base_y, mkbullet)
        else:
            return self._spread_bullets(3 + spread_extra, base_x, base_y, mkbullet)

    # ====================================================================
    # 蓄力进度条可视化（常驻显示，颜色分区指示等级）
    # ====================================================================

    def draw_charge_bar(self, screen: pygame.Surface) -> None:
        """
        在飞机上方绘制蓄力进度条（始终可见）。
        ————————————————————————————————
        颜色分区：
          ████████░░░░░░░░░░░░  红区（0-40%）：单发
          ████████████████░░░░  黄区（40-80%）：双发
          ████████████████████  绿区（80-100%）：三发 → 闪烁提示

        位置：飞机 rect 上方 10 像素
        尺寸：宽度 = 飞机宽度，高度 = 5 像素
        """
        charge: float = self._charge_level

        bar_width: int = self.rect.width
        bar_height: int = 5
        bar_x: int = self.rect.left
        bar_y: int = self.rect.top - 12

        # ---- 背景框 ----
        pygame.draw.rect(screen, GRAY,
                         (bar_x - 1, bar_y - 1, bar_width + 2, bar_height + 2),
                         width=1)

        # ---- 阀值分割线（半透明标记 40% 和 80% 分界） ----
        line_double: int = bar_x + int(bar_width * CHARGE_THRESHOLD_DOUBLE)
        line_triple: int = bar_x + int(bar_width * CHARGE_THRESHOLD_TRIPLE)
        pygame.draw.line(screen, (100, 100, 100),
                         (line_double, bar_y), (line_double, bar_y + bar_height))
        pygame.draw.line(screen, (100, 100, 100),
                         (line_triple, bar_y), (line_triple, bar_y + bar_height))

        # ---- 填充：按蓄力等级着色 ----
        fill_width: int = int(bar_width * charge)
        if fill_width <= 0:
            return

        if charge < CHARGE_THRESHOLD_DOUBLE:
            # 红区：单发
            color: tuple = RED
        elif charge < CHARGE_THRESHOLD_TRIPLE:
            # 黄区：双发
            color = YELLOW
        else:
            # 绿区：三发（闪烁提示可发射）
            if int(time.time() * 4) % 2 == 0:
                color = GREEN
            else:
                color = CYAN  # 绿色/青色交替闪烁

        pygame.draw.rect(screen, color, (bar_x, bar_y, fill_width, bar_height))

        # ---- 等级标签 ----
        font: pygame.font.Font = pygame.font.Font(UI_FONT_PATH, 14)
        if charge >= CHARGE_THRESHOLD_TRIPLE:
            label: str = "三发"
            label_color: tuple = GREEN
        elif charge >= CHARGE_THRESHOLD_DOUBLE:
            label = "双发"
            label_color = YELLOW
        else:
            label = "单发"
            label_color = RED
        label_surf: pygame.Surface = font.render(label, True, label_color)
        label_x: int = bar_x + bar_width + 4
        label_y: int = bar_y - 2
        screen.blit(label_surf, (label_x, label_y))

    # ====================================================================
    # 蓄力状态查询
    # ====================================================================

    @property
    def charge_level(self) -> float:
        """当前蓄力值（0.0~1.0）"""
        return self._charge_level

    @property
    def charge_name(self) -> str:
        """当前蓄力等级名称"""
        if self._charge_level >= CHARGE_THRESHOLD_TRIPLE:
            return "三发"
        elif self._charge_level >= CHARGE_THRESHOLD_DOUBLE:
            return "双发"
        return "单发"

    # ====================================================================
    # 属性查询（供 UI 系统使用）
    # ====================================================================

    # ====================================================================
    # HP 与受伤系统（题10）
    # ====================================================================

    def take_damage(self, amount: int) -> bool:
        """
        受到伤害（⭐ 支持复活机制）。
        ————————————————————————————————
        检查无敌状态：无敌中则忽略伤害。
        扣血后进入无敌状态（1.5秒），防止连续受伤。
        如果 HP 归零且有额外命 → 消耗一命复活。

        返回值：
            bool — True 表示玩家死亡（hp ≤ 0 且无额外命）
        """
        if self._invincible_timer > 0:
            return False  # 无敌中，忽略伤害

        self.hp -= amount
        if self.hp <= 0:
            # ⭐ 复活：消耗一条命，恢复满血
            if self.extra_lives > 0:
                self.extra_lives -= 1
                self.hp = self.max_hp
                self._invincible_timer = 2.0  # 复活后2秒无敌
                self._just_revived = True  # 标记供 Game 层处理特效
                return False  # 没死，复活了
            self.hp = 0
            return True  # 真正死亡

        # 进入无敌状态
        self._invincible_timer = self._invincible_duration
        return False

    def _update_invincible(self, dt: float) -> None:
        """更新无敌计时器"""
        if self._invincible_timer > 0:
            self._invincible_timer -= dt
            if self._invincible_timer < 0:
                self._invincible_timer = 0.0

    # ⭐ 自动连射
    def update_auto_fire(self, dt: float) -> list:
        """
        按住空格时的自动连射逻辑。
        每帧由 Game.update() 调用，返回本帧需要发射的子弹列表。
        连射使用最低蓄力等级（< 40%），不影响蓄力条显示。
        """
        if not self._is_firing:
            self._auto_fire_timer = 0.0
            return []

        self._auto_fire_timer += dt
        if self._auto_fire_timer >= self._auto_fire_interval:
            self._auto_fire_timer -= self._auto_fire_interval
            # 自动连射 = 单发模式（使用当前蓄力但不超过单发阈值）
            charge = self._charge_level
            # 连射消耗蓄力：每次消耗 20% 蓄力
            self._charge_level = max(0.0, self._charge_level - 0.15)
            return self._fire_auto(charge)
        return []

    def _fire_auto(self, charge: float) -> list:
        """自动连射：发射基础子弹（蓄力低于 40% 的单发模式）"""
        active = self._active_powerups
        pierce = PowerUpType.PIERCE in active
        dmg_mult = 2 if PowerUpType.DOUBLE_DAMAGE in active else 1
        is_spread = PowerUpType.TRIPLE_SPREAD in active
        damage = (PLAYER_BULLET_DAMAGE + self._extra_damage) * dmg_mult
        base_x = float(self.rect.centerx)
        base_y = float(self.rect.top)
        spread_extra = self._spread_upgrade

        def mk(x, y, style="single"):
            return Bullet.create_player_bullet(x=x, y=y, damage=damage,
                                              piercing=pierce, style=style)

        if is_spread:
            total = 3 + spread_extra
            return self._spread_bullets(total, base_x, base_y, mk)

        return self._spread_bullets(1 + spread_extra, base_x, base_y, mk)

    @staticmethod
    def _spread_bullets(count, center_x, base_y_pos, factory):
        """生成 count 枚水平扩散的子弹"""
        if count <= 1:
            return [factory(center_x, base_y_pos)]
        spacing = 7
        start = center_x - spacing * (count - 1) / 2.0
        bullets = []
        for i in range(count):
            bx = start + spacing * i
            by_offset = abs(i - (count - 1) / 2.0) * 0.5
            bullets.append(factory(bx, base_y_pos + int(by_offset)))
        return bullets

    # ====================================================================
    # 道具 Buff 管理（题18）
    # ====================================================================

    def apply_powerup(self, ptype, duration: float = POWERUP_DURATION) -> str:
        """
        应用道具效果。
        ————————————————————————————————
        即时型（HEALTH/BOMB）立即生效并返回触发标记。
        持续型（火力量）可叠加：新增/续期对应 Buff，多个 Buff 独立计时。
        """
        if ptype == PowerUpType.HEALTH:
            if self.hp < self.max_hp:
                self.hp += 1
            return "health"
        elif ptype == PowerUpType.BOMB:
            if self.bomb_count < self.max_bombs:
                self.bomb_count += 1
                return "bomb"
            return "bomb_full"  # 炸弹已满，提示
        else:
            # 火力道具叠加：续期已有或新增独立计时
            self._active_powerups[ptype] = max(
                self._active_powerups.get(ptype, 0.0), duration
            )
            return "buff"

    def _update_powerup(self, dt: float) -> None:
        """更新所有道具 Buff 倒计时，过期自动移除。"""
        expired: list[PowerUpType] = []
        for ptype in list(self._active_powerups):
            self._active_powerups[ptype] -= dt
            if self._active_powerups[ptype] <= 0:
                expired.append(ptype)
        for ptype in expired:
            del self._active_powerups[ptype]

    @property
    def active_powerup(self) -> PowerUpType | None:
        """保留兼容：返回第一个持续型道具类型（光晕等用途）。"""
        if self._active_powerups:
            return next(iter(self._active_powerups))
        return None

    @property
    def active_powerups(self) -> dict[PowerUpType, float]:
        """返回所有活跃道具及其剩余时间（只读副本）。"""
        return dict(self._active_powerups)

    @property
    def powerup_timer(self) -> float:
        """返回最长剩余时间（秒）。"""
        if self._active_powerups:
            return max(self._active_powerups.values())
        return 0.0

    @property
    def is_invincible(self) -> bool:
        """是否处于无敌状态"""
        return self._invincible_timer > 0

    def draw_powerup_glow(self, screen: pygame.Surface) -> None:
        """在玩家周围绘制所有活跃道具 Buff 发光效果（叠加显示）。"""
        if not self._active_powerups:
            return
        from settings import POWERUP_COLORS
        cx, cy = self.rect.center
        radius = max(self.rect.width, self.rect.height) // 2 + 4
        # 每个活跃 Buff 绘制一层光环（错开半径）
        for i, (ptype, timer) in enumerate(self._active_powerups.items()):
            color = POWERUP_COLORS.get(ptype, (255, 255, 255))
            alpha_val = int(50 + 30 * math.sin(time.time() * 5 + i * 1.2))
            r = radius + 6 + i * 9
            glow_surf = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            # 外圈脉冲
            pulse = 1.0 + 0.08 * math.sin(time.time() * 6 + i)
            pr = int(r * pulse)
            pygame.draw.circle(glow_surf, (*color, alpha_val // 2), (r, r), pr, width=2)
            # 内圈填充
            pygame.draw.circle(glow_surf, (*color, alpha_val), (r, r), max(2, pr - 4))
            screen.blit(glow_surf, (cx - r, cy - r))

    @property
    def is_dead(self) -> bool:
        """玩家是否已死亡"""
        return self.hp <= 0

    @property
    def hitbox(self) -> pygame.Rect:
        """返回判定点矩形（供碰撞检测使用）"""
        return self._hitbox

    def toggle_hitbox_visible(self) -> None:
        """F1 切换判定点可视化"""
        self._show_hitbox = not self._show_hitbox

    def use_bomb(self) -> bool:
        """使用一颗炸弹。返回 True 表示成功使用。"""
        if self.bomb_count > 0:
            self.bomb_count -= 1
            return True
        return False

    def draw_hitbox(self, screen: pygame.Surface) -> None:
        """绘制判定点（调试用，F1 切換）"""
        if self._show_hitbox:
            pygame.draw.circle(screen, WHITE, self._hitbox.center, 3, width=1)
            pygame.draw.circle(screen, (255, 255, 255, 80), self._hitbox.center, 8, width=1)

    def draw_hp_bar(self, screen: pygame.Surface) -> None:
        """
        在屏幕左上角绘制 HP 条。
        ————————————————————————————————
        左侧显示红色血条，右侧显示 "HP 3/5" 文字。
        """
        bar_x: int = 8
        bar_y: int = 52
        bar_w: int = 120
        bar_h: int = 10

        # 背景框
        pygame.draw.rect(screen, GRAY,
                         (bar_x - 1, bar_y - 1, bar_w + 2, bar_h + 2), width=1)
        # 血量填充（红→绿渐变）
        hp_ratio: float = self.hp / self.max_hp
        fill_w: int = int(bar_w * hp_ratio)
        if hp_ratio > 0.5:
            color: tuple = GREEN
        elif hp_ratio > 0.25:
            color = YELLOW
        else:
            color = RED
        if fill_w > 0:
            pygame.draw.rect(screen, color, (bar_x, bar_y, fill_w, bar_h))

        # 文字
        font: pygame.font.Font = pygame.font.Font(UI_FONT_PATH, 20)
        hp_text: str = f"HP {self.hp}/{self.max_hp}"
        hp_surf: pygame.Surface = font.render(hp_text, True, WHITE)
        screen.blit(hp_surf, (bar_x + bar_w + 6, bar_y - 1))

    # ====================================================================
    # 属性查询（供 UI 系统使用）
    # ====================================================================

    @property
    def is_boosting(self) -> bool:
        """当前是否处于加速状态"""
        return self._boost_flag

    @property
    def current_speed(self) -> float:
        """当前实际速度（考虑加速状态）"""
        return self.base_speed * self.boost_multiplier if self._boost_flag else float(self.base_speed)
