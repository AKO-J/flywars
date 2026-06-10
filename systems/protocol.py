"""
==============================================================================
飞机大战 — 二进制消息协议（题7）
==============================================================================
基于 struct 的二进制协议：

  消息头 (12 bytes):
    ┌────────┬─────────┬──────┬────────┬──────────┐
    │ magic  │ version │ type │ length │   seq    │
    │ 4B     │ 1B      │ 1B   │ 2B BE  │ 4B BE    │
    └────────┴─────────┴──────┴────────┴──────────┘
    magic  = 0x53484D50 ("SHMP")
    version = 0x01
    type    = MessageType 枚举值
    length  = payload 长度 (0-65535)
    seq     = 序列号

  支持的消息类型: CONN AUTH MOVE SHOOT HIT SYNC CHAT HEARTBEAT DISCONN

  心跳: 每 5 秒发 PING，超时 15 秒视为断线
  统计: 收发字节数、消息计数、丢包模拟
==============================================================================
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


# ==========================================================================
# 协议常量
# ==========================================================================

MAGIC: int = 0x53484D50        # "SHMP"
HEADER_FMT: str = "!IBBH I"    # magic, version, type, length(pad), seq
HEADER_SIZE: int = struct.calcsize(HEADER_FMT)  # 12 bytes
PROTOCOL_VERSION: int = 1
MAX_PAYLOAD: int = 65535


class MessageType(IntEnum):
    CONN      = 0x01   # 连接请求/响应
    AUTH      = 0x02   # 认证令牌
    MOVE      = 0x03   # 移动同步
    SHOOT     = 0x04   # 射击事件
    HIT       = 0x05   # 命中事件
    SYNC      = 0x06   # 状态同步
    CHAT      = 0x07   # 聊天消息
    HEARTBEAT = 0x08   # 心跳 PING/PONG
    DISCONN   = 0x09   # 断开连接
    SHOT_RESULT = 0x0A  # 射击结果（服务端→客户端）

    # ── 房间系统 ──
    ROOM_CREATE = 0x0B   # 创建房间（客户端→服务端）
    ROOM_JOIN   = 0x0C   # 加入房间（客户端→服务端）
    ROOM_LEAVE  = 0x0D   # 离开房间（客户端→服务端）
    ROOM_LIST   = 0x0E   # 查询房间列表（客户端→服务端）
    ROOM_READY  = 0x0F   # 准备/取消准备（客户端→服务端）
    ROOM_INFO   = 0x10   # 房间信息推送（服务端→客户端）

    # ── 团队积分 ──
    TEAM_SCORE  = 0x11   # 队伍积分推送（服务端→客户端）
    GAME_TIMER  = 0x12   # 游戏计时器推送（服务端→客户端）
    BATTLE_END  = 0x13   # 战斗结束推送（服务端→客户端）


# ==========================================================================
# 消息体编码/解码
# ==========================================================================

def _encode_conn(player_name: str) -> bytes:
    return player_name.encode("utf-8")

def _decode_conn(payload: bytes) -> dict:
    return {"player_name": payload.decode("utf-8")}

def _encode_auth(token: str) -> bytes:
    return token.encode("utf-8")

def _decode_auth(payload: bytes) -> dict:
    return {"token": payload.decode("utf-8")}

def _encode_move(x: float, y: float, dx: float, dy: float) -> bytes:
    return struct.pack("!ffff", x, y, dx, dy)

def _decode_move(payload: bytes) -> dict:
    x, y, dx, dy = struct.unpack("!ffff", payload)
    return {"x": x, "y": y, "dx": dx, "dy": dy}

def _encode_shoot(x: float, y: float, charge: float) -> bytes:
    return struct.pack("!fff", x, y, charge)

def _decode_shoot(payload: bytes) -> dict:
    x, y, charge = struct.unpack("!fff", payload)
    return {"x": x, "y": y, "charge": charge}

def _encode_hit(target_id: int, damage: int, x: float, y: float) -> bytes:
    return struct.pack("!IHff", target_id, damage, x, y)

def _decode_hit(payload: bytes) -> dict:
    tid, dmg, x, y = struct.unpack("!IHff", payload)
    return {"target_id": tid, "damage": dmg, "x": x, "y": y}

def _encode_sync(player_count: int, data: bytes) -> bytes:
    return struct.pack("!B", player_count) + data

def _decode_sync(payload: bytes) -> dict:
    count = payload[0]
    return {"player_count": count, "raw": payload[1:]}

def _encode_chat(message: str) -> bytes:
    return message.encode("utf-8")

def _decode_chat(payload: bytes) -> dict:
    return {"message": payload.decode("utf-8")}

def _encode_heartbeat(is_pong: bool) -> bytes:
    return struct.pack("!?d", is_pong, time.time())

def _decode_heartbeat(payload: bytes) -> dict:
    is_pong, ts = struct.unpack("!?d", payload)
    return {"is_pong": is_pong, "timestamp": ts}

def _encode_disconn(reason: int) -> bytes:
    return struct.pack("!B", reason)

def _decode_disconn(payload: bytes) -> dict:
    return {"reason": payload[0]}

def _encode_shot_result(shot_seq: int, result: int, damage: int) -> bytes:
    """result: 0=HIT, 1=MISS, 2=REJECT"""
    return struct.pack("!IBH", shot_seq, result, damage)

def _decode_shot_result(payload: bytes) -> dict:
    shot_seq, result, damage = struct.unpack("!IBH", payload)
    return {"shot_seq": shot_seq, "result": result, "damage": damage}

# ── 房间消息：统一用 JSON 字符串承载 ──
import json as _json

def _encode_room_json(**kwargs) -> bytes:
    return _json.dumps(kwargs, ensure_ascii=False).encode("utf-8")

def _decode_room_json(payload: bytes) -> dict:
    return _json.loads(payload.decode("utf-8"))


# 编解码函数表
_ENCODERS = {
    MessageType.CONN:      ("str",  _encode_conn,      _decode_conn),
    MessageType.AUTH:      ("str",  _encode_auth,      _decode_auth),
    MessageType.MOVE:      ("16B",  _encode_move,      _decode_move),
    MessageType.SHOOT:     ("12B",  _encode_shoot,     _decode_shoot),
    MessageType.HIT:       ("14B",  _encode_hit,       _decode_hit),
    MessageType.SYNC:      ("var",  _encode_sync,      _decode_sync),
    MessageType.CHAT:      ("str",  _encode_chat,      _decode_chat),
    MessageType.HEARTBEAT: ("9B",   _encode_heartbeat, _decode_heartbeat),
    MessageType.DISCONN:   ("1B",   _encode_disconn,   _decode_disconn),
    MessageType.SHOT_RESULT: ("7B", _encode_shot_result, _decode_shot_result),
    MessageType.ROOM_CREATE: ("json", _encode_room_json, _decode_room_json),
    MessageType.ROOM_JOIN:   ("json", _encode_room_json, _decode_room_json),
    MessageType.ROOM_LEAVE:  ("json", _encode_room_json, _decode_room_json),
    MessageType.ROOM_LIST:   ("json", _encode_room_json, _decode_room_json),
    MessageType.ROOM_READY:  ("json", _encode_room_json, _decode_room_json),
    MessageType.ROOM_INFO:   ("json", _encode_room_json, _decode_room_json),
    MessageType.TEAM_SCORE:  ("json", _encode_room_json, _decode_room_json),
    MessageType.GAME_TIMER:  ("json", _encode_room_json, _decode_room_json),
    MessageType.BATTLE_END:  ("json", _encode_room_json, _decode_room_json),
}


# ==========================================================================
# Message 数据类
# ==========================================================================

@dataclass
class Message:
    """一条协议消息。"""
    type: MessageType
    payload: dict[str, Any] = field(default_factory=dict)
    seq: int = 0
    version: int = PROTOCOL_VERSION
    timestamp: float = field(default_factory=time.time)

    def encode(self) -> bytes:
        """序列化为二进制字节串。"""
        encoder_info = _ENCODERS.get(self.type)
        if encoder_info is None:
            raise ValueError(f"不支持的消息类型: {self.type}")

        _, encoder, _ = encoder_info
        body = encoder(**self.payload) if self.payload else encoder()

        header = struct.pack(
            HEADER_FMT,
            MAGIC, self.version, int(self.type), len(body), self.seq,
        )
        return header + body

    @classmethod
    def decode(cls, data: bytes) -> "Message":
        """从二进制字节串反序列化。"""
        if len(data) < HEADER_SIZE:
            raise ValueError(f"数据太短: {len(data)} < {HEADER_SIZE}")

        magic, ver, mtype, length, seq = struct.unpack(HEADER_FMT, data[:HEADER_SIZE])

        if magic != MAGIC:
            raise ValueError(f"Magic 不匹配: 0x{magic:08X} != 0x{MAGIC:08X}")
        if length != len(data) - HEADER_SIZE:
            raise ValueError(f"长度不匹配: header={length} actual={len(data) - HEADER_SIZE}")

        try:
            msg_type = MessageType(mtype)
        except ValueError:
            raise ValueError(f"未知消息类型: 0x{mtype:02X}")

        encoder_info = _ENCODERS.get(msg_type)
        if encoder_info is None:
            raise ValueError(f"不支持解码的消息类型: {msg_type}")

        _, _, decoder = encoder_info
        payload = decoder(data[HEADER_SIZE:]) if length > 0 else {}
        return cls(type=msg_type, payload=payload, seq=seq, version=ver)


# ==========================================================================
# 流量统计
# ==========================================================================

@dataclass
class TrafficStats:
    """收发流量统计。"""
    bytes_sent: int = 0
    bytes_recv: int = 0
    msgs_sent: dict[MessageType, int] = field(default_factory=dict)
    msgs_recv: dict[MessageType, int] = field(default_factory=dict)
    errors: int = 0

    def record_send(self, msg: Message, raw_bytes: int) -> None:
        self.bytes_sent += raw_bytes
        self.msgs_sent[msg.type] = self.msgs_sent.get(msg.type, 0) + 1

    def record_recv(self, msg: Message, raw_bytes: int) -> None:
        self.bytes_recv += raw_bytes
        self.msgs_recv[msg.type] = self.msgs_recv.get(msg.type, 0) + 1

    def record_error(self) -> None:
        self.errors += 1

    def summary(self) -> str:
        total_sent = sum(self.msgs_sent.values())
        total_recv = sum(self.msgs_recv.values())
        return (
            f"TX: {self.bytes_sent}B/{total_sent}msg  "
            f"RX: {self.bytes_recv}B/{total_recv}msg  "
            f"ERR: {self.errors}"
        )


# ==========================================================================
# 协议工具函数
# ==========================================================================

def make_conn(player_name: str, seq: int = 0) -> Message:
    return Message(type=MessageType.CONN, payload={"player_name": player_name}, seq=seq)

def make_auth(token: str, seq: int = 0) -> Message:
    return Message(type=MessageType.AUTH, payload={"token": token}, seq=seq)

def make_move(x: float, y: float, dx: float, dy: float, seq: int = 0) -> Message:
    return Message(type=MessageType.MOVE, payload={"x": x, "y": y, "dx": dx, "dy": dy}, seq=seq)

def make_shoot(x: float, y: float, charge: float, seq: int = 0) -> Message:
    return Message(type=MessageType.SHOOT, payload={"x": x, "y": y, "charge": charge}, seq=seq)

def make_hit(target_id: int, damage: int, x: float, y: float, seq: int = 0) -> Message:
    return Message(type=MessageType.HIT, payload={"target_id": target_id, "damage": damage, "x": x, "y": y}, seq=seq)

def make_sync(player_count: int, data: bytes = b"", seq: int = 0) -> Message:
    return Message(type=MessageType.SYNC, payload={"player_count": player_count, "data": data}, seq=seq)

def make_chat(text: str, seq: int = 0) -> Message:
    return Message(type=MessageType.CHAT, payload={"message": text}, seq=seq)

def make_heartbeat(is_pong: bool = False) -> Message:
    return Message(type=MessageType.HEARTBEAT, payload={"is_pong": is_pong})

def make_disconn(reason: int = 0) -> Message:
    return Message(type=MessageType.DISCONN, payload={"reason": reason})

def make_shot_result(shot_seq: int, result: int, damage: int = 0) -> Message:
    """result: 0=HIT, 1=MISS, 2=REJECT"""
    return Message(type=MessageType.SHOT_RESULT, payload={
        "shot_seq": shot_seq, "result": result, "damage": damage,
    })

# ── 房间消息工厂 ──
def make_room_create(name: str, password: str = "") -> Message:
    return Message(type=MessageType.ROOM_CREATE, payload={"name": name, "password": password})

def make_room_join(room_id: str, password: str = "") -> Message:
    return Message(type=MessageType.ROOM_JOIN, payload={"room_id": room_id, "password": password})

def make_room_leave() -> Message:
    return Message(type=MessageType.ROOM_LEAVE, payload={})

def make_room_list() -> Message:
    return Message(type=MessageType.ROOM_LIST, payload={})

def make_room_ready() -> Message:
    return Message(type=MessageType.ROOM_READY, payload={})

def make_room_info(subtype: str, data: dict) -> Message:
    """subtype: info / countdown / start / disband"""
    return Message(type=MessageType.ROOM_INFO, payload={"subtype": subtype, "data": data})

def make_team_score(score_a: int, score_b: int, kills: dict) -> Message:
    return Message(type=MessageType.TEAM_SCORE, payload={
        "score_a": score_a, "score_b": score_b, "kills": kills,
    })

def make_game_timer(remaining: float, total: float) -> Message:
    return Message(type=MessageType.GAME_TIMER, payload={
        "remaining_sec": round(remaining, 1), "total_sec": total,
    })

def make_battle_end(winner: str, score_a: int, score_b: int, stats: list) -> Message:
    return Message(type=MessageType.BATTLE_END, payload={
        "winner": winner, "score_a": score_a, "score_b": score_b, "stats": stats,
    })


# ==========================================================================
# 心跳管理
# ==========================================================================

class HeartbeatManager:
    """心跳管理：定时发 PING，超时判定断线。"""

    def __init__(self, interval: float = 5.0, timeout: float = 15.0) -> None:
        self.interval = interval
        self.timeout = timeout
        self._last_send: float = 0.0
        self._last_recv: float = 0.0
        self._seq: int = 0

    def should_send(self, now: float) -> bool:
        return now - self._last_send >= self.interval

    def send(self, now: float) -> Message:
        self._seq += 1
        self._last_send = now
        return make_heartbeat(is_pong=False)

    def on_recv(self, now: float) -> None:
        self._last_recv = now

    def is_timeout(self, now: float) -> bool:
        if self._last_recv == 0.0:
            return False
        return now - self._last_recv > self.timeout

    def reset(self) -> None:
        self._last_recv = time.time()
        self._last_send = 0.0
