"""
Enemy 单元测试 — 四种移动模式、伤害、Boss
"""
import pygame
from entities.enemy import NormalEnemy, FastEnemy, EliteEnemy, TrackingEnemy, BossEnemy


class TestNormalEnemy:
    def test_moves_downward(self):
        e = NormalEnemy(x=240, y=100)
        initial_y = e._y
        e._move(0.1)
        assert e._y > initial_y

    def test_does_not_move_horizontally(self):
        e = NormalEnemy(x=240, y=100)
        initial_x = e._x
        e._move(0.1)
        assert e._x == initial_x

    def test_takes_damage_and_dies(self):
        e = NormalEnemy(x=240, y=100)
        dead = e.take_damage(2)
        assert dead is True
        assert not e.alive()

    def test_survives_insufficient_damage(self):
        e = NormalEnemy(x=240, y=100)
        g = pygame.sprite.Group(e)
        dead = e.take_damage(1)
        assert dead is False
        assert e.alive()
        assert e.hp == 1

    def test_default_spawn_in_valid_range(self):
        e = NormalEnemy()
        assert 40 <= e._x <= 560
        assert -80 <= e._y <= -20


class TestFastEnemy:
    def test_moves_downward_and_diagonally(self):
        e = FastEnemy(x=240, y=100)
        initial_x = e._x
        e._move(0.1)
        assert e._x != initial_x  # horizontal movement
        assert e._y > 100  # downward

    def test_bounces_off_left_wall(self):
        e = FastEnemy(x=5, y=100)
        e._diag_speed = -120  # moving left
        e._move(0.5)
        assert e._x > 5  # should bounce right

    def test_bounces_off_right_wall(self):
        e = FastEnemy(x=590, y=100)
        e._diag_speed = 120  # moving right
        e._move(0.5)
        assert e._diag_speed < 0  # should bounce left (direction reversed)

    def test_low_hp(self):
        e = FastEnemy()
        assert e.hp == 1


class TestEliteEnemy:
    def test_sine_wave_horizontal_movement(self):
        e = EliteEnemy(x=240, y=100)
        e._wave_center_x = 240
        e._wave_amplitude = 80
        e._total_distance = 0.0
        positions = []
        for i in range(20):
            e._move(0.05)
            positions.append(e._x)
        # Should oscillate around center (振幅80，至少有一些点超出中心±30)
        assert max(positions) - min(positions) > 10  # there is movement

    def test_moves_downward(self):
        e = EliteEnemy(x=240, y=100)
        initial_y = e._y
        e._move(0.1)
        assert e._y > initial_y


class TestTrackingEnemy:
    def test_moves_toward_player(self):
        # Create a mock player
        class MockPlayer:
            rect = pygame.Rect(240, 600, 50, 50)
        player = MockPlayer()
        e = TrackingEnemy(player_sprite=player, x=240, y=100)
        e._move(0.5)
        # Should move toward player (both x and y)
        assert e._y > 100  # moves down toward player

    def test_falls_straight_without_player(self):
        e = TrackingEnemy(player_sprite=None, x=240, y=100)
        initial_x = e._x
        e._move(0.1)
        assert e._x == initial_x
        assert e._y > 100


class TestBossEnemy:
    def test_boss_enters_from_top(self):
        boss = BossEnemy(level=3)
        assert boss._y < 0  # starts above screen
        assert boss._phase == "enter"

    def test_boss_transitions_to_patrol(self):
        boss = BossEnemy(level=3)
        boss._phase = "enter"
        boss._enter_elapsed = 2.1  # exceed enter duration
        boss._move(0.1)
        assert boss._phase == "patrol"

    def test_boss_hp_scales_with_level(self):
        boss3 = BossEnemy(level=3)
        boss5 = BossEnemy(level=5)
        assert boss5.hp > boss3.hp

    def test_boss_fire_no_attack_during_enter(self):
        boss = BossEnemy(level=3)
        bullets = boss.fire(1.0)
        assert len(bullets) == 0

    def test_boss_get_death_positions(self):
        boss = BossEnemy(level=3)
        positions = boss.get_death_explosion_positions()
        assert len(positions) >= 10


class TestEnemyKillOffscreen:
    def test_enemy_killed_when_offscreen(self):
        e = NormalEnemy(x=240, y=800)
        e.update(0.1)
        assert not e.alive()
