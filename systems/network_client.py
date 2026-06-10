"""
==============================================================================
飞机大战 — 网络客户端与重连（题9）
==============================================================================
基于 asyncio 的 TCP 游戏客户端：

特性:
  - 自动连接服务器（后台线程运行 asyncio）
  - 指数退避自动重连（1s → 2s → 4s → ... → max 30s）
  - 心跳 PING/PONG 测量网络延迟（RTT）
  - 线程安全的连接状态暴露给游戏主线程
  - 支持指定服务器地址（构造参数 / 配置文件）

连接状态机:
  DISCONNECTED ──[connect]──→ CONNECTING ──[成功]──→ CONNECTED
       ▲                         │                      │
       │                         │                      │
       └────[重连失败]──────────←┘                      │
       └────────────────────────[断开/超时]────────────←┘

用法:
    client = NetworkClient(host="127.0.0.1", port=8888)
    client.start()   # 启动后台线程，自动连接
    ...
    state = client.state       # 线程安全读取连接状态
    latency = client.latency   # 线程安全读取延迟(ms)
    client.stop()    # 停止并断开
==============================================================================
"""

from __future__ import annotations

import asyncio
import struct
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional

from systems.protocol import (
    Message, MessageType, TrafficStats, HeartbeatManager,
    make_conn, make_heartbeat, make_disconn,
    HEADER_SIZE, MAGIC,
)
from systems.logger import GameLogger, LogLevel


# ==========================================================================
# 帧协议（与服务器一致：4B 长度前缀 + 载荷）
# ==========================================================================

async def _read_frame(reader: asyncio.StreamReader) -> bytes | None:
    """读取一帧：4B 大端长度 + 载荷。"""
    try:
        len_bytes = await reader.readexactly(4)
        length = int.from_bytes(len_bytes, "big")
        if length > 65535:
            return None
        return await reader.readexactly(length)
    except (asyncio.IncompleteReadError, OSError):
        return None


async def _write_frame(writer: asyncio.StreamWriter, data: bytes) -> None:
    """写入一帧：4B 大端长度 + 载荷。"""
    length = len(data).to_bytes(4, "big")
    writer.write(length + data)
    await writer.drain()


# ==========================================================================
# 连接状态枚举
# ==========================================================================

class ConnectionState(Enum):
    DISCONNECTED = auto()   # 未连接 / 已断开
    CONNECTING = auto()     # 正在连接
    CONNECTED = auto()      # 已连接


# ==========================================================================
# 默认配置
# ==========================================================================

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8888
RECONNECT_BASE_DELAY = 1.0       # 初始重连延迟（秒）
RECONNECT_MAX_DELAY = 30.0       # 最大重连延迟（秒）
RECONNECT_BACKOFF_MULTIPLIER = 2.0  # 指数退避乘数
HEARTBEAT_INTERVAL = 5.0         # 心跳间隔（秒）
HEARTBEAT_TIMEOUT = 15.0         # 心跳超时（秒）
CONNECTION_TIMEOUT = 10.0        # 连接超时（秒）
LATENCY_WINDOW = 10              # 延迟采样窗口（最近 N 次）


# ==========================================================================
# NetworkClient
# ==========================================================================

class NetworkClient:
    """
    网络游戏客户端。

    在后台线程中运行 asyncio 事件循环，自动连接服务器，
    断开后自动重连（指数退避），定时发送心跳并测量 RTT。
    所有公开状态均线程安全，游戏主线程可随时读取。
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        player_name: str = "Player",
        auto_reconnect: bool = True,
        reconnect_base_delay: float = RECONNECT_BASE_DELAY,
        reconnect_max_delay: float = RECONNECT_MAX_DELAY,
        heartbeat_interval: float = HEARTBEAT_INTERVAL,
        heartbeat_timeout: float = HEARTBEAT_TIMEOUT,
        connection_timeout: float = CONNECTION_TIMEOUT,
    ) -> None:
        self.host = host
        self.port = port
        self.player_name = player_name
        self.auto_reconnect = auto_reconnect
        self.reconnect_base_delay = reconnect_base_delay
        self.reconnect_max_delay = reconnect_max_delay
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.connection_timeout = connection_timeout

        # 线程安全状态
        self._lock = threading.Lock()
        self._state = ConnectionState.DISCONNECTED
        self._latency_ms: float = 0.0
        self._latency_samples: deque[float] = deque(maxlen=LATENCY_WINDOW)
        self._last_state_change: float = time.time()
        self._stats = TrafficStats()
        self._reconnect_attempt: int = 0
        self._total_reconnects: int = 0

        # 后台线程
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._running = False
        self._writer: asyncio.StreamWriter | None = None
        self._reader: asyncio.StreamReader | None = None

        # 回调（游戏线程注册，网络线程调用时通过 call_soon_threadsafe 安全触发）
        self._on_state_change = None
        self._on_message = None

        self._log = GameLogger.get_instance()
        self._ping_send_time: float = 0.0  # 最近一次 PING 发送时间（用于 RTT 计算）

    # ==================================================================
    # 公开属性（线程安全）
    # ==================================================================

    @property
    def state(self) -> ConnectionState:
        with self._lock:
            return self._state

    @state.setter
    def state(self, value: ConnectionState) -> None:
        with self._lock:
            old = self._state
            self._state = value
            self._last_state_change = time.time()
        if old != value:
            self._log.info("Connection state changed",
                           old=old.name, new=value.name)

    @property
    def latency(self) -> float:
        """当前网络延迟（毫秒），0 表示尚未测量。"""
        with self._lock:
            return self._latency_ms

    @property
    def stats(self) -> TrafficStats:
        with self._lock:
            return self._stats

    @property
    def reconnect_attempt(self) -> int:
        with self._lock:
            return self._reconnect_attempt

    @property
    def total_reconnects(self) -> int:
        with self._lock:
            return self._total_reconnects

    @property
    def is_connected(self) -> bool:
        return self.state == ConnectionState.CONNECTED

    @property
    def state_duration(self) -> float:
        """当前状态已持续时间（秒）。"""
        with self._lock:
            return time.time() - self._last_state_change

    @property
    def running(self) -> bool:
        """后台线程是否正在运行。"""
        return self._running

    # ==================================================================
    # 生命周期
    # ==================================================================

    def start(self) -> None:
        """启动后台网络线程。"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._log.info("NetworkClient started", host=self.host, port=self.port)

    def stop(self) -> None:
        """停止后台线程并断开连接。"""
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
        self._log.info("NetworkClient stopped")

    # ==================================================================
    # 消息发送（线程安全）
    # ==================================================================

    def send(self, msg: Message) -> bool:
        """向服务器发送消息。返回 True 表示已入队发送。"""
        if not self._loop or not self._writer:
            self._log.warning("SEND rejected: not connected",
                              msg_type=msg.type.name,
                              has_loop=self._loop is not None,
                              has_writer=self._writer is not None)
            print(f"[NET] send({msg.type.name}) ✗ 失败: 未连接"
                  f" (loop={self._loop is not None}, writer={self._writer is not None})")
            return False
        self._loop.call_soon_threadsafe(
            self._schedule_send, msg
        )
        self._log.debug("SEND queued",
                        msg_type=msg.type.name,
                        seq=msg.seq)
        print(f"[NET] send({msg.type.name}) ✓ 入队成功  seq={msg.seq}")
        return True

    def send_move(self, x: float, y: float, dx: float, dy: float) -> bool:
        from systems.protocol import make_move
        msg = make_move(x, y, dx, dy)
        self._log.debug("send_move() called",
                        x=round(x, 1), y=round(y, 1),
                        dx=round(dx, 2), dy=round(dy, 2))
        print(f"[NET] send_move() → x={x:.1f} y={y:.1f} dx={dx:.1f} dy={dy:.1f}")
        return self.send(msg)

    def send_shoot(self, x: float, y: float, charge: float) -> bool:
        from systems.protocol import make_shoot
        msg = make_shoot(x, y, charge)
        self._log.debug("send_shoot() called",
                        x=round(x, 1), y=round(y, 1),
                        charge=round(charge, 2))
        print(f"[NET] send_shoot() → x={x:.1f} y={y:.1f} charge={charge:.2f}")
        return self.send(msg)

    def send_hit(self, target_id: int, damage: int, x: float, y: float) -> bool:
        """发送命中事件到服务器。target_id: 被击中的目标 ID"""
        from systems.protocol import make_hit
        msg = make_hit(target_id, damage, x, y)
        print(f"[NET] send_hit() → target={target_id} damage={damage} x={x:.1f} y={y:.1f}")
        return self.send(msg)

    # ── 房间操作 ──
    def send_room_create(self, name: str, password: str = "") -> bool:
        from systems.protocol import make_room_create
        print(f"[NET] send_room_create() → name={name} password={'***' if password else ''}")
        return self.send(make_room_create(name, password))

    def send_room_join(self, room_id: str, password: str = "") -> bool:
        from systems.protocol import make_room_join
        print(f"[NET] send_room_join() → room={room_id}")
        return self.send(make_room_join(room_id, password))

    def send_room_leave(self) -> bool:
        from systems.protocol import make_room_leave
        print(f"[NET] send_room_leave()")
        return self.send(make_room_leave())

    def send_room_list(self) -> bool:
        from systems.protocol import make_room_list
        print(f"[NET] send_room_list()")
        return self.send(make_room_list())

    def send_room_ready(self) -> bool:
        from systems.protocol import make_room_ready
        print(f"[NET] send_room_ready()")
        return self.send(make_room_ready())

    # ==================================================================
    # 后台 asyncio 事件循环
    # ==================================================================

    def _run_loop(self) -> None:
        """后台线程入口：创建并运行 asyncio 事件循环。"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.create_task(self._connect_and_run())
            self._loop.run_forever()
        except Exception:
            pass
        finally:
            # 清理待处理任务
            pending = asyncio.all_tasks(self._loop)
            for task in pending:
                task.cancel()
            self._loop.run_until_complete(
                asyncio.gather(*pending, return_exceptions=True)
            )
            self._loop.close()
            self._loop = None

    async def _connect_and_run(self) -> None:
        """主协程：连接 → 处理消息 → 断开 → 重连（循环）。"""
        while self._running:
            self.state = ConnectionState.CONNECTING
            reader, writer = None, None

            try:
                # 带超时的连接
                connect_start = time.time()
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=self.connection_timeout,
                )

                # 发送 CONN 消息
                conn_msg = make_conn(self.player_name)
                raw_conn = conn_msg.encode()
                frame_size = len(raw_conn) + 4
                self._log.info("SEND CONN",
                               player_name=self.player_name,
                               seq=conn_msg.seq,
                               payload_size=len(raw_conn),
                               frame_size=frame_size,
                               host=self.host, port=self.port)
                print(f"[NET] ⬆ SEND CONN → {self.host}:{self.port}  player={self.player_name}  "
                      f"seq={conn_msg.seq}  size={frame_size}B")
                await _write_frame(writer, raw_conn)
                self._log.info("CONN sent OK",
                               player_name=self.player_name,
                               host=self.host, port=self.port)

                # 保存 writer/reader 供 send() 使用
                self._writer = writer
                self._reader = reader

                self.state = ConnectionState.CONNECTED
                with self._lock:
                    self._reconnect_attempt = 0
                    self._total_reconnects += 1 if self._total_reconnects > 0 or self._total_reconnects == 0 else 0

                connect_ms = (time.time() - connect_start) * 1000
                print(f"[NET] 🟢 CONNECTED to {self.host}:{self.port} (handshake={connect_ms:.0f}ms)")
                self._log.info("CONNECTED to server",
                               host=self.host, port=self.port,
                               handshake_ms=round(connect_ms, 1),
                               total_reconnects=self._total_reconnects)

                # 启动心跳
                hb_task = asyncio.create_task(
                    self._heartbeat_loop(writer)
                )

                # 消息接收循环
                await self._receive_loop(reader, writer)

                # 清理心跳
                hb_task.cancel()
                try:
                    await hb_task
                except asyncio.CancelledError:
                    pass

            except (asyncio.TimeoutError, ConnectionRefusedError,
                    OSError) as e:
                if self.state == ConnectionState.CONNECTING:
                    self._log.warning("Connection failed",
                                      host=self.host, port=self.port,
                                      error=str(e))
            except Exception as e:
                self._log.error("Unexpected network error", error=str(e))
            finally:
                # 清除 writer/reader（send() 将不再可用）
                self._writer = None
                self._reader = None
                # 安全关闭 writer
                if writer:
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass

            # 断开后的状态
            if self.state == ConnectionState.CONNECTED:
                stats_summary = self._stats.summary()
                print(f"[NET] 🔴 DISCONNECTED from {self.host}:{self.port}  stats=[{stats_summary}]")
                self._log.info("DISCONNECTED from server",
                               host=self.host, port=self.port,
                               stats=stats_summary,
                               total_reconnects=self._total_reconnects)
                self.state = ConnectionState.DISCONNECTED

            # 重连逻辑
            if not self._running:
                break
            if not self.auto_reconnect:
                break

            delay = self._next_reconnect_delay()
            attempt = self._reconnect_attempt
            print(f"[NET] 🔄 RECONNECT scheduled  attempt={attempt}  delay={delay:.1f}s  "
                  f"total_reconnects={self._total_reconnects}")
            self._log.info("RECONNECT scheduled",
                           delay_sec=round(delay, 1),
                           attempt=attempt,
                           total_reconnects=self._total_reconnects,
                           host=self.host, port=self.port)
            await asyncio.sleep(delay)

    # ==================================================================
    # 消息接收循环
    # ==================================================================

    async def _receive_loop(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """持续读取并处理服务器发来的消息。"""
        hb_manager = HeartbeatManager(
            self.heartbeat_interval, self.heartbeat_timeout
        )
        hb_manager.on_recv(time.time())

        while self._running and self.state == ConnectionState.CONNECTED:
            try:
                payload = await asyncio.wait_for(
                    _read_frame(reader), timeout=self.connection_timeout
                )
            except asyncio.TimeoutError:
                self._log.warning("Server read timeout")
                break

            if payload is None:
                self._log.info("Server closed connection")
                break

            # 解码消息
            try:
                msg = Message.decode(payload)
                with self._lock:
                    self._stats.record_recv(msg, len(payload) + 4)
            except ValueError as e:
                with self._lock:
                    self._stats.record_error()
                continue

            # 处理消息
            if msg.type == MessageType.HEARTBEAT:
                is_pong = msg.payload.get("is_pong", False)

                if is_pong and self._ping_send_time > 0:
                    # 服务端回复 PONG，用本地发送时间计算 RTT（避免时钟偏差）
                    rtt_ms = (time.time() - self._ping_send_time) * 1000
                    with self._lock:
                        self._latency_samples.append(rtt_ms)
                        self._latency_ms = sum(self._latency_samples) / len(self._latency_samples)
                    self._ping_send_time = 0.0
                    self._log.debug("RECV PONG",
                                    rtt_ms=round(rtt_ms, 1),
                                    avg_rtt_ms=round(self._latency_ms, 1))
                elif not is_pong:
                    # 服务端发来 PING，回复 PONG
                    pong = make_heartbeat(is_pong=True)
                    raw = pong.encode()
                    await _write_frame(writer, raw)
                    with self._lock:
                        self._stats.record_send(pong, len(raw) + 4)

                hb_manager.on_recv(time.time())

            elif msg.type == MessageType.CHAT:
                text = msg.payload.get("message", "")
                self._log.info("Server message", text=text)

                # 将来自服务器的聊天文本转换为游戏事件（通过异步事件队列）
                try:
                    from systems.event_bus import EventBus, Event, GameEvent
                    cmd = text.strip().upper()
                    if cmd == "START":
                        EventBus.get_instance().publish_async(Event(GameEvent.GAME_START, {"source": "network"}))
                    elif cmd in ("STOP", "MENU", "GOTO_MENU"):
                        EventBus.get_instance().publish_async(Event(GameEvent.GOTO_MENU, {"source": "network", "cmd": cmd}))
                    elif cmd == "PAUSE":
                        EventBus.get_instance().publish_async(Event(GameEvent.GAME_PAUSE, {"source": "network"}))
                    elif cmd == "RESUME":
                        EventBus.get_instance().publish_async(Event(GameEvent.GAME_RESUME, {"source": "network"}))
                    else:
                        # 其它文本也作为 CONFIG_RELOADED 类型事件传递以便调试/显示
                        EventBus.get_instance().publish_async(Event(GameEvent.CONFIG_RELOADED, {"text": text, "source": "network"}))
                except Exception:
                    pass

            elif msg.type == MessageType.MOVE:
                self._log.info("RECV MOVE",
                               x=round(msg.payload.get("x", 0), 1),
                               y=round(msg.payload.get("y", 0), 1),
                               dx=round(msg.payload.get("dx", 0), 2),
                               dy=round(msg.payload.get("dy", 0), 2),
                               seq=msg.seq)
                print(f"[NET] ⬇ RECV MOVE ← x={msg.payload.get('x',0):.1f} y={msg.payload.get('y',0):.1f}  "
                      f"dx={msg.payload.get('dx',0):.2f} dy={msg.payload.get('dy',0):.2f}  seq={msg.seq}")
                try:
                    from systems.event_bus import EventBus, Event, GameEvent
                    EventBus.get_instance().publish_async(Event(GameEvent.PLAYER_MOVE, msg.payload))
                except Exception:
                    pass

            elif msg.type == MessageType.SHOOT:
                self._log.info("RECV SHOOT",
                               x=round(msg.payload.get("x", 0), 1),
                               y=round(msg.payload.get("y", 0), 1),
                               charge=round(msg.payload.get("charge", 0), 2),
                               seq=msg.seq)
                print(f"[NET] ⬇ RECV SHOOT ← x={msg.payload.get('x',0):.1f} y={msg.payload.get('y',0):.1f}  "
                      f"charge={msg.payload.get('charge',0):.2f}  seq={msg.seq}")
                try:
                    from systems.event_bus import EventBus, Event, GameEvent
                    EventBus.get_instance().publish_async(Event(GameEvent.PLAYER_SHOOT, msg.payload))
                except Exception:
                    pass

            elif msg.type == MessageType.HIT:
                self._log.info("RECV HIT",
                               target_id=msg.payload.get("target_id", 0),
                               damage=msg.payload.get("damage", 0),
                               x=round(msg.payload.get("x", 0), 1),
                               y=round(msg.payload.get("y", 0), 1),
                               seq=msg.seq)
                print(f"[NET] ⬇ RECV HIT ← target={msg.payload.get('target_id',0)}  "
                      f"damage={msg.payload.get('damage',0)}  "
                      f"x={msg.payload.get('x',0):.1f} y={msg.payload.get('y',0):.1f}  seq={msg.seq}")
                # ⚠️ BUGFIX: 原代码缺少 EventBus 发布，导致命中不掉血
                try:
                    from systems.event_bus import EventBus, Event, GameEvent
                    EventBus.get_instance().publish_async(Event(GameEvent.PLAYER_HIT, msg.payload))
                except Exception:
                    pass

            elif msg.type == MessageType.SYNC:
                raw_len = len(msg.payload.get("raw", b""))
                self._log.info("RECV SYNC",
                               player_count=msg.payload.get("player_count", 0),
                               raw_data_len=raw_len,
                               seq=msg.seq)
                print(f"[NET] ⬇ RECV SYNC ← player_count={msg.payload.get('player_count', '?')}  "
                      f"raw_len={raw_len}B  seq={msg.seq}")

            elif msg.type == MessageType.SHOT_RESULT:
                shot_seq = msg.payload.get("shot_seq", 0)
                result = msg.payload.get("result", 0)
                damage = msg.payload.get("damage", 0)
                labels = {0: "HIT ✅", 1: "MISS", 2: "REJECT 🚫"}
                label = labels.get(result, f"UNKNOWN({result})")
                self._log.info("RECV SHOT_RESULT",
                               shot_seq=shot_seq, result=result,
                               damage=damage)
                print(f"[NET] ⬇ SHOT_RESULT ← {label}  shot_seq={shot_seq}"
                      f"  damage={damage}")

            elif msg.type == MessageType.ROOM_INFO:
                subtype = msg.payload.get("subtype", "info")
                data = msg.payload.get("data", {})
                self._log.info("RECV ROOM_INFO", subtype=subtype)
                if subtype == "info":
                    print(f"[NET] 🏠 ROOM_INFO: {data.get('player_count',0)}/8 "
                          f"ready={len(data.get('ready',[]))}")
                elif subtype == "list":
                    rooms = data.get("rooms", [])
                    print(f"[NET] 📋 ROOM_LIST: {len(rooms)} rooms")
                    for r in rooms:
                        print(f"  {r['id']}: {r['name']} ({r['player_count']}/8) {'🔒' if r['has_password'] else '🔓'}")
                elif subtype == "start":
                    print(f"[NET] 🎮 ROOM_START: teamA={data.get('team_a',[])} teamB={data.get('team_b',[])}")
                elif subtype == "disband":
                    print(f"[NET] 💥 ROOM_DISBAND")
                elif subtype == "error":
                    print(f"[NET] ❌ ROOM_ERROR: {data.get('message','?')}")
                try:
                    from systems.event_bus import EventBus, Event, GameEvent
                    EventBus.get_instance().publish_async(
                        Event(GameEvent.CONFIG_RELOADED,
                              {"text": f"ROOM_{subtype.upper()}", "source": "network", "room_data": data})
                    )
                except Exception:
                    pass

            elif msg.type == MessageType.TEAM_SCORE:
                sa = msg.payload.get("score_a", 0)
                sb = msg.payload.get("score_b", 0)
                print(f"[NET] ⚔ TEAM_SCORE: A={sa} B={sb}")
                try:
                    from systems.event_bus import EventBus, Event, GameEvent
                    EventBus.get_instance().publish_async(
                        Event(GameEvent.CONFIG_RELOADED,
                              {"text": "TEAM_SCORE", "source": "network", "room_data": msg.payload})
                    )
                except Exception:
                    pass

            elif msg.type == MessageType.GAME_TIMER:
                remaining = msg.payload.get("remaining_sec", 0)
                total = msg.payload.get("total_sec", 120)
                print(f"[NET] ⏱ GAME_TIMER: {remaining:.0f}s/{total:.0f}s")
                try:
                    from systems.event_bus import EventBus, Event, GameEvent
                    EventBus.get_instance().publish_async(
                        Event(GameEvent.CONFIG_RELOADED,
                              {"text": "GAME_TIMER", "source": "network", "room_data": msg.payload})
                    )
                except Exception:
                    pass

            elif msg.type == MessageType.BATTLE_END:
                winner = msg.payload.get("winner", "?")
                sa = msg.payload.get("score_a", 0)
                sb = msg.payload.get("score_b", 0)
                stats = msg.payload.get("stats", [])
                print(f"[NET] 🏁 BATTLE_END: winner={winner} A={sa} B={sb} players={len(stats)}")
                for s in stats:
                    print(f"  cid={s['cid']} kills={s['kills']} deaths={s['deaths']}")
                try:
                    from systems.event_bus import EventBus, Event, GameEvent
                    EventBus.get_instance().publish_async(
                        Event(GameEvent.CONFIG_RELOADED,
                              {"text": "BATTLE_END", "source": "network", "room_data": msg.payload})
                    )
                except Exception:
                    pass

    # ==================================================================
    # 心跳循环
    # ==================================================================

    async def _heartbeat_loop(self, writer: asyncio.StreamWriter) -> None:
        """定期发送 PING 以测量延迟并维持连接。"""
        while self._running and self.state == ConnectionState.CONNECTED:
            await asyncio.sleep(self.heartbeat_interval)
            if not self.is_connected:
                break
            try:
                # 发送 PING（记录本地发送时间用于 RTT 计算）
                self._ping_send_time = time.time()
                ping = make_heartbeat(is_pong=False)
                raw = ping.encode()
                await _write_frame(writer, raw)
                with self._lock:
                    self._stats.record_send(ping, len(raw) + 4)
            except Exception:
                break

    # ==================================================================
    # 重连延迟计算
    # ==================================================================

    def _next_reconnect_delay(self) -> float:
        """计算下一次重连的等待时间（指数退避）。"""
        with self._lock:
            self._reconnect_attempt += 1
            attempt = self._reconnect_attempt

        delay = self.reconnect_base_delay * (RECONNECT_BACKOFF_MULTIPLIER ** (attempt - 1))
        delay = min(delay, self.reconnect_max_delay)
        # 添加 ±20% 随机抖动，避免惊群效应
        import random
        jitter = delay * 0.2 * (random.random() * 2 - 1)
        return max(0.1, delay + jitter)

    # ==================================================================
    # 内部方法
    # ==================================================================

    def _schedule_send(self, msg: Message) -> None:
        """在事件循环线程中执行发送（由 call_soon_threadsafe 调度）。"""
        # 这个方法在事件循环线程中运行，需要获取当前的 writer
        # 由于 writer 存储在协程局部，这里创建一个任务
        if self._loop:
            asyncio.ensure_future(
                self._async_send(msg), loop=self._loop
            )

    async def _async_send(self, msg: Message) -> None:
        """在事件循环线程中实际发送消息。"""
        if not self._writer:
            self._log.warning("SEND dropped: writer is None",
                              msg_type=msg.type.name, seq=msg.seq)
            print(f"[NET] _async_send({msg.type.name}) ✗ 丢弃: writer 为空")
            return
        try:
            raw = msg.encode()
            frame_size = len(raw) + 4
            mtype = msg.type

            # ── 按消息类型记录详细日志 ──
            if mtype == MessageType.MOVE:
                self._log.info("SEND MOVE",
                               x=round(msg.payload.get("x", 0), 1),
                               y=round(msg.payload.get("y", 0), 1),
                               dx=round(msg.payload.get("dx", 0), 2),
                               dy=round(msg.payload.get("dy", 0), 2),
                               seq=msg.seq, size=frame_size)
                print(f"[NET] ⬆ SEND MOVE → x={msg.payload.get('x',0):.1f} y={msg.payload.get('y',0):.1f}  "
                      f"dx={msg.payload.get('dx',0):.2f} dy={msg.payload.get('dy',0):.2f}  "
                      f"seq={msg.seq}  size={frame_size}B")
            elif mtype == MessageType.SHOOT:
                self._log.info("SEND SHOOT",
                               x=round(msg.payload.get("x", 0), 1),
                               y=round(msg.payload.get("y", 0), 1),
                               charge=round(msg.payload.get("charge", 0), 2),
                               seq=msg.seq, size=frame_size)
                print(f"[NET] ⬆ SEND SHOOT → x={msg.payload.get('x',0):.1f} y={msg.payload.get('y',0):.1f}  "
                      f"charge={msg.payload.get('charge',0):.2f}  seq={msg.seq}  size={frame_size}B")
            elif mtype == MessageType.HIT:
                self._log.info("SEND HIT",
                               target_id=msg.payload.get("target_id", 0),
                               damage=msg.payload.get("damage", 0),
                               x=round(msg.payload.get("x", 0), 1),
                               y=round(msg.payload.get("y", 0), 1),
                               seq=msg.seq, size=frame_size)
                print(f"[NET] ⬆ SEND HIT → target={msg.payload.get('target_id',0)}  "
                      f"damage={msg.payload.get('damage',0)}  seq={msg.seq}  size={frame_size}B")
            elif mtype == MessageType.DISCONN:
                self._log.info("SEND DISCONN",
                               reason=msg.payload.get("reason", 0),
                               seq=msg.seq, size=frame_size)
                print(f"[NET] ⬆ SEND DISCONN → reason={msg.payload.get('reason',0)}  "
                      f"seq={msg.seq}  size={frame_size}B")
            else:
                self._log.debug("SEND",
                                msg_type=mtype.name,
                                seq=msg.seq, size=frame_size)
                print(f"[NET] ⬆ SEND {mtype.name} → seq={msg.seq}  size={frame_size}B")

            await _write_frame(self._writer, raw)
            with self._lock:
                self._stats.record_send(msg, frame_size)
        except Exception as e:
            self._log.error("SEND failed",
                            msg_type=msg.type.name, seq=msg.seq,
                            error=str(e))
            print(f"[NET] ✗ SEND FAILED  {msg.type.name}  seq={msg.seq}  error={e}")

    # ==================================================================
    # 状态摘要（供 UI 使用）
    # ==================================================================

    def status_text(self) -> str:
        """返回一行连接状态文本（供 HUD 显示）。"""
        s = self.state
        if s == ConnectionState.CONNECTED:
            return f"ONLINE  {self.host}:{self.port}  {self.latency:.0f}ms"
        elif s == ConnectionState.CONNECTING:
            return f"CONNECTING...  {self.host}:{self.port}  (attempt {self.reconnect_attempt})"
        else:
            return f"OFFLINE  {self.host}:{self.port}"

    def status_color(self) -> tuple[int, int, int]:
        """返回状态对应的颜色（绿/黄/红）。"""
        s = self.state
        if s == ConnectionState.CONNECTED:
            return (0, 255, 0)    # GREEN
        elif s == ConnectionState.CONNECTING:
            return (255, 255, 0)  # YELLOW
        else:
            return (255, 0, 0)    # RED
