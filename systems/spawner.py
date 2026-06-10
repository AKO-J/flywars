"""
==============================================================================
飞机大战 — 敌人生成器（题9：四种敌机类型 + 题15：难度递增与Boss战）
==============================================================================
管理四种敌机类型的定时生成 + 关卡难度递增 + Boss 战触发。

难度递增公式（每升一级）：
  生成间隔 ×= DIFFICULTY_SPAWN_INTERVAL_SCALE（≤ SPAWN_INTERVAL_MIN 则钳位）
  敌机速度 ×= DIFFICULTY_SPEED_SCALE
  敌机 HP   ×= DIFFICULTY_HP_SCALE

Boss 战：
  第 BOSS_SPAWN_LEVEL 关触发 Boss（且每 BOSS_SPAWN_LEVEL 关后再触发）
  同一时间只有一个 Boss 存活。
"""

import pygame
from settings import (
    SCREEN_WIDTH,
    ENEMY_NORMAL_SPAWN_INTERVAL, ENEMY_FAST_SPAWN_INTERVAL,
    ENEMY_ELITE_SPAWN_INTERVAL, ENEMY_TRACKING_SPAWN_INTERVAL,
    BOSS_SPAWN_LEVEL,
    DIFFICULTY_SPAWN_INTERVAL_SCALE, DIFFICULTY_SPEED_SCALE, DIFFICULTY_HP_SCALE,
    SPAWN_INTERVAL_MIN,
)
from sprites.enemy import NormalEnemy, FastEnemy, EliteEnemy, TrackingEnemy, BossEnemy


class Spawner:
    """
    敌机定时生成器（关卡感知）。

    用法：
        spawner = Spawner()
        spawner.set_player(player)
        spawner.set_level(level)
        while running:
            boss = spawner.update(dt, enemy_group, all_sprites)
            if boss:
                new_bullets = boss.fire(dt)
                ...
    """

    def __init__(self) -> None:
        # 基础生成间隔
        self._base_intervals: dict[str, float] = {
            "normal":   ENEMY_NORMAL_SPAWN_INTERVAL,
            "fast":     ENEMY_FAST_SPAWN_INTERVAL,
            "elite":    ENEMY_ELITE_SPAWN_INTERVAL,
            "tracking": ENEMY_TRACKING_SPAWN_INTERVAL,
        }

        # 当前生成间隔（随关卡缩放）
        self._intervals: dict[str, float] = dict(self._base_intervals)

        # 独立计时器（秒）
        self._timers: dict[str, float] = {
            "normal":   0.0,
            "fast":     0.0,
            "elite":    0.0,
            "tracking": 0.0,
        }

        # 玩家引用
        self._player: pygame.sprite.Sprite | None = None

        # 关卡
        self._level: int = 1

        # Boss 状态
        self._boss_active: bool = False

        # 统计
        self.total_spawned: int = 0
        self.type_counts: dict[str, int] = {
            "normal": 0, "fast": 0, "elite": 0, "tracking": 0,
        }

    # ================================================================
    # 公共接口
    # ================================================================

    def set_player(self, player: pygame.sprite.Sprite) -> None:
        self._player = player

    def set_level(self, level: int) -> None:
        """设置当前关卡，自动重算生成间隔。"""
        if level == self._level:
            return
        self._level = level
        # 缩放生成间隔
        scale = DIFFICULTY_SPAWN_INTERVAL_SCALE ** (level - 1)
        for key in self._intervals:
            val = self._base_intervals[key] * scale
            self._intervals[key] = max(val, SPAWN_INTERVAL_MIN)

    @property
    def level(self) -> int:
        return self._level

    @property
    def boss_active(self) -> bool:
        return self._boss_active

    def on_boss_defeated(self) -> None:
        """Boss 被击毁后调用。"""
        self._boss_active = False

    def update(
        self,
        dt: float,
        enemy_group: pygame.sprite.Group,
        all_sprites: pygame.sprite.Group,
    ) -> BossEnemy | None:
        """
        更新所有计时器，生成敌机和 Boss。

        返回值：
            BossEnemy | None — 新生成的 Boss（供 Game 层跟踪 fire）
        """
        new_boss: BossEnemy | None = None

        # ---- Boss 生成检测 ----
        if self._should_spawn_boss():
            boss = self._spawn_boss(enemy_group, all_sprites)
            if boss is not None:
                new_boss = boss

        # ---- 普通敌机 ----
        speed_scale = DIFFICULTY_SPEED_SCALE ** (self._level - 1)
        hp_scale = DIFFICULTY_HP_SCALE ** (self._level - 1)

        self._spawn_if_ready("normal", dt, enemy_group, all_sprites,
                             lambda: self._make_normal(speed_scale, hp_scale))
        self._spawn_if_ready("fast", dt, enemy_group, all_sprites,
                             lambda: self._make_fast(speed_scale, hp_scale))
        self._spawn_if_ready("elite", dt, enemy_group, all_sprites,
                             lambda: self._make_elite(speed_scale, hp_scale))
        self._spawn_if_ready("tracking", dt, enemy_group, all_sprites,
                             lambda: self._make_tracking(speed_scale, hp_scale))

        return new_boss

    def reset(self) -> None:
        for key in self._timers:
            self._timers[key] = 0.0
        self.total_spawned = 0
        for key in self.type_counts:
            self.type_counts[key] = 0
        self._level = 1
        self._boss_active = False
        self._intervals = dict(self._base_intervals)

    # ================================================================
    # Boss 生成
    # ================================================================

    def _should_spawn_boss(self) -> bool:
        if self._boss_active:
            return False
        return self._level >= BOSS_SPAWN_LEVEL and self._level % BOSS_SPAWN_LEVEL == 0

    def _spawn_boss(
        self,
        enemy_group: pygame.sprite.Group,
        all_sprites: pygame.sprite.Group,
    ) -> BossEnemy | None:
        try:
            boss = BossEnemy(self._player, self._level)
            enemy_group.add(boss)
            all_sprites.add(boss)
            self._boss_active = True
            self.total_spawned += 1
            return boss
        except Exception as e:
            print(f"[Spawner] Boss 生成失败: {e}")
            return None

    # ================================================================
    # 内部
    # ================================================================

    def _spawn_if_ready(
        self,
        key: str,
        dt: float,
        enemy_group: pygame.sprite.Group,
        all_sprites: pygame.sprite.Group,
        factory,
    ) -> None:
        self._timers[key] += dt
        while self._timers[key] >= self._intervals[key]:
            self._timers[key] -= self._intervals[key]
            try:
                enemy = factory()
            except Exception as e:
                print(f"[Spawner] 敌机生成失败 ({key}): {e}")
                continue
            enemy_group.add(enemy)
            all_sprites.add(enemy)
            self.total_spawned += 1
            self.type_counts[key] += 1

    # ================================================================
    # 工厂方法（带难度缩放）
    # ================================================================

    @staticmethod
    def _scale_enemy(enemy, speed_scale: float, hp_scale: float):
        enemy.speed *= speed_scale
        enemy.hp = int(enemy.hp * hp_scale)
        enemy.max_hp = enemy.hp

    def _make_normal(self, speed_scale: float, hp_scale: float) -> NormalEnemy:
        e = NormalEnemy()
        self._scale_enemy(e, speed_scale, hp_scale)
        return e

    def _make_fast(self, speed_scale: float, hp_scale: float) -> FastEnemy:
        e = FastEnemy()
        self._scale_enemy(e, speed_scale, hp_scale)
        return e

    def _make_elite(self, speed_scale: float, hp_scale: float) -> EliteEnemy:
        e = EliteEnemy()
        self._scale_enemy(e, speed_scale, hp_scale)
        return e

    def _make_tracking(self, speed_scale: float, hp_scale: float) -> TrackingEnemy:
        e = TrackingEnemy(self._player)
        self._scale_enemy(e, speed_scale, hp_scale)
        return e
