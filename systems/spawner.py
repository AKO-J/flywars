"""
==============================================================================
飞机大战 — 敌人生成器（⭐ 波次制：每关由若干波次组成）
==============================================================================
替代旧的纯定时生成，改为波次驱动：
  1. 每关有固定波次列表（LEVEL_WAVES）
  2. 每波由敌机组编队组成（如 3普通+2快速）
  3. 波内敌机逐一生成，间隔恒定
  4. 波次清空后进入休息，然后下一波
  5. 所有波次完成后触发 Boss 战

设计原则：
  - Spawner 只负责生成，不关心碰撞/得分
  - Game 层通过 is_wave_cleared / current_boss 获取状态
  - 难度缩放在生成时应用于单个敌机属性
"""

import random
import math
import pygame
from settings import (
    SCREEN_WIDTH,
    ENEMY_NORMAL_SPEED, ENEMY_FAST_SPEED,
    ENEMY_ELITE_SPEED, ENEMY_TRACKING_SPEED,
    ENEMY_NORMAL_FIRE_INTERVAL, ENEMY_FAST_FIRE_INTERVAL,
    ENEMY_ELITE_FIRE_INTERVAL, ENEMY_TRACKING_FIRE_INTERVAL,
    BOSS_SPAWN_LEVEL,
    DIFFICULTY_SPAWN_INTERVAL_SCALE, DIFFICULTY_SPEED_SCALE,
    DIFFICULTY_HP_SCALE, DIFFICULTY_FIRE_RATE_SCALE,
    DIFFICULTY_NONLINEAR_EXP,
    SPAWN_INTERVAL_MIN,
    LEVEL_WAVES, WAVE_REST_DURATION, WAVE_ANNOUNCE_DURATION,
    FINAL_BOSS_LEVEL,
    FormationType, FORMATION_DEFAULTS, FORMATION_SPAWN_INTERVAL,
)
from sprites.enemy import NormalEnemy, FastEnemy, EliteEnemy, TrackingEnemy, BossEnemy


class Spawner:
    """
    波次制敌机生成器。

    用法：
        spawner = Spawner()
        spawner.set_player(player)
        spawner.set_level(1)
        while running:
            boss = spawner.update(dt, enemy_group, all_sprites)
            ...

    属性（供 Game/HUD 读取）：
        .level          — 当前关卡
        .current_wave   — 当前波次索引（从0开始）
        .total_waves    — 本关总波次数
        .wave_cleared   — 当前波次是否已清空
        .rest_timer     — 波间休息倒计时
        .boss_active    — Boss 是否在场
        .wave_announce  — 波次提示剩余显示时间
    """

    def __init__(self) -> None:
        # 玩家引用
        self._player: pygame.sprite.Sprite | None = None

        # ---- 关卡/波次状态 ----
        self._level: int = 1
        self._wave_index: int = 0
        self._wave_config: list[list[tuple[str, int]]] = []  # 当前关卡的波次列表
        self._spawn_interval: float = 0.8  # 波内敌机生成间隔
        self._total_waves: int = 0
        self._has_boss: bool = False
        self._is_final: bool = False

        # 当前波次尚未生成的敌机队列（随机排列）
        self._spawn_queue: list[str] = []
        self._spawn_positions: list[tuple[float, float]] = []  # ⭐ 阵型位置队列
        self._is_formation_wave: bool = False  # ⭐ 当前波次是否为阵型波
        self._spawn_timer: float = 0.0

        # 波间休息
        self._rest_timer: float = 0.0
        self._is_resting: bool = False
        self._wave_announce_timer: float = 0.0

        # Boss 状态
        self._boss_active: bool = False
        self._boss_spawned: bool = False  # 本关 Boss 是否已生成

        # 统计
        self.total_spawned: int = 0
        self.type_counts: dict[str, int] = {
            "normal": 0, "fast": 0, "elite": 0, "tracking": 0,
        }
        # ⭐ 无尽模式难度倍率（默认1.0）
        self._endless_mult: float = 1.0
        # 本关已消灭敌机数（用于波次清空检测）
        self.kills_this_level: int = 0
        self._alive_count: int = 0  # 当前在场敌机数
        # ⭐ 波次击杀追踪（需全部击杀才推进）
        self._wave_spawned: int = 0      # 本波已生成敌机数
        self._wave_killed: int = 0       # 本波已消灭敌机数
        self._wave_last_spawn: float = 0.0  # 本波最后一只生成时间
        self._wave_timeout: float = 8.0       # 安全超时
        self._timeout_warned: bool = False    # ⭐ 每波只警告一次

        # 预加载关卡1配置
        self.set_level(1)

    # ================================================================
    # 公共接口
    # ================================================================

    def set_player(self, player: pygame.sprite.Sprite) -> None:
        self._player = player

    def set_level(self, level: int) -> None:
        """切换到指定关卡，重置波次状态。"""
        self._level = level
        level_def = LEVEL_WAVES.get(level, LEVEL_WAVES[1])
        self._wave_config = list(level_def["waves"])
        self._spawn_interval = level_def["spawn_interval"]
        self._has_boss = level_def.get("has_boss", False)
        self._is_final = level_def.get("final", False)
        self._total_waves = len(self._wave_config)
        self._wave_index = 0
        self._is_resting = False
        self._rest_timer = 0.0
        self._boss_active = False
        self._boss_spawned = False
        self.kills_this_level = 0
        self._wave_announce_timer = 0.0
        self._timeout_warned = False  # ⭐
        self._build_spawn_queue()

    def on_enemy_killed(self) -> None:
        """由 Game 碰撞系统调用，记录本关击杀。"""
        self.kills_this_level += 1
        self._wave_killed += 1  # ⭐ 本波击杀

    def on_boss_defeated(self) -> None:
        """Boss 被击毁后调用。"""
        self._boss_active = False

    def reset(self) -> None:
        """完全重置。"""
        self._level = 1
        self._wave_index = 0
        self._spawn_queue.clear()
        self._spawn_positions.clear()
        self._is_formation_wave = False
        self._spawn_timer = 0.0
        self._rest_timer = 0.0
        self._is_resting = False
        self._boss_active = False
        self._boss_spawned = False
        self.total_spawned = 0
        self.kills_this_level = 0
        self._wave_killed = 0
        self._timeout_warned = False
        self._alive_count = 0
        self.type_counts = {k: 0 for k in self.type_counts}
        self._wave_announce_timer = 0.0
        self._endless_mult = 1.0
        self.set_level(1)

    # ================================================================
    # 状态查询（供 Game / HUD 使用）
    # ================================================================

    @property
    def level(self) -> int:
        return self._level

    @property
    def current_wave(self) -> int:
        return self._wave_index

    @property
    def total_waves(self) -> int:
        return self._total_waves

    @property
    def wave_cleared(self) -> bool:
        """当前波次是否已清空 — 需生成队列为空且场上无敌机存活。"""
        return len(self._spawn_queue) == 0

    @property
    def is_resting(self) -> bool:
        return self._is_resting

    @property
    def boss_active(self) -> bool:
        return self._boss_active

    @property
    def is_final_level(self) -> bool:
        return self._is_final

    @property
    def all_waves_done(self) -> bool:
        """所有波次是否已完成（含 Boss 已生成/击败）。"""
        return self._wave_index >= self._total_waves

    @property
    def level_complete(self) -> bool:
        """本关是否完成（波次清完 + Boss 已击败/无需 Boss）。"""
        if not self.all_waves_done:
            return False
        if self._has_boss and self._boss_active:
            return False
        if self._has_boss and not self._boss_spawned:
            return False
        return True

    # ================================================================
    # 主更新
    # ================================================================

    def update(
        self,
        dt: float,
        enemy_group: pygame.sprite.Group,
        all_sprites: pygame.sprite.Group,
    ) -> BossEnemy | None:
        """
        更新生成逻辑。
        返回值：新生成的 Boss（None 表示无）。
        """
        new_boss: BossEnemy | None = None

        # ---- 波间休息 ----
        if self._is_resting:
            self._rest_timer -= dt
            if self._rest_timer <= 0:
                self._is_resting = False
                self._wave_index += 1
                self._wave_announce_timer = WAVE_ANNOUNCE_DURATION
                if self._wave_index < self._total_waves:
                    self._build_spawn_queue()
                # 所有波次完成 → 生成 Boss
                elif self._has_boss:
                    new_boss = self._spawn_boss(enemy_group, all_sprites)
                    # ⭐ Boss 出场时清除场上残留小怪
                    for e in list(enemy_group):
                        if not isinstance(e, BossEnemy):
                            e.kill()
            return new_boss

        # ---- 波次提示显示 ----
        if self._wave_announce_timer > 0:
            self._wave_announce_timer -= dt

        # ---- 检查波次是否已全部消灭（⭐ 击杀制） ----
        if self.wave_cleared:
            # ⭐ 必须击杀所有敌机（或超时兜底）
            all_killed = self._wave_killed >= self._wave_spawned
            now_ticks = pygame.time.get_ticks() / 1000.0
            timed_out = self._wave_spawned > 0 and (now_ticks - self._wave_last_spawn) > self._wave_timeout
            
            if not all_killed and not timed_out:
                return new_boss  # 还在等击杀，不放行
            if not all_killed and timed_out:
                if not self._timeout_warned:
                    print(f"[Spawner] ⚠ 超时 {self._wave_timeout}s 强制推进 (已杀 {self._wave_killed}/{self._wave_spawned})")
                    self._timeout_warned = True
            
            # ⭐ 如果 Boss 已生成，不再重复触发
            if self._boss_spawned:
                return new_boss
            # 走完所有波次
            if self._wave_index >= self._total_waves - 1:
                if not self._has_boss:
                    # 无 Boss 关 → 直接标记完成
                    self._wave_index = self._total_waves
                else:
                    # ⭐ 有 Boss 关 → 进入短暂休息后出 Boss
                    self._is_resting = True
                    self._rest_timer = WAVE_REST_DURATION
                return new_boss
            # 进入波间休息
            self._is_resting = True
            self._rest_timer = WAVE_REST_DURATION
            return new_boss

        # ---- 生成敌机（⭐ 支持阵型位置 + 阵型快速序列） ----
        self._spawn_timer += dt
        current_interval = FORMATION_SPAWN_INTERVAL if self._is_formation_wave else self._spawn_interval
        if self._spawn_timer >= current_interval and self._spawn_queue:
            self._spawn_timer -= current_interval
            etype = self._spawn_queue.pop(0)
            # 取阵型位置（如果有的话）
            pos_x = pos_y = None
            if self._spawn_positions:
                pos_x, pos_y = self._spawn_positions.pop(0)
            enemy = self._make_enemy(etype, pos_x, pos_y)
            if enemy is not None:
                enemy_group.add(enemy)
                all_sprites.add(enemy)
                self.total_spawned += 1
                self.type_counts[etype] = self.type_counts.get(etype, 0) + 1
                # ⭐ 追踪本波生成
                self._wave_spawned += 1
                self._wave_last_spawn = pygame.time.get_ticks() / 1000.0

        return new_boss

    # ================================================================
    # 内部
    # ================================================================

    def _build_spawn_queue(self) -> None:
        """生成当前波次的敌机队列（支持阵型）。"""
        # ⭐ 新波次重置
        self._wave_killed = 0
        self._wave_spawned = 0
        self._wave_last_spawn = 0.0
        self._timeout_warned = False
        if self._wave_index >= len(self._wave_config):
            self._spawn_queue = []
            self._spawn_positions = []
            return
        wave = self._wave_config[self._wave_index]

        # 检测新旧格式
        if isinstance(wave, dict):
            units = wave.get("units", [])
            formation_name = wave.get("formation", "none")
            params = wave.get("params", {})
        else:
            units = wave
            formation_name = "none"
            params = {}

        # 展开成平铺列表
        flat: list[str] = []
        for etype, count in units:
            flat.extend([etype] * count)

        if formation_name == "none" or formation_name not in FORMATION_DEFAULTS:
            # 无阵型：随机排列，随机位置（原有行为）
            random.shuffle(flat)
            self._spawn_queue = flat
            self._spawn_positions = []
            self._is_formation_wave = False
        else:
            # 有阵型：计算位置，保持顺序（先出先入阵）
            merged = {**FORMATION_DEFAULTS[formation_name], **params}
            positions = self._compute_formation_positions(
                formation_name, len(flat), merged
            )
            self._spawn_queue = flat
            self._spawn_positions = positions
            self._is_formation_wave = True

        self._spawn_timer = 0.0
        # ⭐ 重置本波击杀追踪
        self._wave_spawned = 0
        self._wave_killed = 0
        self._wave_last_spawn = 0.0

    # ================================================================
    # ⭐ 阵型位置计算
    # ================================================================

    def _compute_formation_positions(
        self, formation: str, count: int, params: dict,
    ) -> list[tuple[float, float]]:
        """
        根据阵型类型和参数计算每个敌机的生成位置。
        返回 [(x, y), ...] 列表，顺序与 _spawn_queue 对应。
        """
        sw = SCREEN_WIDTH
        spacing = params.get("spacing", 40)
        width = params.get("width", min(300, sw - 80))
        entry_y = params.get("entry_y", -60)
        cx = sw / 2
        cy = entry_y

        if count == 0:
            return []
        if count == 1:
            return [(cx, cy)]

        positions: list[tuple[float, float]] = []

        if formation == "line":
            # 一字横排：均匀分布
            start_x = cx - width / 2
            for i in range(count):
                x = start_x + i * (width / (count - 1))
                positions.append((x, cy + (i % 2) * 8))  # 微微交错

        elif formation == "vshape":
            # V字楔形：中间低，两边高（增加深度让V更明显）
            for i in range(count):
                t = -1.0 + 2.0 * i / (count - 1) if count > 1 else 0.0
                x = cx + t * width / 2
                y = cy + abs(t) * spacing * 1.2
                positions.append((x, y))

        elif formation == "triangle":
            # 三角形：多行，每行递增
            row = 0
            placed = 0
            while placed < count:
                in_this_row = min(row + 1, count - placed)
                row_width = (in_this_row - 1) * spacing
                start_x = cx - row_width / 2
                for i in range(in_this_row):
                    if placed < count:
                        x = start_x + i * spacing
                        y = cy + row * spacing * 0.7
                        positions.append((x, y))
                        placed += 1
                row += 1

        elif formation == "arc":
            # 弧线：彩虹弧（宽幅水平展开）
            half_range = width / 2
            for i in range(count):
                t = -1.0 + 2.0 * i / (count - 1) if count > 1 else 0.0
                x = cx + t * half_range
                # y 在中间高两边低（拱形）
                depth = abs(t) * spacing * 0.6
                y = cy + depth
                positions.append((x, y))

        elif formation == "cross":
            # X形交叉：两条对角线
            half = count // 2
            for i in range(count):
                if i < half:
                    t = -1.0 + 2.0 * i / (half - 1) if half > 1 else 0.0
                    x = cx + t * width / 2
                    y = cy + abs(t) * spacing * 1.2
                else:
                    idx = i - half
                    t = -1.0 + 2.0 * idx / (count - half - 1) if (count - half) > 1 else 0.0
                    x = cx + t * width / 2
                    y = cy + (1.0 - abs(t)) * spacing * 1.2
                positions.append((x, y))

        elif formation == "surround":
            # 包围：左右两侧各一半，呈包围状
            half = count // 2
            for i in range(count):
                if i < half:
                    # 左侧: 从左上到中下
                    t = i / max(half - 1, 1)
                    x = 20 + t * (cx - 40)
                    y = cy + t * spacing * 0.5
                else:
                    # 右侧: 从右上到中下
                    t = (i - half) / max(count - half - 1, 1)
                    x = sw - 20 - t * (sw - cx - 40)
                    y = cy + t * spacing * 0.5
                positions.append((x, y))

        # 保底：确保所有位置都在屏幕范围内
        for i, (px, py) in enumerate(positions):
            positions[i] = (max(5, min(sw - 5, px)), py)

        return positions

    def _make_enemy(self, etype: str, pos_x: float | None = None, pos_y: float | None = None):
        """按类型和难度缩放生成敌机（⭐ 支持指定位置）。"""
        # 非线性难度：前期平缓，后期陡升
        effective_level = self._level ** DIFFICULTY_NONLINEAR_EXP
        speed_scale = DIFFICULTY_SPEED_SCALE ** (effective_level - 1)
        hp_scale = DIFFICULTY_HP_SCALE ** (effective_level - 1)
        fire_scale = DIFFICULTY_FIRE_RATE_SCALE ** (effective_level - 1)

        try:
            if etype == "normal":
                e = NormalEnemy(x=pos_x, y=pos_y,
                                fire_interval=ENEMY_NORMAL_FIRE_INTERVAL * fire_scale)
            elif etype == "fast":
                e = FastEnemy(x=pos_x, y=pos_y,
                              fire_interval=ENEMY_FAST_FIRE_INTERVAL * fire_scale)
            elif etype == "elite":
                e = EliteEnemy(x=pos_x, y=pos_y,
                               fire_interval=ENEMY_ELITE_FIRE_INTERVAL * fire_scale)
                if self._player is not None:
                    e.set_player(self._player)
            elif etype == "tracking":
                e = TrackingEnemy(self._player, x=pos_x, y=pos_y,
                                  fire_interval=ENEMY_TRACKING_FIRE_INTERVAL * fire_scale)
            else:
                return None

            e.speed *= speed_scale * self._endless_mult
            e.hp = max(1, int(e.hp * hp_scale * self._endless_mult))
            e.max_hp = e.hp
            # ⭐ 无尽模式：敌机更快更硬
            if self._endless_mult > 1.0:
                e._fire_interval = max(0.3, e._fire_interval / self._endless_mult)
            return e
        except Exception as ex:
            print(f"[Spawner] 生成 {etype} 失败: {ex}")
            return None

    def _spawn_boss(
        self,
        enemy_group: pygame.sprite.Group,
        all_sprites: pygame.sprite.Group,
    ) -> BossEnemy | None:
        """生成本关 Boss。"""
        try:
            boss = BossEnemy(self._player, self._level)
            enemy_group.add(boss)
            all_sprites.add(boss)
            self._boss_active = True
            self._boss_spawned = True
            self.total_spawned += 1
            return boss
        except Exception as e:
            print(f"[Spawner] Boss 生成失败: {e}")
            return None
