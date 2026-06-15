"""
==============================================================================
飞机大战 — 碰撞检测系统（题10：子弹命中与玩家受伤 + 题15：Boss碰撞）
==============================================================================
封装所有碰撞检测逻辑，使用 pygame 内置碰撞 API：

  1. groupcollide()   — 玩家子弹 vs 敌机组（多对多）
  2. spritecollide()  — 玩家 vs 敌机组（一对一，含 Boss）
  3. spritecollide()  — 玩家 vs 敌人子弹（题15新增）

处理流程：
  玩家子弹命中敌机 → 敌机扣血 → 死亡 → 加分 + 爆炸
  玩家碰撞敌机     → 玩家扣血 → 无敌帧（Boss 不死亡）
  敌人子弹命中玩家 → 玩家扣血 → 无敌帧
"""

import random
import pygame
from settings import (
    ENEMY_COLLISION_DAMAGE,
    POWERUP_DROP_CHANCE, POWERUP_ELITE_DROP_CHANCE,
    POWERUP_BOSS_DROP_COUNT,
    PowerUpType,
    XP_NORMAL, XP_FAST, XP_ELITE, XP_TRACKING, XP_BOSS,
)
from sprites.bullet import BulletSource
from sprites.player import Player
from sprites.enemy import Enemy, BossEnemy, EliteEnemy, TrackingEnemy, FastEnemy, NormalEnemy
# ⭐ 空间哈希加速
from systems.spatial_hash import SpatialHash


def _explosion_size(enemy: Enemy) -> str:
    """根据敌机类型返回爆炸尺寸：normal/big/huge。"""
    if isinstance(enemy, BossEnemy):
        return "huge"
    elif isinstance(enemy, (EliteEnemy, TrackingEnemy)):
        return "big"
    return "normal"


class CollisionSystem:
    """
    碰撞检测与处理。

    每帧调用 handle_all()，内部依次执行三个检测步骤。
    """

    def __init__(self) -> None:
        self.score: int = 0
        self.explosion_positions: list[tuple[int, int]] = []
        self.floating_texts: list[tuple[int, int, int]] = []
        # Boss 击毁标记（供 Game 层检测升级）
        self.boss_defeated: bool = False
        # Boss 死亡爆炸位置（题19：供主循环生成连续爆炸）
        self.boss_death_positions: list[tuple[int, int]] = []
        # 道具掉落列表（题18）：[(x, y, PowerUpType), ...]
        self.drops: list[tuple[int, int, PowerUpType]] = []
        self.kills_this_frame: int = 0  # 本帧击杀数（供网络同步）
        # ⭐ 本局累计经验（供成长系统）
        self.xp_earned: int = 0
        # ⭐ 命中火花位置（含伤害值）
        self.hit_sparks: list[dict] = []
        # ⭐ Combo 加分飘字 [(x, y, bonus), ...]
        self.combo_bonus_texts: list[tuple[int, int, int]] = []
        # ⭐ 空间哈希（精灵数多时启用）
        self._spatial: SpatialHash = SpatialHash(cell_size=64)
        self._spatial_enabled: bool = True  # ⭐ 空间哈希已启用
        # ⭐ 当前关卡（用于缩放经验获取）
        self.current_level: int = 1

        # ⭐ Combo 连击系统
        self.combo_count: int = 0           # 当前连击数
        self.combo_timer: float = 0.0       # 连击计时（超时重置）
        self.combo_timeout: float = 2.0     # 连击超时（秒）
        self.combo_multiplier: int = 1      # 当前倍率
        self.combo_peak: int = 0            # 本局最高连击
        self.combo_just_broke: bool = False  # 本帧刚断连

    # ================================================================
    # 公共入口
    # ================================================================

    def handle_all(
        self,
        bullets_group: pygame.sprite.Group,
        enemies_group: pygame.sprite.Group,
        player: Player,
        dt: float = 1.0 / 60.0,  # ⭐ 新增：用于 combo 计时
    ) -> bool:
        """
        执行所有碰撞检测。

        返回值：
            bool — True=继续游戏, False=玩家死亡
        """
        self.explosion_positions.clear()
        self.floating_texts.clear()
        self.boss_defeated = False
        self.boss_death_positions.clear()
        self.drops.clear()
        self.kills_this_frame = 0
        self.hit_sparks.clear()
        self.combo_bonus_texts.clear()

        # ⭐ 更新 combo 计时器
        self._update_combo(dt)

        self._handle_bullet_enemy(bullets_group, enemies_group)
        self._handle_player_enemy(player, enemies_group)
        self._handle_player_enemy_bullet(player, bullets_group)

        game_over = player.is_dead
        return not game_over

    # ════════════════════════════════════════════════════════════════
    # ⭐ Combo 连击系统
    # ════════════════════════════════════════════════════════════════

    def _update_combo(self, dt: float) -> None:
        """更新连击计时器，超时重置。"""
        self.combo_just_broke = False
        if self.combo_count > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo_just_broke = True
                self.combo_count = 0
                self.combo_multiplier = 1

    def _get_combo_bonus_score(self, base_score: int) -> int:
        """根据当前连击倍率计算额外奖励分数。"""
        return base_score * (self.combo_multiplier - 1)

    @property
    def combo_display_text(self) -> str:
        """连击显示文字（含倍率）。"""
        if self.combo_count < 2:
            return ""
        return f"COMBO x{self.combo_multiplier}"

    def reset_combo(self) -> None:
        """重置连击状态。"""
        self.combo_count = 0
        self.combo_timer = 0.0
        self.combo_multiplier = 1
        self.combo_peak = 0
        self.combo_just_broke = False

    def reset(self) -> None:
        self.score = 0
        self.explosion_positions.clear()
        self.floating_texts.clear()
        self.boss_defeated = False
        self.boss_death_positions.clear()
        self.drops.clear()
        self.xp_earned = 0
        self.hit_sparks.clear()
        self.combo_bonus_texts.clear()
        self.reset_combo()

    # ================================================================
    # 玩家子弹 vs 敌机
    # ================================================================

    def _handle_bullet_enemy(
        self,
        bullets_group: pygame.sprite.Group,
        enemies_group: pygame.sprite.Group,
    ) -> None:
        # ⭐ 精灵数较多时使用空间哈希加速
        n_bullets = len(bullets_group)
        n_enemies = len(enemies_group)
        use_spatial = self._spatial_enabled and (n_bullets * n_enemies > 200)

        if use_spatial:
            hits = self._spatial.get_pairs_for_group(bullets_group, enemies_group)
        else:
            # dokilla=False：穿透弹不应被销毁，由我们手动处理
            hits: dict = pygame.sprite.groupcollide(
                bullets_group, enemies_group,
                dokilla=False, dokillb=False,
            )

        for bullet, enemy_list in hits.items():
            if bullet.source != BulletSource.PLAYER:
                continue
            for enemy in enemy_list:
                if not enemy.alive():
                    continue
                # ⭐ 类型保护：确保 enemy 确实是 Enemy 实例
                if not hasattr(enemy, 'take_damage'):
                    continue
                # 穿透弹：同一敌机本帧只命中一次
                if bullet.piercing:
                    if id(enemy) in bullet._hit_enemies:
                        continue
                    bullet._hit_enemies.add(id(enemy))
                killed = enemy.take_damage(bullet.damage)
                # ⭐ 命中火花：每次命中产生，携带伤害值用于反馈
                self.hit_sparks.append({
                    "x": bullet.rect.centerx,
                    "y": bullet.rect.centery,
                    "damage": bullet.damage,
                    "killed": killed,
                })
                if killed:
                    self._on_enemy_killed(enemy)
            # 非穿透弹命中后销毁
            if not bullet.piercing and bullet.alive():
                bullet.kill()

    # ================================================================
    # 玩家 vs 敌机（含 Boss）
    # ================================================================

    def _handle_player_enemy(
        self,
        player: Player,
        enemies_group: pygame.sprite.Group,
    ) -> None:
        # ⭐ 使用 4px 判定点替代整个 rect 碰撞
        hitbox = player.hitbox
        if self._spatial_enabled and len(enemies_group) > 20:
            candidates = self._spatial.get_candidates(player, enemies_group)
        else:
            candidates = [e for e in enemies_group if e.alive() and hitbox.colliderect(e.rect)]
        for enemy in candidates:
            if not enemy.alive():
                continue

            if isinstance(enemy, BossEnemy):
                # Boss 不死亡，只对玩家造成伤害
                if not player.is_invincible:
                    player.take_damage(ENEMY_COLLISION_DAMAGE * 2)
            else:
                # 普通敌机撞毁
                enemy.kill()
                esize = _explosion_size(enemy)
                self.explosion_positions.append((enemy.rect.centerx, enemy.rect.centery, esize))
                player.take_damage(ENEMY_COLLISION_DAMAGE)

    # ================================================================
    # 玩家 vs 敌人子弹（题15新增：Boss 弹幕也能伤害玩家）
    # ================================================================

    def _handle_player_enemy_bullet(
        self,
        player: Player,
        bullets_group: pygame.sprite.Group,
    ) -> None:
        for bullet in bullets_group:
            if bullet.source != BulletSource.ENEMY:
                continue
            if not bullet.alive():
                continue
            if player.hitbox.colliderect(bullet.rect):
                bullet.kill()
                player.take_damage(bullet.damage)

    # ================================================================
    # 击毁处理
    # ================================================================

    def _on_enemy_killed(self, enemy: Enemy) -> None:
        # ⭐ 更新连击
        self.combo_count += 1
        self.combo_timer = self.combo_timeout
        # 倍率表：3连=2x, 5连=3x, 10连=4x, 20连=5x
        if self.combo_count >= 20:
            self.combo_multiplier = 5
        elif self.combo_count >= 10:
            self.combo_multiplier = 4
        elif self.combo_count >= 5:
            self.combo_multiplier = 3
        elif self.combo_count >= 3:
            self.combo_multiplier = 2
        else:
            self.combo_multiplier = 1
        self.combo_peak = max(self.combo_peak, self.combo_count)

        bonus = self._get_combo_bonus_score(enemy.score_value)
        self.score += enemy.score_value + bonus
        self.kills_this_frame += 1
        # ⭐ combo 加分飘字
        if bonus > 0:
            self.combo_bonus_texts.append((enemy.rect.centerx, enemy.rect.centery - 20, bonus))
        # ⭐ 累计经验（⭐ 随关卡缩放：高关给更多经验）
        xp_mult = max(1.0, self.current_level * 0.5)  # 第5关=2.5x, 第9关=4.5x
        if isinstance(enemy, BossEnemy):
            self.xp_earned += int(XP_BOSS * xp_mult)
        elif isinstance(enemy, EliteEnemy):
            self.xp_earned += int(XP_ELITE * xp_mult)
        elif isinstance(enemy, TrackingEnemy):
            self.xp_earned += int(XP_TRACKING * xp_mult)
        elif isinstance(enemy, FastEnemy):
            self.xp_earned += int(XP_FAST * xp_mult)
        elif isinstance(enemy, NormalEnemy):
            self.xp_earned += int(XP_NORMAL * xp_mult)
        esize = _explosion_size(enemy)
        self.explosion_positions.append((enemy.rect.centerx, enemy.rect.centery, esize))
        self.floating_texts.append(
            (enemy.rect.centerx, enemy.rect.centery, enemy.score_value)
        )
        if isinstance(enemy, BossEnemy):
            self.boss_defeated = True
            self.boss_death_positions = enemy.get_death_explosion_positions()

        # ---- 道具掉落判定（题18） ----
        self._roll_powerup_drop(enemy)

    def _roll_powerup_drop(self, enemy: Enemy) -> None:
        """根据敌机类型随机判定道具掉落。"""
        if isinstance(enemy, BossEnemy):
            # Boss 固定掉落多个
            types = list(PowerUpType)
            for _ in range(POWERUP_BOSS_DROP_COUNT):
                ptype = random.choice(types)
                self.drops.append((enemy.rect.centerx, enemy.rect.centery, ptype))
            return

        # 精英/追踪敌机掉落率更高
        if isinstance(enemy, (EliteEnemy, TrackingEnemy)):
            chance = POWERUP_ELITE_DROP_CHANCE
        else:
            chance = POWERUP_DROP_CHANCE

        if random.random() < chance:
            # 权重：火力道具更常见，炸弹稀有些
            fire_types = [
                PowerUpType.DOUBLE_DAMAGE,
                PowerUpType.TRIPLE_SPREAD,
                PowerUpType.PIERCE,
                PowerUpType.RAPID_FIRE,
            ]
            weights = [25, 25, 20, 20]  # 火力80%, 生命10%, 炸弹10%
            pool = fire_types + [PowerUpType.HEALTH, PowerUpType.BOMB]
            w = weights + [10, 10]
            ptype = random.choices(pool, weights=w, k=1)[0]
            self.drops.append((enemy.rect.centerx, enemy.rect.centery, ptype))
