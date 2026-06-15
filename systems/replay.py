"""
==============================================================================
飞机大战 — 回放系统
==============================================================================
轻量级输入记录与回放，用于调试和炫技。

原理：
  - 每帧记录玩家输入状态（按键掩码、鼠标/位置、蓄力状态）
  - 回放时逐帧注入这些输入，驱动玩家实体
  - 数据紧凑：每帧仅 ~12 字节

用法：
  recorder = ReplayRecorder()
  recorder.start()
  # 游戏中每帧：
  recorder.record_frame(frame_count, player)
  # 保存：
  data = recorder.export()

  player = ReplayPlayer(data)
  player.start()
  # 回放中每帧：
  input_state = player.play_frame(frame_count)
  player_sprite.apply_replay_input(input_state)
"""

import json
import time
import struct
import zlib
from dataclasses import dataclass, field, asdict
from typing import Any


# ═══════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ReplayFrame:
    """单帧输入记录。"""
    frame: int          # 帧序号
    keys: int           # 按键掩码（每个 bit 代表一个键）
    mouse_x: int        # 鼠标 X（0 表示未用）
    mouse_y: int        # 鼠标 Y
    charge: float       # 蓄力值 (0.0-1.0)
    is_firing: bool     # 是否正在射击
    move_left: bool     # 移动方向
    move_right: bool
    move_up: bool
    move_down: bool

    def to_bytes(self) -> bytes:
        """将本帧编码为紧凑二进制 (16 bytes)。"""
        flags = (
            (int(self.is_firing)   << 0) |
            (int(self.move_left)   << 1) |
            (int(self.move_right)  << 2) |
            (int(self.move_up)     << 3) |
            (int(self.move_down)   << 4)
        )
        charge_int = int(self.charge * 255)
        return struct.pack(
            "<IiHHBB",
            self.frame, self.keys, self.mouse_x, self.mouse_y,
            charge_int, flags,
        )

    @classmethod
    def from_bytes(cls, data: bytes, offset: int = 0) -> tuple["ReplayFrame", int]:
        """从字节解码一帧，返回 (frame, new_offset)。"""
        frame, keys, mx, my, charge_int, flags = struct.unpack(
            "<IiHHBB", data[offset:offset + 16]
        )
        return cls(
            frame=frame, keys=keys,
            mouse_x=mx, mouse_y=my,
            charge=charge_int / 255.0,
            is_firing=bool(flags & 0x01),
            move_left=bool(flags & 0x02),
            move_right=bool(flags & 0x04),
            move_up=bool(flags & 0x08),
            move_down=bool(flags & 0x10),
        ), offset + 16


@dataclass
class ReplayData:
    """完整的回放数据。"""
    version: int = 1
    game_seed: int = 0           # 随机种子（用于精确重现敌机生成）
    timestamp: float = 0.0       # 录制时间
    duration_frames: int = 0     # 总帧数
    duration_seconds: float = 0.0
    final_score: int = 0
    final_level: int = 0
    frames: list[ReplayFrame] = field(default_factory=list)

    def encode(self) -> bytes:
        """编码为压缩二进制。"""
        header = struct.pack("<BIfI", self.version, self.timestamp,
                            self.duration_frames, self.final_score)
        frame_data = b"".join(f.to_bytes() for f in self.frames)
        payload = header + frame_data
        compressed = zlib.compress(payload, level=6)
        return struct.pack("<I", len(payload)) + compressed

    @classmethod
    def decode(cls, data: bytes) -> "ReplayData":
        """从压缩二进制解码。"""
        uncompressed_len = struct.unpack("<I", data[:4])[0]
        compressed = data[4:]
        payload = zlib.decompress(compressed, bufsize=uncompressed_len + 1024)

        version, ts, duration_frames, final_score = struct.unpack(
            "<BIfI", payload[:13]
        )
        rd = cls(
            version=version, timestamp=ts,
            duration_frames=duration_frames, final_score=final_score,
            duration_seconds=duration_frames / 60.0,
        )
        offset = 13
        while offset < len(payload):
            frame, offset = ReplayFrame.from_bytes(payload, offset)
            rd.frames.append(frame)
        return rd


# ═══════════════════════════════════════════════════════════════════
# 录制器
# ═══════════════════════════════════════════════════════════════════

class ReplayRecorder:
    """输入录制器 — 记录每帧玩家输入状态。"""

    def __init__(self) -> None:
        self._recording: bool = False
        self._data: ReplayData = ReplayData()
        self._start_frame: int = 0
        self._start_time: float = 0.0

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self, game_seed: int = 0) -> None:
        """开始录制。"""
        self._recording = True
        self._data = ReplayData(
            game_seed=game_seed,
            timestamp=time.time(),
        )
        self._start_frame = 0
        self._start_time = time.time()

    def stop(self) -> ReplayData:
        """停止录制并返回完整数据。"""
        self._recording = False
        if self._data.frames:
            self._data.duration_frames = (
                self._data.frames[-1].frame - self._data.frames[0].frame
            )
        else:
            self._data.duration_frames = 0
        self._data.duration_seconds = time.time() - self._start_time
        return self._data

    def record_frame(self, frame: int, player) -> None:
        """记录一帧的玩家输入状态。"""
        if not self._recording:
            return
        self._data.frames.append(ReplayFrame(
            frame=frame,
            keys=sum(1 << k for k in range(512) if pygame.key.get_pressed()[k]),
            mouse_x=0,
            mouse_y=0,
            charge=player.charge_level if hasattr(player, 'charge_level') else 0.0,
            is_firing=player._is_firing if hasattr(player, '_is_firing') else False,
            move_left=player.move_left if hasattr(player, 'move_left') else False,
            move_right=player.move_right if hasattr(player, 'move_right') else False,
            move_up=player.move_up if hasattr(player, 'move_up') else False,
            move_down=player.move_down if hasattr(player, 'move_down') else False,
        ))

    def export(self) -> bytes:
        """导出为紧凑二进制格式。"""
        if self._recording:
            self.stop()
        return self._data.encode()

    def save(self, filepath: str) -> None:
        """保存到文件。"""
        data = self.export()
        with open(filepath, "wb") as f:
            f.write(data)


# ═══════════════════════════════════════════════════════════════════
# 回放器
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ReplayInputState:
    """回放输出的输入状态 — 可以直接应用到 Player。"""
    keys: int = 0
    charge: float = 0.0
    is_firing: bool = False
    move_left: bool = False
    move_right: bool = False
    move_up: bool = False
    move_down: bool = False

    def apply_to(self, player) -> None:
        """将回放输入状态应用到玩家实体。"""
        if hasattr(player, '_is_firing'):
            player._is_firing = self.is_firing
        if hasattr(player, 'move_left'):
            player.move_left = self.move_left
        if hasattr(player, 'move_right'):
            player.move_right = self.move_right
        if hasattr(player, 'move_up'):
            player.move_up = self.move_up
        if hasattr(player, 'move_down'):
            player.move_down = self.move_down
        if hasattr(player, 'charge_level'):
            # 注：蓄力值由游戏逻辑驱动，回放时设置近似值
            pass


class ReplayPlayer:
    """回放播放器 — 按帧回放录制的输入。"""

    def __init__(self, data: bytes | ReplayData) -> None:
        if isinstance(data, bytes):
            self._data = ReplayData.decode(data)
        else:
            self._data = data
        self._playing: bool = False
        self._frame_index: int = 0
        self._current_input: ReplayInputState = ReplayInputState()
        self._total_frames: int = len(self._data.frames)

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def progress(self) -> float:
        """回放进度 0.0-1.0。"""
        if self._total_frames <= 0:
            return 1.0
        return self._frame_index / self._total_frames

    @property
    def total_duration(self) -> float:
        return self._data.duration_seconds

    def start(self) -> None:
        self._playing = True
        self._frame_index = 0

    def stop(self) -> None:
        self._playing = False

    def play_frame(self, current_frame: int) -> ReplayInputState | None:
        """
        播放一帧 — 根据当前游戏帧号查找对应输入帧。
        返回 None 表示回放结束。
        """
        if not self._playing or self._frame_index >= self._total_frames:
            self._playing = False
            return None

        # 查找对应帧
        rf = self._data.frames[self._frame_index]
        if rf.frame > current_frame:
            # 还没到该帧
            return self._current_input

        # 前进到当前帧
        while (self._frame_index < self._total_frames
               and self._data.frames[self._frame_index].frame <= current_frame):
            rf = self._data.frames[self._frame_index]
            self._current_input = ReplayInputState(
                keys=rf.keys,
                charge=rf.charge,
                is_firing=rf.is_firing,
                move_left=rf.move_left,
                move_right=rf.move_right,
                move_up=rf.move_up,
                move_down=rf.move_down,
            )
            self._frame_index += 1

        return self._current_input


# 延迟导入（仅在 record_frame 中使用）
import pygame  # noqa: E402
