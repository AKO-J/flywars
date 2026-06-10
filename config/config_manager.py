"""
==============================================================================
飞机大战 — 配置管理器
==============================================================================
功能：
  1. 加载 default.json + user.json（深度合并，user 覆盖 default）
  2. 格式校验（必需键 + 值类型 + 值域检查）
  3. F5 热重载：重新读取文件，diff 变更键，通知 Game 应用
  4. 同步 settings 模块级变量，兼容现有 from settings import X 代码
==============================================================================
"""
from __future__ import annotations

import json
import copy
from pathlib import Path
from typing import Any


# ==========================================================================
# 配置 Schema（校验用）
# ==========================================================================

_SCHEMA: dict[str, dict[str, type | tuple]] = {
    "window": {"width": int, "height": int, "fps": int},
    "player": {"speed": (int, float), "boost_multiplier": float, "max_hp": int,
               "invincible_time": float, "charge_time": float},
    "bullet": {"player_speed": (int, float), "player_damage": int,
               "enemy_speed": (int, float), "enemy_damage": int,
               "charge_threshold_double": float, "charge_threshold_triple": float},
    "enemy": {},
    "boss": {"hp": int, "speed": (int, float), "score": int, "spawn_level": int,
             "final_level": int},
    "difficulty": {"spawn_interval_scale": float, "speed_scale": float,
                   "hp_scale": float, "spawn_interval_min": float},
    "background": {"base_speed": (int, float)},
    "audio": {"sfx_volume": float, "bgm_volume": float},
    "powerup": {"drop_chance": float, "elite_drop_chance": float,
                "boss_drop_count": int, "duration": float},
    "ui": {"level_score_base": int, "level_up_display_time": float},
    "network": {"server_host": str, "server_port": int,
                "reconnect_base_delay": float, "reconnect_max_delay": float,
                "heartbeat_interval": float, "heartbeat_timeout": float},
}

# 热加载可即时生效的键（无需重启的配置路径）
_HOT_RELOADABLE: set[str] = {
    "player.speed", "player.boost_multiplier", "player.max_hp",
    "player.invincible_time", "player.charge_time",
    "bullet.player_speed", "bullet.player_damage",
    "bullet.enemy_speed", "bullet.enemy_damage",
    "bullet.charge_threshold_double", "bullet.charge_threshold_triple",
    "bullet.double_shot_spacing",
    "enemy.normal.spawn_interval", "enemy.fast.spawn_interval",
    "enemy.elite.spawn_interval", "enemy.tracking.spawn_interval",
    "enemy.normal.speed", "enemy.fast.speed", "enemy.elite.speed",
    "enemy.tracking.speed",
    "enemy.normal.hp", "enemy.fast.hp", "enemy.elite.hp", "enemy.tracking.hp",
    "difficulty.spawn_interval_scale", "difficulty.speed_scale",
    "difficulty.hp_scale", "difficulty.spawn_interval_min",
    "background.base_speed",
    "audio.sfx_volume", "audio.bgm_volume",
    "powerup.drop_chance", "powerup.elite_drop_chance",
    "powerup.boss_drop_count", "powerup.duration",
    "boss.bullet_speed", "boss.bullet_damage",
    "boss.fire_interval_circle", "boss.fire_interval_aimed",
    "boss.fire_interval_spiral", "boss.fan_count", "boss.fan_angle",
    "boss.fan_interval",
    "ui.floating_text_speed", "ui.floating_text_lifetime",
    "ui.level_score_base", "ui.level_up_display_time",
    "network.server_host", "network.server_port",
    "network.reconnect_base_delay", "network.reconnect_max_delay",
    "network.heartbeat_interval", "network.heartbeat_timeout",
}


class ConfigManager:
    """JSON 配置管理器 — 启动时加载，F5 热重载。"""

    def __init__(self, default_path: str = "config/default.json",
                 user_path: str = "config/user.json") -> None:
        self._default_path: Path = Path(default_path)
        self._user_path: Path = Path(user_path)
        self._data: dict[str, Any] = {}
        self._base_dir: Path = Path(__file__).resolve().parent.parent
        self.load()

    # ==================================================================
    # 加载与合并
    # ==================================================================

    def load(self) -> dict[str, Any]:
        """加载两个 JSON 文件，深度合并（user 覆盖 default），校验后存入 _data。"""
        default = self._read_json(self._base_dir / self._default_path)
        user = self._read_json(self._base_dir / self._user_path)

        merged = self._deep_merge(copy.deepcopy(default), user)
        self._validate(merged)
        self._data = merged
        self._sync_to_settings()
        return self._data

    def _read_json(self, path: Path) -> dict[str, Any]:
        """读取 JSON 文件，文件缺失或损坏时返回空字典。"""
        if not path.exists():
            print(f"[Config] 文件不存在: {path.name}，使用空配置")
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                print(f"[Config] {path.name} 格式错误（非 JSON 对象），使用空配置")
                return {}
            return data
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Config] 读取 {path.name} 失败: {e}，使用空配置")
            return {}

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """深度合并两个字典 — override 的值覆盖 base。"""
        for key, value in override.items():
            if key.startswith("_"):
                continue  # 跳过注释键
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigManager._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

    # ==================================================================
    # 校验
    # ==================================================================

    def _validate(self, data: dict[str, Any]) -> None:
        """校验配置格式：必需键 + 值类型 + 值域。"""
        errors: list[str] = []

        for section, fields in _SCHEMA.items():
            if section not in data:
                errors.append(f"缺失配置节: {section}")
                continue
            section_data = data[section]
            for key, expected_type in fields.items():
                if key not in section_data:
                    errors.append(f"{section}.{key} 缺失")
                    continue
                value = section_data[key]
                if not isinstance(value, expected_type):
                    errors.append(
                        f"{section}.{key} 类型错误: 期望 {expected_type}, "
                        f"实际 {type(value).__name__} (值={value})"
                    )

        # 值域检查
        self._check_range(data, "player.speed", 1, 20, errors)
        self._check_range(data, "player.max_hp", 1, 100, errors)
        self._check_range(data, "player.charge_time", 0.1, 5.0, errors)
        self._check_range(data, "bullet.player_speed", 50, 2000, errors)
        self._check_range(data, "bullet.enemy_speed", 50, 2000, errors)
        self._check_range(data, "window.width", 320, 3840, errors)
        self._check_range(data, "window.height", 240, 2160, errors)
        self._check_range(data, "window.fps", 10, 240, errors)
        self._check_range(data, "audio.sfx_volume", 0.0, 1.0, errors)
        self._check_range(data, "audio.bgm_volume", 0.0, 1.0, errors)
        self._check_range(data, "powerup.drop_chance", 0.0, 1.0, errors)
        self._check_range(data, "powerup.elite_drop_chance", 0.0, 1.0, errors)
        self._check_range(data, "difficulty.spawn_interval_scale", 0.1, 1.0, errors)
        self._check_range(data, "difficulty.speed_scale", 0.5, 3.0, errors)
        self._check_range(data, "difficulty.hp_scale", 0.5, 5.0, errors)

        if errors:
            msg = "\n".join(f"  - {e}" for e in errors)
            raise ValueError(f"配置校验失败:\n{msg}")

    @staticmethod
    def _check_range(data: dict, key_path: str, lo: float, hi: float,
                     errors: list[str]) -> None:
        val = ConfigManager._nested_get(data, key_path)
        if val is not None and not (lo <= val <= hi):
            errors.append(f"{key_path} 值域错误: {val} 不在 [{lo}, {hi}]")

    # ==================================================================
    # 热重载
    # ==================================================================

    def reload(self) -> dict[str, Any]:
        """重新读取 JSON，返回变更的键值对。"""
        old = copy.deepcopy(self._data)
        try:
            self.load()
        except (ValueError, OSError) as e:
            print(f"[Config] 热重载失败，回退到旧配置: {e}")
            self._data = old
            self._sync_to_settings()
            return {}
        return self._diff(old, self._data)

    @staticmethod
    def _diff(old: dict, new: dict) -> dict[str, Any]:
        """计算两个配置树的差异，返回变更路径→新值的映射。"""
        changes: dict[str, Any] = {}

        def _recurse(o: Any, n: Any, prefix: str) -> None:
            if isinstance(o, dict) and isinstance(n, dict):
                for k in n:
                    _recurse(o.get(k), n[k], f"{prefix}.{k}" if prefix else k)
            elif o != n:
                changes[prefix] = n

        _recurse(old, new, "")
        # 仅返回热加载可生效的键
        return {k: v for k, v in changes.items() if k in _HOT_RELOADABLE}

    # ==================================================================
    # 公共访问器
    # ==================================================================

    def get(self, key_path: str, default: Any = None) -> Any:
        """用点号分隔路径获取配置值，如 config.get("player.speed")。"""
        return self._nested_get(self._data, key_path) or default

    def get_section(self, section: str) -> dict[str, Any]:
        """获取整个配置节。"""
        return self._data.get(section, {})

    @property
    def data(self) -> dict[str, Any]:
        """只读访问完整配置数据。"""
        return copy.deepcopy(self._data)

    @staticmethod
    def _nested_get(data: dict, key_path: str) -> Any:
        keys = key_path.split(".")
        current: Any = data
        for k in keys:
            if isinstance(current, dict):
                current = current.get(k)
            else:
                return None
        return current

    # ==================================================================
    # 同步到 settings 模块（兼容现有 from settings import X 代码）
    # ==================================================================

    def _sync_to_settings(self) -> None:
        """将配置值写入 settings 模块变量，兼容现有代码。"""
        try:
            import settings as _s

            d = self._data

            # 窗口
            _s.SCREEN_WIDTH = d["window"]["width"]
            _s.SCREEN_HEIGHT = d["window"]["height"]
            _s.GAME_TITLE = d["window"]["title"]
            _s.FPS = d["window"]["fps"]

            # 玩家
            _s.PLAYER_SPEED = d["player"]["speed"]
            _s.PLAYER_BOOST_MULTIPLIER = d["player"]["boost_multiplier"]
            _s.PLAYER_MAX_HP = d["player"]["max_hp"]
            _s.PLAYER_INVINCIBLE_TIME = d["player"]["invincible_time"]
            _s.PLAYER_CHARGE_TIME = d["player"]["charge_time"]
            _s.PLAYER_WIDTH = d["player"]["width"]
            _s.PLAYER_HEIGHT = d["player"]["height"]
            _s.PLAYER_TILT_ANGLE = d["player"]["tilt_angle"]

            # 子弹
            _s.PLAYER_BULLET_SPEED = d["bullet"]["player_speed"]
            _s.PLAYER_BULLET_DAMAGE = d["bullet"]["player_damage"]
            _s.PLAYER_BULLET_WIDTH = d["bullet"]["player_width"]
            _s.PLAYER_BULLET_HEIGHT = d["bullet"]["player_height"]
            _s.ENEMY_BULLET_SPEED = d["bullet"]["enemy_speed"]
            _s.ENEMY_BULLET_DAMAGE = d["bullet"]["enemy_damage"]
            _s.ENEMY_BULLET_WIDTH = d["bullet"]["enemy_width"]
            _s.ENEMY_BULLET_HEIGHT = d["bullet"]["enemy_height"]
            _s.CHARGE_THRESHOLD_DOUBLE = d["bullet"]["charge_threshold_double"]
            _s.CHARGE_THRESHOLD_TRIPLE = d["bullet"]["charge_threshold_triple"]
            _s.DOUBLE_SHOT_SPACING = d["bullet"]["double_shot_spacing"]

            # 敌机 — Normal
            _s.ENEMY_NORMAL_SPEED = d["enemy"]["normal"]["speed"]
            _s.ENEMY_NORMAL_HP = d["enemy"]["normal"]["hp"]
            _s.ENEMY_NORMAL_SCORE = d["enemy"]["normal"]["score"]
            _s.ENEMY_NORMAL_WIDTH = d["enemy"]["normal"]["width"]
            _s.ENEMY_NORMAL_HEIGHT = d["enemy"]["normal"]["height"]
            _s.ENEMY_NORMAL_SPAWN_INTERVAL = d["enemy"]["normal"]["spawn_interval"]

            # 敌机 — Fast
            _s.ENEMY_FAST_SPEED = d["enemy"]["fast"]["speed"]
            _s.ENEMY_FAST_HP = d["enemy"]["fast"]["hp"]
            _s.ENEMY_FAST_SCORE = d["enemy"]["fast"]["score"]
            _s.ENEMY_FAST_WIDTH = d["enemy"]["fast"]["width"]
            _s.ENEMY_FAST_HEIGHT = d["enemy"]["fast"]["height"]
            _s.ENEMY_FAST_SPAWN_INTERVAL = d["enemy"]["fast"]["spawn_interval"]
            _s.ENEMY_FAST_DIAGONAL_SPEED = d["enemy"]["fast"]["diagonal_speed"]

            # 敌机 — Elite
            _s.ENEMY_ELITE_SPEED = d["enemy"]["elite"]["speed"]
            _s.ENEMY_ELITE_HP = d["enemy"]["elite"]["hp"]
            _s.ENEMY_ELITE_SCORE = d["enemy"]["elite"]["score"]
            _s.ENEMY_ELITE_WIDTH = d["enemy"]["elite"]["width"]
            _s.ENEMY_ELITE_HEIGHT = d["enemy"]["elite"]["height"]
            _s.ENEMY_ELITE_SPAWN_INTERVAL = d["enemy"]["elite"]["spawn_interval"]
            _s.ENEMY_ELITE_WAVE_AMPLITUDE = d["enemy"]["elite"]["wave_amplitude"]
            _s.ENEMY_ELITE_WAVE_FREQUENCY = d["enemy"]["elite"]["wave_frequency"]

            # 敌机 — Tracking
            _s.ENEMY_TRACKING_SPEED = d["enemy"]["tracking"]["speed"]
            _s.ENEMY_TRACKING_HP = d["enemy"]["tracking"]["hp"]
            _s.ENEMY_TRACKING_SCORE = d["enemy"]["tracking"]["score"]
            _s.ENEMY_TRACKING_WIDTH = d["enemy"]["tracking"]["width"]
            _s.ENEMY_TRACKING_HEIGHT = d["enemy"]["tracking"]["height"]
            _s.ENEMY_TRACKING_SPAWN_INTERVAL = d["enemy"]["tracking"]["spawn_interval"]

            # Boss
            _s.BOSS_SPAWN_LEVEL = d["boss"]["spawn_level"]
            _s.BOSS_HP = d["boss"]["hp"]
            _s.BOSS_SPEED = d["boss"]["speed"]
            _s.BOSS_SCORE = d["boss"]["score"]
            _s.BOSS_WIDTH = d["boss"]["width"]
            _s.BOSS_HEIGHT = d["boss"]["height"]
            _s.BOSS_FIRE_INTERVAL_CIRCLE = d["boss"]["fire_interval_circle"]
            _s.BOSS_FIRE_INTERVAL_AIMED = d["boss"]["fire_interval_aimed"]
            _s.BOSS_FIRE_INTERVAL_SPIRAL = d["boss"]["fire_interval_spiral"]
            _s.BOSS_FAN_COUNT = d["boss"]["fan_count"]
            _s.BOSS_FAN_ANGLE = d["boss"]["fan_angle"]
            _s.BOSS_FAN_INTERVAL = d["boss"]["fan_interval"]
            _s.BOSS_BULLET_SPEED = d["boss"]["bullet_speed"]
            _s.BOSS_BULLET_DAMAGE = d["boss"]["bullet_damage"]
            _s.BOSS_ENTER_DURATION = d["boss"]["enter_duration"]
            _s.BOSS_PATROL_MARGIN = d["boss"]["patrol_margin"]
            _s.BOSS_EXPLOSION_COUNT = d["boss"]["explosion_count"]
            _s.BOSS_EXPLOSION_DELAY = d["boss"]["explosion_delay"]
            _s.FINAL_BOSS_LEVEL = d["boss"]["final_level"]
            _s.ENEMY_COLLISION_DAMAGE = d["boss"]["collision_damage"]

            # 难度
            _s.DIFFICULTY_SPAWN_INTERVAL_SCALE = d["difficulty"]["spawn_interval_scale"]
            _s.DIFFICULTY_SPEED_SCALE = d["difficulty"]["speed_scale"]
            _s.DIFFICULTY_HP_SCALE = d["difficulty"]["hp_scale"]
            _s.SPAWN_INTERVAL_MIN = d["difficulty"]["spawn_interval_min"]

            # 背景
            _s.BACKGROUND_BASE_SPEED = d["background"]["base_speed"]

            # 道具
            _s.POWERUP_DROP_CHANCE = d["powerup"]["drop_chance"]
            _s.POWERUP_ELITE_DROP_CHANCE = d["powerup"]["elite_drop_chance"]
            _s.POWERUP_BOSS_DROP_COUNT = d["powerup"]["boss_drop_count"]
            _s.POWERUP_DURATION = d["powerup"]["duration"]
            _s.POWERUP_FALL_SPEED = d["powerup"]["fall_speed"]
            _s.POWERUP_LIFETIME = d["powerup"]["lifetime"]
            _s.POWERUP_SIZE = 28  # 内部常量，无需暴露到 JSON
            _s.POWERUP_PULSE_SPEED = 4.0

            # UI
            _s.FLOATING_TEXT_SPEED = d["ui"]["floating_text_speed"]
            _s.FLOATING_TEXT_LIFETIME = d["ui"]["floating_text_lifetime"]
            _s.LEVEL_SCORE_BASE = d["ui"]["level_score_base"]
            _s.LEVEL_UP_DISPLAY_TIME = d["ui"]["level_up_display_time"]

            # 网络客户端（题9）
            _s.NETWORK_SERVER_HOST = d["network"]["server_host"]
            _s.NETWORK_SERVER_PORT = d["network"]["server_port"]
            _s.NETWORK_AUTO_CONNECT = d["network"].get("auto_connect", False)
            _s.NETWORK_RECONNECT_BASE_DELAY = d["network"]["reconnect_base_delay"]
            _s.NETWORK_RECONNECT_MAX_DELAY = d["network"]["reconnect_max_delay"]
            _s.NETWORK_HEARTBEAT_INTERVAL = d["network"]["heartbeat_interval"]
            _s.NETWORK_HEARTBEAT_TIMEOUT = d["network"]["heartbeat_timeout"]

        except (KeyError, TypeError) as e:
            print(f"[Config] 同步 settings 失败: {e}")


# ==========================================================================
# 全局单例
# ==========================================================================

_config_instance: ConfigManager | None = None


def get_config() -> ConfigManager:
    """获取全局 ConfigManager 单例。"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance
