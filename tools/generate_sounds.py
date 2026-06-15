"""
==============================================================================
FlyWars 音效生成器 — 程序化合成所有音效
==============================================================================
使用 pygame.sndarray + numpy 生成 PCM 波形，
保存为 44100Hz 16bit mono WAV 文件。

用法：
    python tools/generate_sounds.py

输出到 assets/sounds/ 目录。
已有文件不会被覆盖（加 --force 强制覆盖）。
"""

import os
import sys
import argparse

import numpy as np

# 确保项目根目录在 Python 路径中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_OUTPUT_DIR = os.path.join(_PROJECT_ROOT, "assets", "sounds")

# 采样参数
SAMPLE_RATE: int = 44100
MAX_AMP: int = 28000


def save_wav(filename: str, samples: np.ndarray) -> None:
    """将 numpy 数组保存为 16bit mono WAV 文件。"""
    import struct
    import wave

    filepath = os.path.join(_OUTPUT_DIR, filename)
    if os.path.exists(filepath) and not args.force:
        print(f"  ⏭  已存在: {filename}")
        return

    # 钳位到 [-32768, 32767]
    samples = np.clip(samples, -32768, 32767).astype(np.int16)

    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(samples.tobytes())
    print(f"  ✅ 生成: {filename}")


# ==========================================================================
# 音效生成函数
# ==========================================================================

def make_shoot() -> np.ndarray:
    """激光射击 — 高频衰减 + 噪声尾迹"""
    n = int(SAMPLE_RATE * 0.12)
    t = np.arange(n) / SAMPLE_RATE
    env = np.exp(-t * 50)
    wave = np.sin(2 * np.pi * 2200 * t) * env * MAX_AMP
    wave += np.sin(2 * np.pi * 1800 * t) * env * MAX_AMP * 0.5
    noise = np.random.uniform(-1, 1, n) * np.exp(-t * 80) * MAX_AMP * 0.15
    return (wave + noise).astype(np.float64)


def make_explosion() -> np.ndarray:
    """爆炸 — 白噪声 + 低频衰减"""
    n = int(SAMPLE_RATE * 0.35)
    t = np.arange(n) / SAMPLE_RATE
    env = np.exp(-t * 8)
    noise = np.random.uniform(-1, 1, n) * env * MAX_AMP
    low = np.sin(2 * np.pi * 80 * t) * env * MAX_AMP * 0.6
    mid = np.sin(2 * np.pi * 160 * t) * env * MAX_AMP * 0.3
    return (noise + low + mid).astype(np.float64)


def make_hit() -> np.ndarray:
    """受伤 — 金属撞击 + 短促低音"""
    n = int(SAMPLE_RATE * 0.15)
    t = np.arange(n) / SAMPLE_RATE
    env = np.exp(-t * 30)
    wave = np.sin(2 * np.pi * 300 * t) * env * MAX_AMP
    wave += np.sin(2 * np.pi * 600 * t) * env * MAX_AMP * 0.5
    noise = np.random.uniform(-1, 1, n) * env * MAX_AMP * 0.2
    return (wave + noise).astype(np.float64)


def make_death() -> np.ndarray:
    """死亡 — 音调骤降的坠落感"""
    n = int(SAMPLE_RATE * 0.6)
    t = np.arange(n) / SAMPLE_RATE
    env = np.exp(-t * 4)
    # 频率从 400Hz 线性下降到 40Hz
    freq = 400 - 360 * (t / t[-1])
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    wave = np.sin(phase) * env * MAX_AMP
    noise = np.random.uniform(-1, 1, n) * env * MAX_AMP * 0.3
    return (wave + noise).astype(np.float64)


def make_enemy_shoot() -> np.ndarray:
    """敌机射击 — 比玩家射击更低沉"""
    n = int(SAMPLE_RATE * 0.1)
    t = np.arange(n) / SAMPLE_RATE
    env = np.exp(-t * 40)
    wave = np.sin(2 * np.pi * 800 * t) * env * MAX_AMP
    wave += np.sin(2 * np.pi * 600 * t) * env * MAX_AMP * 0.4
    return wave.astype(np.float64)


def make_boss_alert() -> np.ndarray:
    """Boss 登场 — 上升警报音"""
    n = int(SAMPLE_RATE * 0.8)
    t = np.arange(n) / SAMPLE_RATE
    env = 1.0 - np.exp(-t * 5)  # 淡入
    env *= np.exp(-t * 1.5)     # 整体衰减
    freq = 200 + 600 * (t / t[-1])  # 200→800Hz
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    wave = np.sin(phase) * env * MAX_AMP * 0.7
    # 叠加一个低音持续
    low = np.sin(2 * np.pi * 100 * t) * env * MAX_AMP * 0.3
    return (wave + low).astype(np.float64)


def make_boss_hit() -> np.ndarray:
    """Boss 受伤 — 厚重重击"""
    n = int(SAMPLE_RATE * 0.2)
    t = np.arange(n) / SAMPLE_RATE
    env = np.exp(-t * 15)
    low = np.sin(2 * np.pi * 60 * t) * env * MAX_AMP
    mid = np.sin(2 * np.pi * 120 * t) * env * MAX_AMP * 0.5
    noise = np.random.uniform(-1, 1, n) * env * MAX_AMP * 0.4
    return (low + mid + noise).astype(np.float64)


def make_boss_death() -> np.ndarray:
    """Boss 毁灭 — 多重爆炸叠加"""
    n = int(SAMPLE_RATE * 1.0)
    t = np.arange(n) / SAMPLE_RATE
    env = np.exp(-t * 3)
    # 三次爆炸脉冲
    pulse1 = np.exp(-((t - 0.05) ** 2) / 0.002) * 1.0
    pulse2 = np.exp(-((t - 0.25) ** 2) / 0.003) * 0.8
    pulse3 = np.exp(-((t - 0.50) ** 2) / 0.004) * 0.6
    pulses = pulse1 + pulse2 + pulse3
    noise = np.random.uniform(-1, 1, n) * pulses * MAX_AMP
    low = np.sin(2 * np.pi * 50 * t) * env * MAX_AMP * 0.5
    mid = np.sin(2 * np.pi * 120 * t) * env * MAX_AMP * 0.3
    return (noise + low + mid).astype(np.float64)


def make_powerup() -> np.ndarray:
    """道具拾取 — 上升悦音"""
    n = int(SAMPLE_RATE * 0.25)
    t = np.arange(n) / SAMPLE_RATE
    env = np.exp(-t * 12)
    freq = 800 + 1200 * (t / t[-1])  # 800→2000Hz
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    wave = np.sin(phase) * env * MAX_AMP * 0.6
    wave += np.sin(phase * 1.5) * env * MAX_AMP * 0.3  # 泛音
    return wave.astype(np.float64)


def make_bomb() -> np.ndarray:
    """炸弹 — 低频轰鸣 + 冲击波"""
    n = int(SAMPLE_RATE * 0.5)
    t = np.arange(n) / SAMPLE_RATE
    env = np.exp(-t * 5)
    low = np.sin(2 * np.pi * 40 * t) * env * MAX_AMP
    mid = np.sin(2 * np.pi * 80 * t) * env * MAX_AMP * 0.5
    noise = np.random.uniform(-1, 1, n) * env * MAX_AMP * 0.6
    return (low + mid + noise).astype(np.float64)


def make_level_up() -> np.ndarray:
    """关卡过渡 — 辉煌上升和弦"""
    n = int(SAMPLE_RATE * 0.6)
    t = np.arange(n) / SAMPLE_RATE
    env = np.exp(-t * 3)
    # C-E-G 和弦琶音
    freqs = [262, 330, 392]
    wave = np.zeros(n)
    for i, f in enumerate(freqs):
        delay = i * 0.08
        mask = (t > delay).astype(float)
        local_t = np.maximum(t - delay, 0)
        local_env = np.exp(-local_t * 5) * mask
        wave += np.sin(2 * np.pi * f * local_t) * local_env * MAX_AMP * 0.4
    wave *= np.exp(-t * 1.5)
    return wave.astype(np.float64)


def make_wave_start() -> np.ndarray:
    """新波次 — 警示脉冲"""
    n = int(SAMPLE_RATE * 0.3)
    t = np.arange(n) / SAMPLE_RATE
    env = np.exp(-t * 8)
    freq = 400 + 200 * np.sin(2 * np.pi * 20 * t)  # 颤音
    wave = np.sin(2 * np.pi * freq * t) * env * MAX_AMP * 0.5
    return wave.astype(np.float64)


def make_revive() -> np.ndarray:
    """复活 — 温暖上升"""
    n = int(SAMPLE_RATE * 0.5)
    t = np.arange(n) / SAMPLE_RATE
    env = 1.0 - np.exp(-t * 10)
    env *= np.exp(-t * 2)
    freq = 300 + 700 * (t / t[-1])
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    wave = np.sin(phase) * env * MAX_AMP * 0.5
    wave += np.sin(phase * 0.5) * env * MAX_AMP * 0.3  # 低八度衬托
    return wave.astype(np.float64)


def make_menu_select() -> np.ndarray:
    """菜单 — 清脆点击"""
    n = int(SAMPLE_RATE * 0.06)
    t = np.arange(n) / SAMPLE_RATE
    env = np.exp(-t * 80)
    wave = np.sin(2 * np.pi * 1000 * t) * env * MAX_AMP * 0.3
    return wave.astype(np.float64)


def make_bgm() -> np.ndarray:
    """背景音乐 — 简单的电子节奏循环（8 秒）"""
    duration = 8.0
    n = int(SAMPLE_RATE * duration)
    t = np.arange(n) / SAMPLE_RATE

    # 低音节奏：120BPM 四拍
    beat = 0.5
    bass = np.zeros(n)
    for i in range(int(duration / beat)):
        start = int(i * beat * SAMPLE_RATE)
        end = int(start + beat * 0.3 * SAMPLE_RATE)
        if end > n:
            break
        local_t = (np.arange(end - start)) / SAMPLE_RATE
        bass[start:end] = np.sin(2 * np.pi * 110 * local_t) * np.exp(-local_t * 4)

    # 主旋律：简单的琶音循环
    melody_notes = [262, 330, 392, 330, 294, 349, 440, 349]
    note_len = duration / len(melody_notes)
    melody = np.zeros(n)
    for i, freq in enumerate(melody_notes):
        start = int(i * note_len * SAMPLE_RATE)
        end = int((i + 1) * note_len * SAMPLE_RATE)
        if end > n:
            end = n
        length = end - start
        if length <= 0:
            break
        local_t = np.arange(length) / SAMPLE_RATE
        note = np.sin(2 * np.pi * freq * local_t) * np.exp(-local_t * 2)
        note += np.sin(2 * np.pi * freq * 2 * local_t) * np.exp(-local_t * 2) * 0.3
        melody[start:end] = note[:length]

    # 高频打击
    hihat = np.zeros(n)
    for i in range(int(duration / 0.25)):
        pos = int(i * 0.25 * SAMPLE_RATE)
        if pos >= n:
            break
        env = np.exp(-np.arange(min(200, n - pos)) / SAMPLE_RATE * 100)
        hihat[pos:pos + len(env)] += np.random.uniform(-1, 1, len(env)) * env * 0.15

    wave = bass * 0.5 + melody * 0.4 + hihat * MAX_AMP
    return (wave * MAX_AMP * 0.5).astype(np.float64)


# ==========================================================================
# 主入口
# ==========================================================================

SOUNDS: list[tuple[str, callable]] = [
    ("shoot.wav", make_shoot),
    ("explosion.wav", make_explosion),
    ("hit.wav", make_hit),
    ("death.wav", make_death),
    ("enemy_shoot.wav", make_enemy_shoot),
    ("boss_alert.wav", make_boss_alert),
    ("boss_hit.wav", make_boss_hit),
    ("boss_death.wav", make_boss_death),
    ("powerup.wav", make_powerup),
    ("bomb.wav", make_bomb),
    ("level_up.wav", make_level_up),
    ("wave_start.wav", make_wave_start),
    ("revive.wav", make_revive),
    ("menu_select.wav", make_menu_select),
]

BGM = ("bgm.ogg", make_bgm)


def main():
    parser = argparse.ArgumentParser(description="生成 FlyWars 音效")
    parser.add_argument("--force", action="store_true", help="强制覆盖已有文件")
    parser.add_argument("--bgm", action="store_true", help="同时生成背景音乐")
    global args
    args = parser.parse_args()

    os.makedirs(_OUTPUT_DIR, exist_ok=True)
    print(f"输出目录: {_OUTPUT_DIR}\n")

    for filename, maker in SOUNDS:
        samples = maker()
        save_wav(filename, samples)

    if args.bgm:
        print("\n生成背景音乐（较慢，约 8 秒）...")
        samples = make_bgm()
        # BGM 为 OGG 格式，这里用 WAV 保存（后续可转码）
        save_wav("bgm.wav", samples)

    print(f"\n完成！共处理 {len(SOUNDS)} 个音效。")


if __name__ == "__main__":
    main()
