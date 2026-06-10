"""
Bullet 单元测试 — 创建、移动、越界回收
"""
import pygame
from entities.bullet import Bullet, BulletSource


class TestBulletCreation:
    def test_player_bullet_factory(self):
        b = Bullet.create_player_bullet(x=240, y=600)
        assert b.source == BulletSource.PLAYER
        assert b.direction == -1
        assert b.speed > 0
        assert b.damage > 0

    def test_enemy_bullet_factory(self):
        b = Bullet.create_enemy_bullet(x=240, y=100)
        assert b.source == BulletSource.ENEMY
        assert b.direction == 1

    def test_player_bullet_custom_damage(self):
        b = Bullet.create_player_bullet(x=240, y=600, damage=5)
        assert b.damage == 5

    def test_player_bullet_piercing(self):
        b = Bullet.create_player_bullet(x=240, y=600, piercing=True)
        assert b.piercing is True
        assert len(b._hit_enemies) == 0

    def test_default_player_bullet_not_piercing(self):
        b = Bullet.create_player_bullet(x=240, y=600)
        assert b.piercing is False


class TestBulletMovement:
    def test_player_bullet_moves_up(self):
        b = Bullet.create_player_bullet(x=240, y=600)
        initial_y = b._y
        b.update(0.1)
        assert b._y < initial_y

    def test_enemy_bullet_moves_down(self):
        b = Bullet.create_enemy_bullet(x=240, y=100)
        initial_y = b._y
        b.update(0.1)
        assert b._y > initial_y

    def test_custom_velocity_overrides_default(self):
        b = Bullet(x=240, y=300, source=BulletSource.ENEMY, direction=1)
        b._vx = 50.0
        b._vy = 100.0
        b._custom_velocity = True
        initial_x = b._x
        b.update(0.1)
        assert b._x == initial_x + 5.0  # 50 * 0.1

    def test_bullet_speed_with_dt(self):
        b = Bullet.create_player_bullet(x=240, y=600)
        speed = b.speed
        initial_y = b._y
        b.update(1.0)
        assert abs((initial_y - b._y) - speed) < 1.0


class TestBulletOffscreen:
    def test_player_bullet_dies_above_screen(self):
        b = Bullet.create_player_bullet(x=240, y=-20)
        b.update(0.1)
        assert not b.alive()

    def test_enemy_bullet_dies_below_screen(self):
        b = Bullet.create_enemy_bullet(x=240, y=720)
        b.update(0.1)
        assert not b.alive()

    def test_bullet_dies_left_of_screen(self):
        b = Bullet.create_player_bullet(x=-20, y=300)
        b.update(0.1)
        assert not b.alive()

    def test_bullet_dies_right_of_screen(self):
        b = Bullet.create_player_bullet(x=500, y=300)
        b.update(0.1)
        assert not b.alive()

    def test_bullet_alive_within_bounds(self):
        b = Bullet.create_player_bullet(x=240, y=300)
        g = pygame.sprite.Group(b)
        b.update(0.01)
        assert b.alive()
        b.kill()


class TestPiercingBullet:
    def test_piercing_remembers_hit_enemies(self):
        b = Bullet.create_player_bullet(x=240, y=600, piercing=True)
        enemy_id = id(object())
        b._hit_enemies.add(enemy_id)
        assert enemy_id in b._hit_enemies
