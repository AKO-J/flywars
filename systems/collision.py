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
)
from sprites.bullet import BulletSource
from sprites.player import Player
from sprites.enemy import Enemy, BossEnemy, EliteEnemy, TrackingEnemy, FastEnemy, NormalEnemy


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

    # ================================================================
    # 公共入口
    # ================================================================

    def handle_all(
        self,
        bullets_group: pygame.sprite.Group,
        enemies_group: pygame.sprite.Group,
        player: Player,
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

        self._handle_bullet_enemy(bullets_group, enemies_group)
        self._handle_player_enemy(player, enemies_group)
        self._handle_player_enemy_bullet(player, bullets_group)

        game_over = player.is_dead
        return not game_over

    def reset(self) -> None:
        self.score = 0
        self.explosion_positions.clear()
        self.floating_texts.clear()
        self.boss_defeated = False
        self.boss_death_positions.clear()
        self.drops.clear()

    # ================================================================
    # 玩家子弹 vs 敌机
    # ================================================================

    def _handle_bullet_enemy(
        self,
        bullets_group: pygame.sprite.Group,
        enemies_group: pygame.sprite.Group,
    ) -> None:
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
                # 穿透弹：同一敌机本帧只命中一次
                if bullet.piercing:
                    if id(enemy) in bullet._hit_enemies:
                        continue
                    bullet._hit_enemies.add(id(enemy))
                killed = enemy.take_damage(bullet.damage)
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
        hits: list = pygame.sprite.spritecollide(
            player, enemies_group, dokill=False
        )
        for enemy in hits:
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
            if player.rect.colliderect(bullet.rect):
                bullet.kill()
                player.take_damage(bullet.damage)

    # ================================================================
    # 击毁处理
    # ================================================================

    def _on_enemy_killed(self, enemy: Enemy) -> None:
        self.score += enemy.score_value
        self.kills_this_frame += 1
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
