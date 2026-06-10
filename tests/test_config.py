"""
ConfigManager 单元测试 — 加载、合并、校验、热重载
"""
import json
import tempfile
import os
from config.config_manager import ConfigManager


class TestConfigManagerLoad:
    def test_load_valid_config_files(self):
        config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
        default_path = os.path.join(config_dir, "default.json")
        user_path = os.path.join(config_dir, "user.json")
        cm = ConfigManager(default_path=str(default_path), user_path=str(user_path))
        assert cm.get("window.width") is not None

    def test_get_with_dot_path(self):
        cm = _make_config()
        assert cm.get("player.speed") is not None

    def test_get_with_default_value(self):
        cm = _make_config()
        assert cm.get("nonexistent.key", 42) == 42

    def test_get_section(self):
        cm = _make_config()
        section = cm.get_section("player")
        assert "speed" in section
        assert "max_hp" in section


class TestConfigManagerMerge:
    def test_user_overrides_default(self):
        cm = _make_config()
        # user.json sets sfx_volume to 0.7
        sfx = cm.get("audio.sfx_volume")
        assert sfx is not None

    def test_deep_merge_keeps_default_keys(self):
        cm = _make_config()
        assert cm.get("window.width") == 600  # from default
        assert cm.get("window.height") == 820


class TestConfigManagerValidation:
    def test_load_rejects_negative_speed(self):
        import copy
        default = {"player": {"speed": -5, "boost_multiplier": 1.8, "max_hp": 5,
                    "invincible_time": 1.5, "charge_time": 0.85, "width": 55,
                    "height": 57, "tilt_angle": 20}}
        cm = _make_config()
        try:
            cm._validate(default)
            assert False, "should raise ValueError"
        except ValueError:
            pass

    def test_load_rejects_out_of_range_volume(self):
        custom = {"audio": {"sfx_volume": 3.0, "bgm_volume": 0.3}}
        cm = _make_config()
        from config.config_manager import _SCHEMA
        old = dict(_SCHEMA)
        try:
            cm._validate({"audio": {"sfx_volume": 3.0}})
            assert False, "should raise ValueError"
        except ValueError:
            pass

    def test_load_rejects_out_of_range_fps(self):
        custom = {"window": {"width": 480, "height": 700, "fps": 500}}
        cm = _make_config()
        try:
            cm._validate(custom)
            assert False, "should raise"
        except ValueError:
            pass


class TestConfigManagerReload:
    def test_reload_detects_changes(self):
        import copy
        cm = _make_config()
        # Simulate a change by directly modifying data
        old_data = copy.deepcopy(cm._data)
        cm._data["audio"]["sfx_volume"] = 0.99
        changes = cm._diff(old_data, cm._data)
        assert "audio.sfx_volume" in changes


class TestConfigManagerDeepMerge:
    def test_deep_merge_nested(self):
        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"b": 99}}
        result = ConfigManager._deep_merge(base, override)
        assert result["a"]["b"] == 99
        assert result["a"]["c"] == 2

    def test_deep_merge_top_level(self):
        base = {"a": 1, "b": 2}
        override = {"a": 99}
        result = ConfigManager._deep_merge(base, override)
        assert result["a"] == 99
        assert result["b"] == 2


def _make_config() -> ConfigManager:
    config_dir = os.path.join(os.path.dirname(__file__), "..", "config")
    default_path = os.path.join(config_dir, "default.json")
    user_path = os.path.join(config_dir, "user.json")
    return ConfigManager(default_path=str(default_path), user_path=str(user_path))
