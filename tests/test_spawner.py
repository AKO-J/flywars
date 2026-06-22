"""飞机大战 — Spawner 单元测试（⭐ 波次制版）"""

import pytest
from systems.spawner import Spawner


@pytest.fixture
def spawner() -> Spawner:
    return Spawner()


class TestSpawnerInit:
    def test_initial_level_is_one(self, spawner: Spawner):
        assert spawner.level == 1

    def test_boss_not_active_initially(self, spawner: Spawner):
        assert not spawner.boss_active

    def test_counts_start_at_zero(self, spawner: Spawner):
        assert spawner.total_spawned == 0
        assert spawner.type_counts["normal"] == 0
        assert spawner.type_counts["fast"] == 0


class TestSpawnerLevel:
    def test_set_level_1_config(self, spawner: Spawner):
        """关卡1应有3波次、无Boss"""
        spawner.set_level(1)
        assert spawner.total_waves == 2
        assert not spawner._has_boss

    def test_set_level_3_no_boss_yet(self, spawner: Spawner):
        """关卡3为积累期，无Boss"""
        spawner.set_level(3)
        assert not spawner._has_boss
        assert spawner.total_waves == 4

    def test_set_level_5_first_boss(self, spawner: Spawner):
        """第5关为首个Boss战"""
        spawner.set_level(5)
        assert spawner._has_boss

    def test_final_level_is_9(self, spawner: Spawner):
        """第9关为最终关"""
        spawner.set_level(9)
        assert spawner._is_final
        assert spawner.total_waves == 6

    def test_set_level_resets_wave_index(self, spawner: Spawner):
        spawner.set_level(1)
        assert spawner.current_wave == 0
        spawner._wave_index = 2
        spawner.set_level(1)
        assert spawner.current_wave == 0


class TestSpawnerWave:
    def test_initial_wave_not_empty(self, spawner: Spawner):
        spawner.set_level(1)
        spawner._build_spawn_queue()
        assert len(spawner._spawn_queue) > 0
        assert all(t in ("normal", "fast") for t in spawner._spawn_queue)

    def test_wave_cleared_when_queue_empty(self, spawner: Spawner):
        spawner.set_level(1)
        spawner._build_spawn_queue()
        assert not spawner.wave_cleared
        spawner._spawn_queue.clear()
        assert spawner.wave_cleared


class TestSpawnerBoss:
    def test_level_1_no_boss_spawn(self, spawner: Spawner):
        """关卡1没有Boss"""
        spawner.set_level(1)
        assert not spawner._has_boss

    def test_level_5_boss_after_waves(self, spawner: Spawner):
        """第5关在波次完成后应能生成Boss"""
        spawner.set_level(5)
        assert spawner._has_boss
        assert not spawner._boss_spawned

    def test_on_boss_defeated_clears_flag(self, spawner: Spawner):
        spawner._boss_active = True
        spawner.on_boss_defeated()
        assert not spawner.boss_active


class TestSpawnerReset:
    def test_reset_clears_all_state(self, spawner: Spawner):
        spawner._level = 5
        spawner.total_spawned = 999
        spawner.reset()
        assert spawner.level == 1
        assert spawner.total_spawned == 0
        assert spawner.current_wave == 0
        assert not spawner._boss_spawned
