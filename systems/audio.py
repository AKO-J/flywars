"""
==============================================================================
飞机大战 — 音效系统（题14：射击、爆炸与背景音乐）
==============================================================================
使用 pygame.mixer 实现音效播放。

设计：
  - 优先从 assets/sounds/ 加载外部音频文件
  - 文件缺失时自动降级为程序化波形合成（PCM 波形生成）
  - 射击音效：短促频率扫描激光声（80ms）
  - 爆炸音效：白噪声包络冲击声（400ms）
  - 背景音乐：正弦波旋律循环（~12秒），支持循环播放
  - 独立音量控制：音效/音乐分离调节
  - 完整异常处理：mixer 初始化失败 → 静音运行；
    文件加载失败 → 降级合成；合成失败 → 跳过该音效
"""

import array
import math
import os
import random
import pygame
from utils.resource_manager import ResourceManager


class AudioSystem:
    """
    音效管理器。

    使用方法：
      audio = AudioSystem()
      audio.play_shoot()       # 播放射击音效
      audio.play_explosion()   # 播放爆炸音效
      audio.start_bgm()        # 循环播放背景音乐
      audio.stop_bgm()         # 停止背景音乐
      audio.set_sfx_volume(v)  # 设置音效音量 (0.0-1.0)
      audio.set_bgm_volume(v)  # 设置音乐音量 (0.0-1.0)

    属性：
      is_ready   → 音效系统是否可用
      sfx_volume → 当前音效音量
      bgm_volume → 当前背景音乐音量
    """

    SAMPLE_RATE: int = 44100

    # ---- 音频文件路径（相对于项目根目录） ----
    _ASSETS_DIR: str = os.path.join(
        os.path.dirname(__file__), "..", "assets", "sounds"
    )

    SHOOT_FILE: str = os.path.join(_ASSETS_DIR, "shoot.wav")
    EXPLOSION_FILE: str = os.path.join(_ASSETS_DIR, "explosion.wav")
    HIT_FILE: str = os.path.join(_ASSETS_DIR, "hit.wav")
    DEATH_FILE: str = os.path.join(_ASSETS_DIR, "death.wav")
    ENEMY_SHOOT_FILE: str = os.path.join(_ASSETS_DIR, "enemy_shoot.wav")
    BOSS_ALERT_FILE: str = os.path.join(_ASSETS_DIR, "boss_alert.wav")
    BOSS_HIT_FILE: str = os.path.join(_ASSETS_DIR, "boss_hit.wav")
    BOSS_DEATH_FILE: str = os.path.join(_ASSETS_DIR, "boss_death.wav")
    POWERUP_FILE: str = os.path.join(_ASSETS_DIR, "powerup.wav")
    BOMB_FILE: str = os.path.join(_ASSETS_DIR, "bomb.wav")
    LEVEL_UP_FILE: str = os.path.join(_ASSETS_DIR, "level_up.wav")
    WAVE_START_FILE: str = os.path.join(_ASSETS_DIR, "wave_start.wav")
    REVIVE_FILE: str = os.path.join(_ASSETS_DIR, "revive.wav")
    MENU_SELECT_FILE: str = os.path.join(_ASSETS_DIR, "menu_select.wav")
    BGM_FILE: str = os.path.join(_ASSETS_DIR, "bgm.ogg")

    def __init__(self) -> None:
        self._ready: bool = False
        self._sfx_volume: float = 0.7
        self._bgm_volume: float = 0.4

        # ---- 初始化 pygame.mixer ----
        try:
            pygame.mixer.init(
                frequency=self.SAMPLE_RATE, size=-16,
                channels=2, buffer=512
            )
            self._ready = True
        except pygame.error as e:
            print(f"[Audio] mixer 初始化失败，静音运行: {e}")
            # 静音降级：所有 play_xxx / start_bgm 方法检查 self._ready 后直接返回
            self.sfx_shoot = None
            self.sfx_explosion = None
            self._bgm = None
            self._sfx_channel = None
            self._bgm_channel_obj = None
            return

        # ---- 加载或合成音效 ----
        self.sfx_shoot: pygame.mixer.Sound | None = self._load_or_make(
            self.SHOOT_FILE, self._make_shoot, "射击音效"
        )
        self.sfx_explosion: pygame.mixer.Sound | None = self._load_or_make(
            self.EXPLOSION_FILE, self._make_explosion, "爆炸音效"
        )
        self.sfx_hit: pygame.mixer.Sound | None = self._load_or_make(
            self.HIT_FILE, self._make_hit, "受伤音效"
        )
        self.sfx_death: pygame.mixer.Sound | None = self._load_or_make(
            self.DEATH_FILE, self._make_death, "死亡音效"
        )
        self.sfx_enemy_shoot: pygame.mixer.Sound | None = self._load_or_make(
            self.ENEMY_SHOOT_FILE, self._make_enemy_shoot, "敌机射击"
        )
        self.sfx_boss_alert: pygame.mixer.Sound | None = self._load_or_make(
            self.BOSS_ALERT_FILE, self._make_boss_alert, "Boss登场"
        )
        self.sfx_boss_hit: pygame.mixer.Sound | None = self._load_or_make(
            self.BOSS_HIT_FILE, self._make_boss_hit, "Boss受伤"
        )
        self.sfx_boss_death: pygame.mixer.Sound | None = self._load_or_make(
            self.BOSS_DEATH_FILE, self._make_boss_death, "Boss毁灭"
        )
        self.sfx_powerup: pygame.mixer.Sound | None = self._load_or_make(
            self.POWERUP_FILE, self._make_powerup, "道具拾取"
        )
        self.sfx_bomb: pygame.mixer.Sound | None = self._load_or_make(
            self.BOMB_FILE, self._make_bomb, "炸弹"
        )
        self.sfx_level_up: pygame.mixer.Sound | None = self._load_or_make(
            self.LEVEL_UP_FILE, self._make_level_up, "关卡过渡"
        )
        self.sfx_wave_start: pygame.mixer.Sound | None = self._load_or_make(
            self.WAVE_START_FILE, self._make_wave_start, "波次提示"
        )
        self.sfx_revive: pygame.mixer.Sound | None = self._load_or_make(
            self.REVIVE_FILE, self._make_revive, "复活"
        )
        self.sfx_menu_select: pygame.mixer.Sound | None = self._load_or_make(
            self.MENU_SELECT_FILE, self._make_menu_select, "菜单选择"
        )
        self._bgm: pygame.mixer.Sound | None = self._load_or_make(
            self.BGM_FILE, self._make_bgm, "背景音乐"
        )

        # 专用频道（避免音效互相抢占）
        self._sfx_channel: pygame.mixer.Channel = pygame.mixer.Channel(0)
        self._bgm_channel_obj: pygame.mixer.Channel = pygame.mixer.Channel(1)

    # ================================================================
    # 公共接口
    # ================================================================

    def play_shoot(self) -> None:
        """播放射击音效。"""
        if not self._ready or self.sfx_shoot is None:
            return
        self.sfx_shoot.set_volume(self._sfx_volume)
        self.sfx_shoot.play()

    def play_explosion(self) -> None:
        """播放爆炸音效。"""
        if not self._ready or self.sfx_explosion is None:
            return
        self.sfx_explosion.set_volume(self._sfx_volume)
        self.sfx_explosion.play()

    def play_hit(self) -> None:
        if not self._ready or self.sfx_hit is None:
            return
        self.sfx_hit.set_volume(self._sfx_volume)
        self.sfx_hit.play()

    def play_death(self) -> None:
        if not self._ready or self.sfx_death is None:
            return
        self.sfx_death.set_volume(self._sfx_volume)
        self.sfx_death.play()

    def play_enemy_shoot(self) -> None:
        if not self._ready or self.sfx_enemy_shoot is None:
            return
        self.sfx_enemy_shoot.set_volume(self._sfx_volume)
        self.sfx_enemy_shoot.play()

    def play_boss_alert(self) -> None:
        if not self._ready or self.sfx_boss_alert is None:
            return
        self.sfx_boss_alert.set_volume(self._sfx_volume)
        self.sfx_boss_alert.play()

    def play_boss_hit(self) -> None:
        if not self._ready or self.sfx_boss_hit is None:
            return
        self.sfx_boss_hit.set_volume(self._sfx_volume)
        self.sfx_boss_hit.play()

    def play_boss_death(self) -> None:
        if not self._ready or self.sfx_boss_death is None:
            return
        self.sfx_boss_death.set_volume(self._sfx_volume)
        self.sfx_boss_death.play()

    def play_powerup(self) -> None:
        if not self._ready or self.sfx_powerup is None:
            return
        self.sfx_powerup.set_volume(self._sfx_volume)
        self.sfx_powerup.play()

    def play_bomb(self) -> None:
        if not self._ready or self.sfx_bomb is None:
            return
        self.sfx_bomb.set_volume(self._sfx_volume)
        self.sfx_bomb.play()

    def play_level_up(self) -> None:
        if not self._ready or self.sfx_level_up is None:
            return
        self.sfx_level_up.set_volume(self._sfx_volume)
        self.sfx_level_up.play()

    def play_wave_start(self) -> None:
        if not self._ready or self.sfx_wave_start is None:
            return
        self.sfx_wave_start.set_volume(self._sfx_volume)
        self.sfx_wave_start.play()

    def play_revive(self) -> None:
        if not self._ready or self.sfx_revive is None:
            return
        self.sfx_revive.set_volume(self._sfx_volume)
        self.sfx_revive.play()

    def play_menu_select(self) -> None:
        if not self._ready or self.sfx_menu_select is None:
            return
        self.sfx_menu_select.set_volume(self._sfx_volume)
        self.sfx_menu_select.play()

    def start_bgm(self) -> None:
        """循环播放背景音乐。"""
        if not self._ready or self._bgm is None:
            return
        self._bgm.set_volume(self._bgm_volume)
        self._bgm_channel_obj.play(self._bgm, loops=-1)

    def stop_bgm(self) -> None:
        """停止背景音乐。"""
        if not self._ready:
            return
        self._bgm_channel_obj.stop()

    def reset(self) -> None:
        """重置音频状态（新游戏时调用：确保音量正确、BGM 未播放）。"""
        if not self._ready:
            return
        self._bgm_channel_obj.stop()
        self.set_sfx_volume(self._sfx_volume)
        self._bgm.set_volume(self._bgm_volume)

    def set_sfx_volume(self, volume: float) -> None:
        """设置音效音量，取值范围 0.0 ~ 1.0。超出范围自动钳位。"""
        self._sfx_volume = max(0.0, min(1.0, volume))

    def set_bgm_volume(self, volume: float) -> None:
        """设置背景音乐音量，取值范围 0.0 ~ 1.0。即时生效。"""
        self._bgm_volume = max(0.0, min(1.0, volume))
        if self._ready and self._bgm is not None:
            self._bgm.set_volume(self._bgm_volume)

    @property
    def is_ready(self) -> bool:
        """音效系统是否初始化成功并可播放。"""
        return self._ready

    @property
    def sfx_volume(self) -> float:
        return self._sfx_volume

    @property
    def bgm_volume(self) -> float:
        return self._bgm_volume

    # ================================================================
    # 文件加载 — 三级降级策略
    # ================================================================

    @staticmethod
    def _load_sound_file(filepath: str) -> pygame.mixer.Sound | None:
        """
        尝试加载音频文件（优先查 ResourceManager 缓存）。
        """
        # 转为项目相对路径，查 ResourceManager 缓存
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            rel = os.path.relpath(filepath, project_root).replace("\\", "/")
            cached = ResourceManager.get_instance().get_sound(rel)
            if cached is not None:
                return cached
        except (ValueError, OSError):
            pass

        # 回退：直接从磁盘加载
        try:
            if not os.path.exists(filepath):
                return None
            return pygame.mixer.Sound(filepath)
        except FileNotFoundError:
            return None
        except pygame.error as e:
            print(f"[Audio] 无法加载音频文件 '{filepath}': {e}")
            return None
        except PermissionError as e:
            print(f"[Audio] 无权读取音频文件 '{filepath}': {e}")
            return None
        except OSError as e:
            print(f"[Audio] 读取音频文件异常 '{filepath}': {e}")
            return None

    def _load_or_make(
        self,
        filepath: str,
        factory: callable,
        label: str,
    ) -> pygame.mixer.Sound | None:
        """
        三级降级加载：

        L1 → 从 filepath 加载外部音频文件
        L2 → 文件缺失/加载失败 → 调用 factory() 程序化合成
        L3 → 合成也失败 → 返回 None，对应 play_xxx 静默跳过
        """
        # L1: 尝试加载文件
        sound = self._load_sound_file(filepath)
        if sound is not None:
            print(f"[Audio] {label}: 已加载外部文件 → {os.path.basename(filepath)}")
            return sound

        # L2: 降级为程序化合成
        if filepath and os.path.exists(filepath):
            pass  # 文件存在但加载失败 → 已在 _load_sound_file 中打印原因
        else:
            print(f"[Audio] {label}: 文件缺失 '{os.path.basename(filepath)}'，降级为程序化合成")

        try:
            return factory()
        except Exception as e:
            print(f"[Audio] {label}: 程序化合成也失败: {e}")
            return None

    # ================================================================
    # 程序化音效生成（PCM 波形合成）— L2 降级方案
    # ================================================================

    @staticmethod
    def _samples_to_bytes(samples: list[int]) -> bytes:
        """将样本列表转为 16-bit 立体声 PCM 字节串（自动钳位）。"""
        arr = array.array('h')
        for s in samples:
            clamped = max(-32768, min(32767, s))
            arr.append(clamped)  # 左声道
            arr.append(clamped)  # 右声道（同值 = 单声道居中）
        return arr.tobytes()

    def _make_shoot(self) -> pygame.mixer.Sound | None:
        """
        射击音效 — 频率扫描激光声。
        ────────────────────────────
        频率 1500Hz → 200Hz 线性扫描，80ms，振幅线性衰减。
        听感：短促有力的"啾"声，类似经典街机射击音效。
        """
        sr = self.SAMPLE_RATE
        duration = 0.08
        num_samples = int(sr * duration)
        samples: list[int] = [0] * num_samples

        for i in range(num_samples):
            t = i / sr
            progress = i / num_samples
            freq = 1500.0 - 1300.0 * progress       # 频率持续下降
            amp = 0.85 * (1.0 - progress)            # 振幅线性衰减
            samples[i] = int(amp * 32767 * math.sin(2.0 * math.pi * freq * t))

        try:
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except pygame.error as e:
            print(f"[Audio] 射击音效合成失败: {e}")
            return None

    def _make_explosion(self) -> pygame.mixer.Sound | None:
        """
        爆炸音效 — 白噪声包络。
        ────────────────────────────
        白噪声 + 快速起音 + 指数衰减，400ms。
        听感：短促的"轰"声，模拟爆炸冲击感。
        固定随机种子(42)确保每次生成一致。
        """
        sr = self.SAMPLE_RATE
        duration = 0.4
        num_samples = int(sr * duration)
        samples: list[int] = [0] * num_samples
        rng = random.Random(42)

        for i in range(num_samples):
            progress = i / num_samples
            # 快速起音（前2%时间线性爬升）
            if progress < 0.02:
                attack = progress / 0.02
            else:
                attack = 1.0
            decay = math.exp(-progress * 8.0)
            amp = 0.9 * attack * decay
            samples[i] = int(amp * 32767 * rng.uniform(-1.0, 1.0))

        try:
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except pygame.error as e:
            print(f"[Audio] 爆炸音效合成失败: {e}")
            return None

    def _make_hit(self) -> pygame.mixer.Sound | None:
        """受伤音效 — 金属撞击声"""
        try:
            sr = self.SAMPLE_RATE; n = int(sr * 0.15)
            samples = [0] * n
            for i in range(n):
                t = i / sr; env = math.exp(-t * 30)
                v = math.sin(2 * math.pi * 300 * t) * env * 28000
                v += math.sin(2 * math.pi * 600 * t) * env * 14000
                v += (random.random() * 2 - 1) * env * 6000
                samples[i] = int(v)
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except Exception:
            return None

    def _make_death(self) -> pygame.mixer.Sound | None:
        """死亡音效 — 音调骤降坠落"""
        try:
            sr = self.SAMPLE_RATE; n = int(sr * 0.6)
            samples = [0] * n
            freq = 400.0
            phase = 0.0
            for i in range(n):
                t = i / sr; env = math.exp(-t * 4)
                freq = 400 - 360 * (i / n)
                phase += 2 * math.pi * freq / sr
                v = math.sin(phase) * env * 28000
                v += (random.random() * 2 - 1) * env * 8000
                samples[i] = int(v)
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except Exception:
            return None

    def _make_enemy_shoot(self) -> pygame.mixer.Sound | None:
        """敌机射击"""
        try:
            sr = self.SAMPLE_RATE; n = int(sr * 0.1)
            samples = [0] * n
            for i in range(n):
                t = i / sr; env = math.exp(-t * 40)
                v = math.sin(2 * math.pi * 800 * t) * env * 28000
                v += math.sin(2 * math.pi * 600 * t) * env * 11000
                samples[i] = int(v)
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except Exception:
            return None

    def _make_boss_alert(self) -> pygame.mixer.Sound | None:
        """Boss登场 — 上升警报"""
        try:
            sr = self.SAMPLE_RATE; n = int(sr * 0.8)
            samples = [0] * n
            phase = 0.0
            for i in range(n):
                t = i / sr
                env = (1 - math.exp(-t * 5)) * math.exp(-t * 1.5)
                freq = 200 + 600 * (i / n)
                phase += 2 * math.pi * freq / sr
                v = math.sin(phase) * env * 20000
                v += math.sin(2 * math.pi * 100 * t) * env * 8000
                samples[i] = int(v)
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except Exception:
            return None

    def _make_boss_hit(self) -> pygame.mixer.Sound | None:
        """Boss受伤"""
        try:
            sr = self.SAMPLE_RATE; n = int(sr * 0.2)
            samples = [0] * n
            for i in range(n):
                t = i / sr; env = math.exp(-t * 15)
                v = math.sin(2 * math.pi * 60 * t) * env * 28000
                v += (random.random() * 2 - 1) * env * 11000
                samples[i] = int(v)
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except Exception:
            return None

    def _make_boss_death(self) -> pygame.mixer.Sound | None:
        """Boss毁灭 — 多重爆炸"""
        try:
            sr = self.SAMPLE_RATE; n = int(sr * 1.0)
            samples = [0] * n
            for i in range(n):
                t = i / sr; env = math.exp(-t * 3)
                p1 = math.exp(-((t - 0.05)**2) / 0.002)
                p2 = math.exp(-((t - 0.25)**2) / 0.003) * 0.8
                p3 = math.exp(-((t - 0.50)**2) / 0.004) * 0.6
                noise = (random.random() * 2 - 1) * (p1 + p2 + p3) * 20000
                low = math.sin(2 * math.pi * 50 * t) * env * 14000
                samples[i] = int(noise + low)
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except Exception:
            return None

    def _make_powerup(self) -> pygame.mixer.Sound | None:
        """道具拾取 — 上升音阶"""
        try:
            sr = self.SAMPLE_RATE; n = int(sr * 0.25)
            samples = [0] * n
            phase = 0.0
            for i in range(n):
                t = i / sr; env = math.exp(-t * 12)
                freq = 800 + 1200 * (i / n)
                phase += 2 * math.pi * freq / sr
                v = math.sin(phase) * env * 16000
                v += math.sin(phase * 1.5) * env * 8000
                samples[i] = int(v)
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except Exception:
            return None

    def _make_bomb(self) -> pygame.mixer.Sound | None:
        """炸弹 — 低频轰鸣"""
        try:
            sr = self.SAMPLE_RATE; n = int(sr * 0.5)
            samples = [0] * n
            for i in range(n):
                t = i / sr; env = math.exp(-t * 5)
                v = math.sin(2 * math.pi * 40 * t) * env * 28000
                v += (random.random() * 2 - 1) * env * 16000
                samples[i] = int(v)
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except Exception:
            return None

    def _make_level_up(self) -> pygame.mixer.Sound | None:
        """关卡过渡 — 和弦琶音"""
        try:
            sr = self.SAMPLE_RATE; n = int(sr * 0.6)
            samples = [0] * n
            for i in range(n):
                t = i / sr; env = math.exp(-t * 3)
                v = 0.0
                for j, f in enumerate([262, 330, 392]):
                    delay = j * 0.08
                    if t > delay:
                        lt = t - delay
                        le = math.exp(-lt * 5)
                        v += math.sin(2 * math.pi * f * lt) * le * 11000
                samples[i] = int(v * math.exp(-t * 1.5))
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except Exception:
            return None

    def _make_wave_start(self) -> pygame.mixer.Sound | None:
        """波次提示 — 颤音脉冲"""
        try:
            sr = self.SAMPLE_RATE; n = int(sr * 0.3)
            samples = [0] * n
            for i in range(n):
                t = i / sr; env = math.exp(-t * 8)
                v = math.sin(2 * math.pi * (400 + 200 * math.sin(2 * math.pi * 20 * t)) * t)
                samples[i] = int(v * env * 14000)
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except Exception:
            return None

    def _make_revive(self) -> pygame.mixer.Sound | None:
        """复活 — 温暖上升"""
        try:
            sr = self.SAMPLE_RATE; n = int(sr * 0.5)
            samples = [0] * n
            phase = 0.0; phase2 = 0.0
            for i in range(n):
                t = i / sr
                env = (1 - math.exp(-t * 10)) * math.exp(-t * 2)
                freq = 300 + 700 * (i / n)
                phase += 2 * math.pi * freq / sr
                phase2 += 2 * math.pi * freq * 0.5 / sr
                v = math.sin(phase) * env * 14000
                v += math.sin(phase2) * env * 8000
                samples[i] = int(v)
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except Exception:
            return None

    def _make_menu_select(self) -> pygame.mixer.Sound | None:
        """菜单选择 — 清脆点击"""
        try:
            sr = self.SAMPLE_RATE; n = int(sr * 0.06)
            samples = [0] * n
            for i in range(n):
                t = i / sr; env = math.exp(-t * 80)
                v = math.sin(2 * math.pi * 1000 * t) * env * 8000
                samples[i] = int(v)
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(samples))
        except Exception:
            return None

    def _make_bgm(self) -> pygame.mixer.Sound | None:
        """
        背景音乐 — 正弦波旋律循环。
        ────────────────────────────
        8 小节简单旋律 + 低音和声线，约 12 秒循环。
        基频叠加 2 次/3 次谐波使音色温暖不刺耳。
        """
        sr = self.SAMPLE_RATE

        # 音符频率映射 (Hz) — 科学音高记号
        NOTE = {
            'C4': 262, 'D4': 294, 'E4': 330, 'F4': 349,
            'G4': 392, 'A4': 440, 'B4': 494, 'C5': 523,
            'D5': 587, 'E5': 659,
            'C3': 131, 'D3': 147, 'E3': 165, 'F3': 175,
            'G3': 196, 'A3': 220, 'B3': 247,
            'R': 0,  # 休止符
        }

        # 主旋律: [(音符号, 时长ms, 力度), ...]
        melody: list[tuple[str, int, float]] = [
            # 小节 1-2
            ('E4', 180, 1.0), ('G4', 180, 0.9), ('A4', 180, 0.8),
            ('B4', 180, 0.7), ('C5', 360, 0.9), ('B4', 180, 0.7),
            ('A4', 180, 0.6), ('G4', 360, 0.8),
            # 小节 3-4
            ('E4', 180, 0.9), ('D4', 180, 0.8), ('C4', 180, 0.7),
            ('D4', 180, 0.6), ('E4', 180, 0.7), ('G4', 180, 0.6),
            ('E4', 180, 0.5), ('D4', 360, 0.7),
            # 小节 5-6
            ('C5', 180, 0.9), ('B4', 180, 0.8), ('A4', 180, 0.7),
            ('G4', 180, 0.6), ('F4', 180, 0.5), ('E4', 180, 0.6),
            ('D4', 180, 0.5), ('C4', 360, 0.7),
            # 小节 7-8
            ('G4', 180, 0.8), ('A4', 180, 0.7), ('B4', 180, 0.6),
            ('C5', 180, 0.8), ('D5', 360, 0.9), ('C5', 180, 0.7),
            ('B4', 180, 0.6), ('G4', 360, 0.8),
            # 衔接尾音
            ('E4', 360, 0.6),
        ]

        # 低音和声线
        bass_line: list[tuple[str, int, float]] = [
            ('E3', 720, 0.4), ('C3', 720, 0.35),
            ('A3', 720, 0.35), ('G3', 720, 0.3),
            ('F3', 720, 0.3), ('C3', 720, 0.35),
            ('G3', 720, 0.35), ('C3', 720, 0.4),
        ]

        total_duration = sum(dur for _, dur, _ in melody)
        total_samples = int(sr * total_duration / 1000.0)
        samples: list[float] = [0.0] * total_samples

        # ---- 合成旋律轨道 ----
        idx = 0
        for note, dur_ms, vol in melody:
            n = int(sr * dur_ms / 1000.0)
            freq = NOTE[note]
            for i in range(n):
                if idx + i >= total_samples:
                    break
                t = i / sr
                if freq > 0:
                    # 基频 + 2次/3次谐波（增加温暖感）
                    v = (0.7 * math.sin(2.0 * math.pi * freq * t) +
                         0.2 * math.sin(2.0 * math.pi * freq * 2.0 * t) +
                         0.1 * math.sin(2.0 * math.pi * freq * 3.0 * t))
                    samples[idx + i] += v * vol * 0.3
                # 音符尾部轻微衰减（避免咔嗒声）
                decay = 1.0 - 0.05 * (i / max(n, 1))
                samples[idx + i] *= decay
            idx += n

        # ---- 合成低音轨道 ----
        idx = 0
        for note, dur_ms, vol in bass_line:
            n = int(sr * dur_ms / 1000.0)
            freq = NOTE[note]
            for i in range(n):
                if idx + i >= total_samples:
                    break
                t = i / sr
                if freq > 0:
                    v = 0.6 * math.sin(2.0 * math.pi * freq * t) + \
                        0.4 * math.sin(2.0 * math.pi * freq * 2.0 * t)
                    samples[idx + i] += v * vol * 0.25
            idx += n

        # ---- 归一化到 16-bit 范围 ----
        max_val = max(abs(s) for s in samples) if samples else 1.0
        scale = 32767 / max_val if max_val > 0 else 1.0
        int_samples = [int(s * scale) for s in samples]

        try:
            return pygame.mixer.Sound(buffer=self._samples_to_bytes(int_samples))
        except pygame.error as e:
            print(f"[Audio] 背景音乐合成失败: {e}")
            return None
