"""
Player 单元测试 — 移动、蓄力、射击、受伤、道具
"""
import pygame
from entities.player import Player


class TestPlayerInit:
    def test_player_initial_position(self):
        p = Player()
        assert p.rect.centerx == 300
        assert p.rect.bottom == 790

    def test_player_initial_hp(self):
        p = Player()
        assert p.hp == 8
        assert p.max_hp == 8

    def test_player_not_dead_initially(self):
        p = Player()
        assert p.is_dead is False
        assert p.is_invincible is False

    def test_player_charge_starts_empty(self):
        p = Player()
        assert p.charge_level == 0.0
        assert p.charge_name == "单发"

    def test_player_no_active_powerups_initially(self):
        p = Player()
        assert len(p.active_powerups) == 0
        assert p.powerup_timer == 0.0

    def test_player_has_three_images(self):
        p = Player()
        assert p._image_straight is not None
        assert p._image_left is not None
        assert p._image_right is not None


class TestPlayerMovement:
    def test_clamp_left_boundary(self):
        p = Player()
        p.rect.left = -10
        p._clamp_to_screen()
        assert p.rect.left == 0

    def test_clamp_right_boundary(self):
        p = Player()
        p.rect.right = 610
        p._clamp_to_screen()
        assert p.rect.right == 600

    def test_clamp_top_boundary(self):
        p = Player()
        p.rect.top = -5
        p._clamp_to_screen()
        assert p.rect.top == 0

    def test_clamp_bottom_boundary(self):
        p = Player()
        p.rect.bottom = 830
        p._clamp_to_screen()
        assert p.rect.bottom == 820

    def test_clamp_all_within_bounds(self):
        p = Player()
        p.rect.topleft = (100, 100)
        p._clamp_to_screen()
        assert p.rect.topleft == (100, 100)

    def test_orientation_straight_when_idle(self):
        p = Player()
        p._update_orientation(False, False)
        assert p.image == p._image_straight

    def test_orientation_left(self):
        p = Player()
        p._update_orientation(True, False)
        assert p.image == p._image_left

    def test_orientation_right(self):
        p = Player()
        p._update_orientation(False, True)
        assert p.image == p._image_right

    def test_orientation_straight_when_both_directions(self):
        p = Player()
        p._update_orientation(True, True)
        assert p.image == p._image_straight


class TestPlayerCharge:
    def test_charge_increases_over_time(self):
        p = Player()
        assert p.charge_level == 0.0
        p._update_charge(0.3)
        assert p.charge_level > 0.0
        assert p.charge_level < 1.0

    def test_charge_caps_at_one(self):
        p = Player()
        p._update_charge(5.0)
        assert p.charge_level == 1.0

    def test_charge_name_levels(self):
        p = Player()
        assert p.charge_name == "单发"
        p._update_charge(0.4)  # reaches 40% threshold
        p._update_charge(0.1)
        assert p.charge_name == "双发"
        # Fill to 80%
        while p.charge_level < 0.8:
            p._update_charge(0.01)
        assert p.charge_name == "三发"


class TestPlayerFire:
    def test_fire_resets_charge_to_zero(self):
        p = Player()
        p._update_charge(1.0)
        assert p.charge_level > 0.5
        p.fire()
        assert p.charge_level == 0.0

    def test_fire_returns_list_of_bullets(self):
        p = Player()
        p._update_charge(1.0)
        bullets = p.fire()
        assert len(bullets) >= 1
        for b in bullets:
            from entities.bullet import Bullet, BulletSource
            assert isinstance(b, Bullet)
            assert b.source == BulletSource.PLAYER

    def test_fire_single_at_low_charge(self):
        p = Player()
        p._update_charge(0.1)
        bullets = p.fire()
        assert len(bullets) == 1

    def test_fire_double_at_medium_charge(self):
        p = Player()
        while p.charge_level < 0.6:
            p._update_charge(0.05)
        bullets = p.fire()
        assert len(bullets) == 2

    def test_fire_triple_at_high_charge(self):
        p = Player()
        p._update_charge(1.0)
        bullets = p.fire()
        assert len(bullets) == 3


class TestPlayerDamage:
    def test_take_damage_reduces_hp(self):
        p = Player()
        dead = p.take_damage(1)
        assert p.hp == 7  # 8 - 1
        assert dead is False

    def test_take_damage_triggers_invincibility(self):
        p = Player()
        p.take_damage(1)
        assert p.is_invincible is True

    def test_invincible_blocks_damage(self):
        p = Player()
        p.take_damage(1)  # hp 8→7, enters invincible
        hp_after = p.hp
        p.take_damage(1)  # should be ignored
        assert p.hp == hp_after

    def test_invincibility_expires(self):
        p = Player()
        p.take_damage(1)
        p._invincible_timer = 0.0
        p._update_invincible(0.001)
        assert p.is_invincible is False

    def test_fatal_damage_kills(self):
        p = Player()
        dead = p.take_damage(8)  # 一次扣光所有 HP
        assert p.hp == 0
        assert p.is_dead is True
        assert dead is True


class TestPlayerPowerup:
    def test_health_powerup_restores_hp(self):
        p = Player()
        p.take_damage(2)
        result = p.apply_powerup(pygame.K_F1)  # placeholder
        # Use actual PowerUpType
        from settings import PowerUpType
        result = p.apply_powerup(PowerUpType.HEALTH)
        assert result == "health"
        assert p.hp == 7  # 8 - 2 + 1

    def test_health_powerup_not_exceed_max(self):
        p = Player()
        from settings import PowerUpType
        result = p.apply_powerup(PowerUpType.HEALTH)
        assert result == "health"
        assert p.hp == p.max_hp

    def test_bomb_powerup_returns_bomb(self):
        p = Player()
        from settings import PowerUpType
        result = p.apply_powerup(PowerUpType.BOMB)
        assert result == "bomb"

    def test_buff_powerup_adds_to_active(self):
        p = Player()
        from settings import PowerUpType
        result = p.apply_powerup(PowerUpType.DOUBLE_DAMAGE)
        assert result == "buff"
        assert PowerUpType.DOUBLE_DAMAGE in p.active_powerups

    def test_buff_powerup_expires(self):
        p = Player()
        from settings import PowerUpType, POWERUP_DURATION
        p.apply_powerup(PowerUpType.DOUBLE_DAMAGE)
        # Simulate time passing
        p._active_powerups[PowerUpType.DOUBLE_DAMAGE] = 0.0
        p._update_powerup(0.1)
        assert PowerUpType.DOUBLE_DAMAGE not in p.active_powerups

    def test_multiple_buffs_stack(self):
        p = Player()
        from settings import PowerUpType
        p.apply_powerup(PowerUpType.DOUBLE_DAMAGE)
        p.apply_powerup(PowerUpType.PIERCE)
        assert len(p.active_powerups) == 2
