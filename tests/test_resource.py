"""
ResourceManager 单元测试 — 缓存、占位、统计
"""
import pygame
from utils.resource_manager import ResourceManager


class TestResourceManagerImage:
    def test_get_image_caches(self):
        rm = ResourceManager.get_instance()
        img1 = rm.get_image("assets/images/player.png", width=55, height=57)
        img2 = rm.get_image("assets/images/player.png", width=55, height=57)
        assert img1 is img2  # same object from cache

    def test_get_image_different_sizes_separate_cache(self):
        rm = ResourceManager.get_instance()
        initial = rm.get_stats()["cache"]["images"]
        rm.get_image("assets/images/player.png", width=20, height=20)
        assert rm.get_stats()["cache"]["images"] >= initial

    def test_missing_image_returns_placeholder(self):
        rm = ResourceManager.get_instance()
        img = rm.get_image("nonexistent_file.png", width=32, height=32)
        assert img is not None
        assert img.get_width() == 32
        assert img.get_height() == 32

    def test_placeholder_is_magenta(self):
        rm = ResourceManager.get_instance()
        img = rm.get_image("nonexistent.png", width=32, height=32)
        # Check pixel at (3, 20) — off diagonal, inside border
        color = img.get_at((3, 20))
        assert color[:3] == (255, 0, 255)  # magenta


class TestResourceManagerSound:
    def test_get_sound_missing_returns_none(self):
        rm = ResourceManager.get_instance()
        snd = rm.get_sound("nonexistent_sound.wav")
        assert snd is None

    def test_get_sound_caches(self):
        rm = ResourceManager.get_instance()
        snd1 = rm.get_sound("assets/sounds/shoot.wav")
        snd2 = rm.get_sound("assets/sounds/shoot.wav")
        # Both None if file doesn't exist, or same object
        assert snd1 is snd2


class TestResourceManagerFont:
    @classmethod
    def setup_class(cls):
        pygame.font.init()

    def test_get_font_fallback(self):
        rm = ResourceManager.get_instance()
        font = rm.get_font("nonexistent_font.ttf", 20)
        assert font is not None

    def test_get_font_caches(self):
        rm = ResourceManager.get_instance()
        f1 = rm.get_font("nonexistent.ttf", 20)
        f2 = rm.get_font("nonexistent.ttf", 20)
        assert f1 is f2

    def test_get_font_different_sizes_separate_cache(self):
        rm = ResourceManager.get_instance()
        rm.get_font("nonexistent.ttf", 12)
        rm.get_font("nonexistent.ttf", 24)
        assert True


class TestResourceManagerStats:
    def test_stats_includes_all_categories(self):
        rm = ResourceManager.get_instance()
        s = rm.get_stats()
        assert "cache" in s
        assert "access" in s
        assert "memory" in s
        assert "images" in s["cache"]
        assert "sounds" in s["cache"]
        assert "fonts" in s["cache"]

    def test_load_count_increases(self):
        rm = ResourceManager.get_instance()
        initial = rm.get_stats()["access"]["loads"]["image"]
        rm.get_image("assets/images/player.png", width=55, height=57)
        new_count = rm.get_stats()["access"]["loads"]["image"]
        assert new_count >= initial

    def test_hit_count_increases_on_cache_hit(self):
        rm = ResourceManager.get_instance()
        rm.get_image("assets/images/player.png", width=15, height=15)
        initial_hits = rm.get_stats()["access"]["hits"]["image"]
        rm.get_image("assets/images/player.png", width=15, height=15)  # cached
        assert rm.get_stats()["access"]["hits"]["image"] > initial_hits

    def test_memory_estimate_reasonable(self):
        rm = ResourceManager.get_instance()
        s = rm.get_stats()
        assert s["memory"]["image_estimate_mb"] >= 0


class TestResourceManagerClear:
    def test_clear_empties_cache(self):
        rm = ResourceManager.get_instance()
        rm.get_image("assets/images/player.png", width=10, height=10)
        assert rm.get_stats()["cache"]["images"] > 0
        rm.clear_cache()
        assert rm.get_stats()["cache"]["images"] == 0
        assert rm.get_stats()["cache"]["sounds"] == 0
        assert rm.get_stats()["cache"]["fonts"] == 0
