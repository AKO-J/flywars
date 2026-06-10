"""
CollisionSystem 单元测试 — 碰撞检测三步骤
"""
import pygame
from entities.player import Player
from entities.bullet import Bullet
from entities.enemy import NormalEnemy
from systems.collision import CollisionSystem


class TestCollisionBulletEnemy:
    def test_bullet_hits_enemy(self):
        cs = CollisionSystem()
        player = Player()
        bullet = Bullet.create_player_bullet(x=240, y=200, damage=3)
        enemy = NormalEnemy(x=240, y=200)
        # Position enemy's rect to overlap bullet
        enemy.rect.centerx = 240
        enemy.rect.centery = 200
        bullet.rect.centerx = 240
        bullet.rect.centery = 200
        bullets = pygame.sprite.Group(bullet)
        enemies = pygame.sprite.Group(enemy)

        initial_score = cs.score
        cs._handle_bullet_enemy(bullets, enemies)
        assert cs.score > initial_score or not enemy.alive()

    def test_bullet_kills_enemy(self):
        cs = CollisionSystem()
        bullet = Bullet.create_player_bullet(x=240, y=200, damage=10)
        enemy = NormalEnemy(x=240, y=200)
        bullets = pygame.sprite.Group(bullet)
        enemies = pygame.sprite.Group(enemy)

        cs._handle_bullet_enemy(bullets, enemies)
        assert not enemy.alive()

    def test_enemy_bullet_ignored(self):
        cs = CollisionSystem()
        bullet = Bullet.create_enemy_bullet(x=240, y=200)
        enemy = NormalEnemy(x=240, y=200)
        bullets = pygame.sprite.Group(bullet)
        enemies = pygame.sprite.Group(enemy)

        initial_score = cs.score
        cs._handle_bullet_enemy(bullets, enemies)
        assert cs.score == initial_score

    def test_no_collision_when_separated(self):
        cs = CollisionSystem()
        bullet = Bullet.create_player_bullet(x=240, y=0)
        enemy = NormalEnemy(x=240, y=400)
        bullets = pygame.sprite.Group(bullet)
        enemies = pygame.sprite.Group(enemy)

        initial_score = cs.score
        cs._handle_bullet_enemy(bullets, enemies)
        assert cs.score == initial_score

    def test_piercing_bullet_not_destroyed(self):
        cs = CollisionSystem()
        bullet = Bullet.create_player_bullet(x=240, y=200, piercing=True, damage=10)
        enemy = NormalEnemy(x=240, y=200)
        bullets = pygame.sprite.Group(bullet)
        enemies = pygame.sprite.Group(enemy)

        cs._handle_bullet_enemy(bullets, enemies)
        assert bullet.alive()
        assert not enemy.alive()


class TestCollisionPlayerEnemy:
    def test_player_collides_enemy_takes_damage(self):
        cs = CollisionSystem()
        player = Player()
        enemy = NormalEnemy(x=player.rect.centerx, y=player.rect.centery)
        enemies = pygame.sprite.Group(enemy)

        initial_hp = player.hp
        cs._handle_player_enemy(player, enemies)
        assert player.hp < initial_hp

    def test_enemy_destroyed_on_player_collision(self):
        cs = CollisionSystem()
        player = Player()
        enemy = NormalEnemy(x=player.rect.centerx, y=player.rect.centery)
        enemies = pygame.sprite.Group(enemy)

        cs._handle_player_enemy(player, enemies)
        assert not enemy.alive()

    def test_invincible_player_not_damaged_by_enemy(self):
        cs = CollisionSystem()
        player = Player()
        # Simulate being already invincible
        player._invincible_timer = 1.0
        enemy = NormalEnemy(x=player.rect.centerx, y=player.rect.centery)
        enemies = pygame.sprite.Group(enemy)

        initial_hp = player.hp
        cs._handle_player_enemy(player, enemies)
        assert player.hp == initial_hp


class TestCollisionPlayerEnemyBullet:
    def test_enemy_bullet_hits_player(self):
        cs = CollisionSystem()
        player = Player()
        bullet = Bullet.create_enemy_bullet(
            x=player.rect.centerx, y=player.rect.centery
        )
        bullets = pygame.sprite.Group(bullet)

        initial_hp = player.hp
        cs._handle_player_enemy_bullet(player, bullets)
        assert player.hp < initial_hp

    def test_player_bullet_ignored_for_player_damage(self):
        cs = CollisionSystem()
        player = Player()
        bullet = Bullet.create_player_bullet(
            x=player.rect.centerx, y=player.rect.centery
        )
        bullets = pygame.sprite.Group(bullet)

        initial_hp = player.hp
        cs._handle_player_enemy_bullet(player, bullets)
        assert player.hp == initial_hp


class TestCollisionSystemReset:
    def test_reset_clears_score(self):
        cs = CollisionSystem()
        cs.score = 500
        cs.reset()
        assert cs.score == 0

    def test_handle_all_returns_alive_status(self):
        cs = CollisionSystem()
        player = Player()
        bullets = pygame.sprite.Group()
        enemies = pygame.sprite.Group()
        alive = cs.handle_all(bullets, enemies, player)
        assert alive is True

    def test_handle_all_clears_positions_each_frame(self):
        cs = CollisionSystem()
        cs.explosion_positions.append((100, 100, "normal"))
        cs.handle_all(pygame.sprite.Group(), pygame.sprite.Group(), Player())
        assert len(cs.explosion_positions) == 0
