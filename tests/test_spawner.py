"""
Spawner 单元测试 — 生成计时器、关卡缩放、Boss 触发
"""
import pygame
from entities.player import Player
from systems.spawner import Spawner


class TestSpawnerInit:
    def test_initial_level_is_one(self):
        s = Spawner()
        assert s.level == 1

    def test_boss_not_active_initially(self):
        s = Spawner()
        assert s.boss_active is False

    def test_counts_start_at_zero(self):
        s = Spawner()
        assert s.total_spawned == 0
        assert all(v == 0 for v in s.type_counts.values())


class TestSpawnerLevel:
    def test_set_level_updates_intervals(self):
        s = Spawner()
        old_interval = s._intervals["normal"]
        s.set_level(5)
        assert s._intervals["normal"] < old_interval  # harder = faster spawn

    def test_set_level_no_op_for_same_level(self):
        s = Spawner()
        old_intervals = dict(s._intervals)
        s.set_level(1)
        assert s._intervals == old_intervals

    def test_interval_not_below_minimum(self):
        s = Spawner()
        s.set_level(100)  # extreme level
        for interval in s._intervals.values():
            assert interval >= 0.15  # SPAWN_INTERVAL_MIN


class TestSpawnerBoss:
    def test_should_spawn_boss_at_level_3(self):
        s = Spawner()
        s.set_level(3)
        assert s._should_spawn_boss() is True

    def test_no_boss_below_level_3(self):
        s = Spawner()
        s.set_level(2)
        assert s._should_spawn_boss() is False

    def test_no_boss_when_boss_active(self):
        s = Spawner()
        s.set_level(3)
        s._boss_active = True
        assert s._should_spawn_boss() is False

    def test_on_boss_defeated_clears_flag(self):
        s = Spawner()
        s._boss_active = True
        s.on_boss_defeated()
        assert s.boss_active is False

    def test_boss_spawns_at_level_6(self):
        s = Spawner()
        s.set_level(6)
        assert s._should_spawn_boss() is True


class TestSpawnerReset:
    def test_reset_clears_all_state(self):
        s = Spawner()
        s.set_level(5)
        s._boss_active = True
        s.total_spawned = 50
        s.type_counts["normal"] = 30
        s.reset()
        assert s.level == 1
        assert s.boss_active is False
        assert s.total_spawned == 0
        assert s.type_counts["normal"] == 0


class TestSpawnerTimers:
    def test_timer_accumulates(self):
        s = Spawner()
        initial = s._timers["normal"]
        group = pygame.sprite.Group()
        all_s = pygame.sprite.Group()
        s.set_player(Player())
        s.update(0.5, group, all_s)
        assert s._timers["normal"] > initial or s.total_spawned > 0

    def test_no_spawn_before_interval(self):
        s = Spawner()
        s.set_player(Player())
        group = pygame.sprite.Group()
        all_s = pygame.sprite.Group()
        s.update(0.01, group, all_s)  # very short time
        assert s.total_spawned == 0


class TestSpawnerScaleEnemy:
    def test_scale_modifies_speed_and_hp(self):
        from entities.enemy import NormalEnemy
        s = Spawner()
        e = NormalEnemy()
        original_speed = e.speed
        original_hp = e.hp
        s._scale_enemy(e, 2.0, 3.0)
        assert e.speed == original_speed * 2.0
        assert e.hp == int(original_hp * 3.0)
