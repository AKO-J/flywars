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
        """将样本列表转为 16-bit 立体声 PCM 字节串。"""
        arr = array.array('h')
        for s in samples:
            arr.append(s)  # 左声道
            arr.append(s)  # 右声道（同值 = 单声道居中）
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
