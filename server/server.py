"""
==============================================================================
飞机大战 — 异步 TCP 服务器框架（题8）
==============================================================================
基于 asyncio 的 TCP 游戏服务器：

  用法:
    python server/server.py --host 127.0.0.1 --port 8888 --max-clients 10

  管理命令（服务器终端输入）:
    /list            — 列出所有连接的客户端
    /kick <id>       — 踢出指定客户端
    /stats           — 流量统计
    /shutdown        — 优雅关闭

特性:
  - 多客户端并发（asyncio）
  - 最大连接限制
  - 协议消息帧（4B 长度前缀 + Message 载荷）
  - 心跳超时检测
  - 优雅关闭（SIGINT/SIGTERM → 通知所有客户端 → 关闭）
  - 网络日志记录
==============================================================================
"""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import sys
import time
from typing import Optional

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from systems.protocol import (
    Message, MessageType, TrafficStats, HeartbeatManager,
    make_conn, make_chat, make_disconn, make_heartbeat,
    make_sync, make_shot_result, make_room_info,
    make_team_score, make_game_timer, make_battle_end,
    HEADER_SIZE,
)
from systems.logger import GameLogger, LogLevel
from systems.frame_io import read_frame, write_frame


# ==========================================================================
# 配置
# ==========================================================================

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8888
MAX_CLIENTS = 10
HEARTBEAT_INTERVAL = 5.0
HEARTBEAT_TIMEOUT = 15.0
CONNECTION_TIMEOUT = 30.0


# ==========================================================================
# 帧协议: 从 systems.frame_io 导入（read_frame / write_frame）
# ==========================================================================


# ==========================================================================
# 客户端处理器
# ==========================================================================

class ClientHandler:
    """管理单个客户端连接。"""

    def __init__(self, client_id: int, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter, addr: tuple) -> None:
        self.id = client_id
        self.reader = reader
        self.writer = writer
        self.addr = f"{addr[0]}:{addr[1]}"
        self.connected_at = time.time()
        self.last_active = time.time()   # 最近一次收到消息的时间
        self._alive = True

    async def close(self, reason: str = "") -> None:
        """安全关闭连接。"""
        if not self._alive:
            return
        self._alive = False
        try:
            if reason:
                disconn = make_disconn(reason=0)
                await write_frame(self.writer, disconn.encode())
        except Exception:
            pass
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

    @property
    def alive(self) -> bool:
        return self._alive


# ==========================================================================
# 房间系统
# ==========================================================================

class Room:
    def __init__(self, rid: str, name: str, password: str, owner_cid: int):
        self.id = rid
        self.name = name
        self.password = password
        self.owner = owner_cid
        self.players: list[int] = []     # 加入顺序
        self.team_a: list[int] = []       # 索引偶数
        self.team_b: list[int] = []       # 索引奇数
        self.ready: set[int] = set()
        self.state = "waiting"
        self._countdown_task: asyncio.Task | None = None

        # ── 团队积分 ──
        self.score_a: int = 0
        self.score_b: int = 0
        self.kills: dict[int, int] = {}     # cid → kills
        self.deaths: dict[int, int] = {}    # cid → deaths
        self.game_start_time: float = 0.0
        self.game_duration: float = 120.0    # 120秒
        self._game_timer_task: asyncio.Task | None = None

    @property
    def player_count(self) -> int:
        return len(self.players)

    def add_player(self, cid: int) -> str:
        if len(self.players) >= 8:
            raise ValueError("房间已满")
        self.players.append(cid)
        if (len(self.players) - 1) % 2 == 0:
            self.team_a.append(cid)
            return "A"
        else:
            self.team_b.append(cid)
            return "B"

    def remove_player(self, cid: int):
        self.players.remove(cid)
        self.ready.discard(cid)
        if cid in self.team_a:
            self.team_a.remove(cid)
        elif cid in self.team_b:
            self.team_b.remove(cid)

    def to_dict(self, full: bool = False) -> dict:
        base = {
            "id": self.id, "name": self.name,
            "has_password": bool(self.password),
            "player_count": self.player_count,
            "state": self.state, "owner": self.owner,
        }
        if full:
            base["team_a"] = self.team_a
            base["team_b"] = self.team_b
            base["ready"] = list(self.ready)
            base["players"] = self.players
        return base


class RoomManager:
    def __init__(self, clients_ref: dict, broadcast_coro):
        self._clients = clients_ref
        self._broadcast = broadcast_coro
        self._rooms: dict[str, Room] = {}
        self._player_room: dict[int, str] = {}

    async def create(self, name: str, password: str, creator_cid: int) -> Room:
        import random, string
        while True:
            rid = ''.join(random.choices(string.digits, k=6))
            if rid not in self._rooms:
                break
        room = Room(rid, name, password, creator_cid)
        room.add_player(creator_cid)
        self._rooms[rid] = room
        self._player_room[creator_cid] = rid
        return room

    async def join(self, rid: str, password: str, cid: int) -> Room:
        room = self._rooms.get(rid)
        if not room or room.state != "waiting":
            raise ValueError("房间不存在或已开始游戏")
        if room.player_count >= 8:
            raise ValueError("房间已满")
        if room.password and room.password != password:
            raise ValueError("密码错误")
        if cid in self._player_room:
            raise ValueError("已在另一个房间中")
        room.add_player(cid)
        self._player_room[cid] = rid
        await self._push_room_info(rid)
        return room

    async def leave(self, cid: int):
        rid = self._player_room.get(cid)
        if not rid:
            return
        room = self._rooms[rid]
        room.remove_player(cid)
        del self._player_room[cid]
        if cid == room.owner:
            await self._disband(rid)
        elif not room.players:
            del self._rooms[rid]
        else:
            await self._push_room_info(rid)

    async def toggle_ready(self, cid: int):
        rid = self._player_room.get(cid)
        if not rid:
            raise ValueError("不在任何房间中")
        room = self._rooms[rid]
        if cid in room.ready:
            room.ready.discard(cid)
        else:
            room.ready.add(cid)
        await self._push_room_info(rid)
        if room.player_count >= 2 and len(room.ready) == room.player_count:
            if room._countdown_task:
                room._countdown_task.cancel()
            await self._start_game(rid)

    async def list_rooms(self) -> list[dict]:
        return [r.to_dict(full=False)
                for r in self._rooms.values() if r.state == "waiting"]

    async def _push_room_info(self, rid: str):
        room = self._rooms.get(rid)
        if not room:
            return
        info = make_room_info("info", room.to_dict(full=True))
        data = info.encode()
        frame_size = len(data) + 4
        for cid, handler in list(self._clients.items()):
            if cid in room.players and handler.alive:
                try:
                    await write_frame(handler.writer, data)
                except Exception:
                    pass

    async def _start_game(self, rid: str):
        room = self._rooms.get(rid)
        if not room:
            return
        room.state = "playing"
        room.game_start_time = time.time()
        room.score_a = 0
        room.score_b = 0
        for cid in room.players:
            room.kills[cid] = 0
            room.deaths[cid] = 0

        start = make_room_info("start", {"team_a": room.team_a, "team_b": room.team_b})
        data = start.encode()
        for cid, handler in list(self._clients.items()):
            if cid in room.players and handler.alive:
                try:
                    await write_frame(handler.writer, data)
                except Exception:
                    pass

        # 通过 ROOM_INFO(game_start) 触发每个客户端的 GAME_START
        go_msg = make_room_info("game_start", {})
        go_data = go_msg.encode()
        for cid, handler in list(self._clients.items()):
            if cid in room.players and handler.alive:
                try:
                    await write_frame(handler.writer, go_data)
                except Exception:
                    pass

        # ── 启动游戏计时器 + 积分推送 ──
        if room._game_timer_task:
            room._game_timer_task.cancel()
        room._game_timer_task = asyncio.create_task(self._game_loop(rid))

    async def _game_loop(self, rid: str):
        """游戏循环：每秒推送积分 + 计时，超时判定胜负。"""
        room = self._rooms.get(rid)
        if not room:
            return
        total = room.game_duration
        while room.state == "playing":
            await asyncio.sleep(1.0)
            room = self._rooms.get(rid)
            if not room or room.state != "playing":
                break
            elapsed = time.time() - room.game_start_time
            remaining = max(0, total - elapsed)

            # 推送积分
            kills_summary = {}
            for cid in room.players:
                kills_summary[str(cid)] = room.kills.get(cid, 0)
            sc = make_team_score(room.score_a, room.score_b, kills_summary)
            tmr = make_game_timer(remaining, total)
            await self._push_to_room(rid, sc)
            await self._push_to_room(rid, tmr)

            # 计时结束
            if remaining <= 0:
                await self._end_game(rid, "timeout")
                break

    async def _push_to_room(self, rid: str, msg: Message):
        room = self._rooms.get(rid)
        if not room:
            return
        data = msg.encode()
        for cid, handler in list(self._clients.items()):
            if cid in room.players and handler.alive:
                try:
                    await write_frame(handler.writer, data)
                except Exception:
                    pass

    async def _end_game(self, rid: str, reason: str):
        room = self._rooms.get(rid)
        if not room:
            return
        if room._game_timer_task:
            room._game_timer_task.cancel()
        winner = "draw"
        if room.score_a > room.score_b:
            winner = "A"
        elif room.score_b > room.score_a:
            winner = "B"

        stats = []
        for cid in room.players:
            stats.append({
                "cid": cid,
                "kills": room.kills.get(cid, 0),
                "deaths": room.deaths.get(cid, 0),
            })
        end = make_battle_end(winner, room.score_a, room.score_b, stats)
        await self._push_to_room(rid, end)
        room.state = "waiting"

    async def _disband(self, rid: str):
        room = self._rooms.pop(rid, None)
        if not room:
            return
        disband = make_room_info("disband", {})
        data = disband.encode()
        for cid in room.players:
            self._player_room.pop(cid, None)
            handler = self._clients.get(cid)
            if handler and handler.alive:
                try:
                    await write_frame(handler.writer, data)
                except Exception:
                    pass


# ==========================================================================
# 服务器核心
# ==========================================================================

class GameServer:
    """异步 TCP 游戏服务器。"""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 max_clients: int = MAX_CLIENTS) -> None:
        self.host = host
        self.port = port
        self.max_clients = max_clients

        self._server: asyncio.Server | None = None
        self._clients: dict[int, ClientHandler] = {}
        self._next_id: int = 1
        self._running = False
        self._stats = TrafficStats()
        self._log = GameLogger.get_instance()

        # ── 玩家状态追踪（用于 SYNC 广播）──
        self._players: dict[int, dict] = {}  # cid → {name, x, y, hp}

        # ── 射击校验（防作弊）──
        # _shot_tracker[pid] = {"last_time": ts, "count": n, "window_start": ts}
        self._shot_tracker: dict[int, dict] = {}
        self._shot_max_rate: float = 4.0       # 每秒最多 N 发
        self._shot_pos_tolerance: float = 400.0  # 射击位置与上次位置最大偏差(px)

        # ── 房间管理器 ──
        self.rooms = RoomManager(self._clients, self._broadcast)

    # ==================================================================
    # 启动与停止
    # ==================================================================

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client, self.host, self.port,
        )
        self._running = True
        self._log.info("Server started", host=self.host, port=self.port,
                       max_clients=self.max_clients)
        print(f"\n[Server] Listening on {self.host}:{self.port}")
        print(f"[Server] Commands: /list /kick <id> /stats /shutdown\n")

        # 启动管理 CLI、心跳检查、状态同步
        asyncio.create_task(self._admin_cli())
        asyncio.create_task(self._heartbeat_checker())
        asyncio.create_task(self._sync_loop())

    async def shutdown(self) -> None:
        """优雅关闭。"""
        self._log.info("Server shutting down...", clients=len(self._clients))
        print(f"\n[Server] Shutting down, notifying {len(self._clients)} clients...")

        # 通知所有客户端
        for handler in list(self._clients.values()):
            await handler.close(reason="server_shutdown")

        # 关闭服务端 socket
        if self._server:
            self._server.close()
            await self._server.wait_closed()

        self._running = False
        self._log.info("Server stopped")
        print("[Server] Stopped")

    # ==================================================================
    # 客户端连接处理
    # ==================================================================

    async def _handle_client(self, reader: asyncio.StreamReader,
                             writer: asyncio.StreamWriter) -> None:
        addr = writer.get_extra_info("peername")

        # 连接数检查
        if len(self._clients) >= self.max_clients:
            self._log.warning("Connection rejected (full)", addr=str(addr))
            writer.close()
            await writer.wait_closed()
            return

        # 注册客户端
        cid = self._next_id
        self._next_id += 1
        handler = ClientHandler(cid, reader, writer, addr)
        self._clients[cid] = handler
        self._log.info("Client connected", id=cid, addr=handler.addr)

        # 心跳管理器
        hb = HeartbeatManager(HEARTBEAT_INTERVAL, HEARTBEAT_TIMEOUT)
        hb.on_recv(time.time())

        try:
            while self._running and handler.alive:
                try:
                    payload = await asyncio.wait_for(
                        read_frame(reader), timeout=CONNECTION_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    self._log.warning("Client timeout", id=cid)
                    break

                if payload is None:
                    break  # 客户端断开

                # 解码消息
                try:
                    msg = Message.decode(payload)
                    self._stats.record_recv(msg, len(payload) + 4)
                except ValueError as e:
                    self._stats.record_error()
                    continue

                # 更新活跃时间（用于心跳超时检测）
                handler.last_active = time.time()

                # ── 处理消息 ──
                if msg.type == MessageType.CONN:
                    pname = msg.payload.get("player_name", "?")
                    self._players[cid] = {"name": pname, "x": 0.0, "y": 0.0, "hp": 100}
                    self._log.info("RECV CONN", id=cid, player_name=pname,
                                   total_players=len(self._players))
                    print(f"[Server] 🔗 RECV CONN  id={cid}  player={pname}  "
                          f"players={len(self._players)}")
                    # 回复欢迎消息
                    welcome = make_chat(f"WELCOME {cid}")
                    await write_frame(writer, welcome.encode())
                    self._stats.record_send(welcome, len(welcome.encode()) + 4)

                elif msg.type == MessageType.HEARTBEAT:
                    hb.on_recv(time.time())
                    # 回复 PONG
                    pong = make_heartbeat(is_pong=True)
                    raw_pong = pong.encode()
                    await write_frame(writer, raw_pong)
                    self._stats.record_send(pong, len(raw_pong) + 4)

                elif msg.type == MessageType.MOVE:
                    x = msg.payload.get("x", 0)
                    y = msg.payload.get("y", 0)
                    dx = msg.payload.get("dx", 0)
                    dy = msg.payload.get("dy", 0)
                    # 更新玩家坐标
                    if cid in self._players:
                        self._players[cid]["x"] = x
                        self._players[cid]["y"] = y
                    self._log.info("RECV MOVE", id=cid,
                                   x=round(x, 1), y=round(y, 1),
                                   dx=round(dx, 2), dy=round(dy, 2),
                                   seq=msg.seq)
                    print(f"[Server] ⬇ RECV MOVE  id={cid}  x={x:.1f} y={y:.1f}  "
                          f"dx={dx:.2f} dy={dy:.2f}  seq={msg.seq}")
                    # 广播给其他客户端
                    await self._broadcast(msg, exclude=cid)

                elif msg.type == MessageType.SHOOT:
                    shot_x = msg.payload.get("x", 0)
                    shot_y = msg.payload.get("y", 0)
                    charge = msg.payload.get("charge", 0)
                    shot_seq = msg.seq
                    self._log.info("RECV SHOOT", id=cid,
                                   x=round(shot_x, 1), y=round(shot_y, 1),
                                   charge=round(charge, 2), seq=shot_seq)
                    print(f"[Server] ⬇ RECV SHOOT  id={cid}  "
                          f"x={shot_x:.1f} y={shot_y:.1f}  "
                          f"charge={charge:.2f}  seq={shot_seq}")

                    # ── 射击合法性校验 ──
                    valid, reject_reason = self._validate_shot(cid, shot_x, shot_y)
                    if not valid:
                        self._log.warning("SHOT REJECTED", id=cid,
                                          reason=reject_reason, seq=shot_seq)
                        print(f"[Server] 🚫 SHOT REJECTED  id={cid}  reason={reject_reason}")
                        result_msg = make_shot_result(shot_seq, 2, 0)  # REJECT
                        raw = result_msg.encode()
                        await write_frame(writer, raw)
                        self._stats.record_send(result_msg, len(raw) + 4)
                        continue  # 不广播非法射击

                    # 合法射击 → 广播给其他客户端 + 回 HIT 确认
                    await self._broadcast(msg, exclude=cid)
                    result_msg = make_shot_result(shot_seq, 0, 10)  # HIT, damage=10
                    raw_r = result_msg.encode()
                    await write_frame(writer, raw_r)
                    self._stats.record_send(result_msg, len(raw_r) + 4)
                    print(f"[Server] ✅ SHOT_RESULT(HIT) → id={cid}  seq={shot_seq}")

                elif msg.type == MessageType.HIT:
                    target_id = msg.payload.get("target_id", 0)
                    damage = msg.payload.get("damage", 0)
                    hit_x = msg.payload.get("x", 0)
                    hit_y = msg.payload.get("y", 0)
                    self._log.info("RECV HIT", id=cid,
                                   target_id=target_id, damage=damage,
                                   x=round(hit_x, 1), y=round(hit_y, 1),
                                   seq=msg.seq)
                    print(f"[Server] ⬇ RECV HIT  id={cid}  target={target_id}  "
                          f"damage={damage}  "
                          f"x={hit_x:.1f} y={hit_y:.1f}  "
                          f"seq={msg.seq}")

                    # ── 服务器端 HIT 验证（反作弊）──
                    hit_valid, hit_reason = self._validate_hit(
                        cid, target_id, damage, hit_x, hit_y
                    )
                    if not hit_valid:
                        self._log.warning("HIT REJECTED", id=cid,
                                          target_id=target_id,
                                          reason=hit_reason)
                        print(f"[Server] 🚫 HIT REJECTED  id={cid}  "
                              f"target={target_id}  reason={hit_reason}")
                        continue  # 不广播非法 HIT

                    # 更新被击中玩家的 HP
                    if target_id in self._players:
                        old_hp = self._players[target_id]["hp"]
                        self._players[target_id]["hp"] = max(0, old_hp - damage)
                        print(f"[Server] 💔 PLAYER_HIT  target={target_id}  "
                              f"hp={old_hp}→{self._players[target_id]['hp']}  "
                              f"damage={damage}")
                        self._log.info("PLAYER_HIT", target_id=target_id,
                                       old_hp=old_hp,
                                       new_hp=self._players[target_id]["hp"],
                                       damage=damage)
                    # ── 团队积分累加（击杀敌人 → 队伍 +10分）──
                    rid = self.rooms._player_room.get(cid)
                    if rid:
                        room = self.rooms._rooms.get(rid)
                        if room and room.state == "playing":
                            room.kills[cid] = room.kills.get(cid, 0) + 1
                            if cid in room.team_a:
                                room.score_a += 10
                            elif cid in room.team_b:
                                room.score_b += 10

                    # 广播 HIT 给其他客户端（排除发送者，本地已扣血）
                    await self._broadcast(msg, exclude=cid)

                elif msg.type == MessageType.CHAT:
                    self._log.info("CHAT", id=cid, text=msg.payload.get("message", ""))
                    print(f"[Server] 💬 CHAT  id={cid}  text={msg.payload.get('message', '')}")
                    # 广播给所有客户端
                    await self._broadcast(msg, exclude=cid)

                # ── 房间消息 ──
                elif msg.type == MessageType.ROOM_CREATE:
                    name = msg.payload.get("name", "未命名")
                    pwd = msg.payload.get("password", "")
                    try:
                        room = await self.rooms.create(name, pwd, cid)
                        print(f"[Server] 🏠 ROOM_CREATE  id={room.id}  owner={cid}  name={name}")
                        await self.rooms._push_room_info(room.id)
                    except ValueError as e:
                        print(f"[Server] ❌ ROOM_CREATE failed: {e}")
                        err = make_room_info("error", {"message": str(e)})
                        await write_frame(writer, err.encode())

                elif msg.type == MessageType.ROOM_JOIN:
                    rid = msg.payload.get("room_id", "")
                    pwd = msg.payload.get("password", "")
                    try:
                        await self.rooms.join(rid, pwd, cid)
                        print(f"[Server] 🚪 ROOM_JOIN  room={rid}  player={cid}")
                    except ValueError as e:
                        print(f"[Server] ❌ ROOM_JOIN failed: {e}")
                        err = make_room_info("error", {"message": str(e)})
                        await write_frame(writer, err.encode())

                elif msg.type == MessageType.ROOM_LEAVE:
                    try:
                        await self.rooms.leave(cid)
                        print(f"[Server] 🚶 ROOM_LEAVE  player={cid}")
                    except ValueError as e:
                        print(f"[Server] ❌ ROOM_LEAVE failed: {e}")
                        err = make_room_info("error", {"message": str(e)})
                        await write_frame(writer, err.encode())

                elif msg.type == MessageType.ROOM_LIST:
                    rooms = await self.rooms.list_rooms()
                    info = make_room_info("list", {"rooms": rooms})
                    await write_frame(writer, info.encode())
                    print(f"[Server] 📋 ROOM_LIST  sent {len(rooms)} rooms to {cid}")

                elif msg.type == MessageType.ROOM_READY:
                    try:
                        await self.rooms.toggle_ready(cid)
                        print(f"[Server] ✅ ROOM_READY toggled  player={cid}")
                    except ValueError as e:
                        print(f"[Server] ❌ ROOM_READY failed: {e}")
                        err = make_room_info("error", {"message": str(e)})
                        await write_frame(writer, err.encode())

                elif msg.type == MessageType.DISCONN:
                    self._log.info("Client disconnected (self)", id=cid)
                    print(f"[Server] 🔌 DISCONN  id={cid}")
                    break

        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            # 清理
            self._clients.pop(cid, None)
            self._players.pop(cid, None)  # 移除玩家状态
            # 自动退出房间
            try:
                asyncio.ensure_future(self.rooms.leave(cid))
            except Exception:
                pass
            await handler.close()
            self._log.info("Client disconnected", id=cid, addr=handler.addr,
                           remaining_players=len(self._players))
            print(f"[Server] 🔌 Client left  id={cid}  "
                  f"players_remaining={len(self._players)}")

    # ==================================================================
    # 射击合法性校验
    # ==================================================================

    def _validate_shot(self, player_id: int, x: float, y: float) -> tuple[bool, str]:
        """校验射击是否合法。返回 (合法?, 原因)。"""
        import time as _time
        now = _time.time()

        # ① 位置基本合法性
        if not (0 <= x <= 2000 and 0 <= y <= 1500):
            return False, f"坐标越界 ({x:.0f},{y:.0f})"

        # ② 与上次位置偏差检查（跳过首次射击：位置为默认值时不做检查）
        pinfo = self._players.get(player_id)
        if pinfo:
            last_x = pinfo.get("x", 0)
            last_y = pinfo.get("y", 0)
            # 跳过首次射击（客户端可能尚未发送 MOVE）
            if last_x != 0 or last_y != 0:
                dist = ((x - last_x) ** 2 + (y - last_y) ** 2) ** 0.5
                if dist > self._shot_pos_tolerance:
                    return False, f"位置偏差过大 ({dist:.0f}px > {self._shot_pos_tolerance:.0f})"

        # ③ 射速限制
        tracker = self._shot_tracker.get(player_id)
        if tracker is None:
            self._shot_tracker[player_id] = {
                "last_time": now, "count": 1, "window_start": now,
            }
            return True, "ok"

        # 滑动窗口：每秒重置
        if now - tracker["window_start"] > 1.0:
            tracker["window_start"] = now
            tracker["count"] = 0

        tracker["count"] += 1
        tracker["last_time"] = now

        if tracker["count"] > self._shot_max_rate:
            return False, f"射速过快 ({tracker['count']}发/秒 > {self._shot_max_rate})"

        return True, "ok"

    # ==================================================================
    # HIT 合法性校验（反作弊）
    # ==================================================================

    # 单次命中最大合理伤害
    _HIT_MAX_DAMAGE: int = 50
    # 命中的目标必须存在且存活
    _HIT_MAX_DISTANCE: float = 600.0  # 射击者与目标最大距离(px)

    def _validate_hit(self, shooter_id: int, target_id: int,
                      damage: int, hit_x: float, hit_y: float
                      ) -> tuple[bool, str]:
        """校验 HIT 报告是否合理。返回 (合法?, 原因)。"""
        # ① 不能攻击自己
        if shooter_id == target_id:
            return False, "攻击自己"

        # ② 目标必须存在
        target = self._players.get(target_id)
        if target is None:
            return False, f"目标不存在 (id={target_id})"

        # ③ 目标必须存活
        if target.get("hp", 0) <= 0:
            return False, f"目标已死亡 (hp={target['hp']})"

        # ④ 伤害合理性
        if damage <= 0 or damage > self._HIT_MAX_DAMAGE:
            return False, f"伤害异常 ({damage} > {self._HIT_MAX_DAMAGE})"

        # ⑤ 距离检查（射击者与目标的坐标偏差）
        shooter = self._players.get(shooter_id)
        if shooter:
            sx, sy = shooter.get("x", 0), shooter.get("y", 0)
            dist = ((hit_x - sx) ** 2 + (hit_y - sy) ** 2) ** 0.5
            if dist > self._HIT_MAX_DISTANCE:
                return False, (f"命中距离过大 ({dist:.0f}px > "
                               f"{self._HIT_MAX_DISTANCE:.0f})")

        return True, "ok"

    # ==================================================================
    # 广播
    # ==================================================================

    async def _broadcast(self, msg: Message, exclude: int | None = None) -> None:
        """广播消息给所有客户端（可选排除某客户端）。"""
        data = msg.encode()
        frame_size = len(data) + 4
        sent_count = 0
        for cid, handler in list(self._clients.items()):
            if cid == exclude or not handler.alive:
                continue
            try:
                await write_frame(handler.writer, data)
                self._stats.record_send(msg, frame_size)
                sent_count += 1
            except Exception as e:
                self._log.warning("Broadcast failed to client",
                                  target_id=cid, error=str(e))
        if sent_count > 0:
            self._log.debug("BROADCAST",
                            msg_type=msg.type.name,
                            sent_to=sent_count,
                            excluded=exclude,
                            size=frame_size)
            print(f"[Server] ⬆ BROADCAST {msg.type.name}  → {sent_count} client(s)  "
                  f"size={frame_size}B  exclude={exclude}")

    # ==================================================================
    # 状态同步循环
    # ==================================================================

    async def _sync_loop(self) -> None:
        """定期广播 SYNC 消息，包含所有玩家的 id/x/y/hp。"""
        import struct as _struct
        SYNC_INTERVAL = 1.0  # 每秒同步一次

        while self._running:
            await asyncio.sleep(SYNC_INTERVAL)
            if not self._players:
                continue

            # 打包: 每个玩家 I(4B id) + f(4B x) + f(4B y) + B(1B hp) = 13B
            data = b""
            for pid, pinfo in self._players.items():
                data += _struct.pack("!IffB", pid,
                                     float(pinfo.get("x", 0)),
                                     float(pinfo.get("y", 0)),
                                     int(pinfo.get("hp", 100)))

            sync_msg = make_sync(len(self._players), data)
            self._log.info("BROADCAST SYNC",
                           player_count=len(self._players),
                           data_len=len(data))
            print(f"[Server] ⬆ BROADCAST SYNC  players={len(self._players)}  "
                  f"data={len(data)}B")
            await self._broadcast(sync_msg, exclude=None)

    # ==================================================================
    # 心跳检查
    # ==================================================================

    async def _heartbeat_checker(self) -> None:
        """定时检查所有客户端心跳，超时则断开。"""
        while self._running:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            now = time.time()
            for cid, handler in list(self._clients.items()):
                if not handler.alive:
                    continue
                # 检查最近活跃时间，超过超时则断开
                idle = now - handler.last_active
                if idle > HEARTBEAT_TIMEOUT:
                    self._log.warning("Heartbeat timeout",
                                      id=cid, idle_sec=round(idle, 1))
                    print(f"[Server] ⏰ HEARTBEAT TIMEOUT  id={cid}  "
                          f"idle={idle:.1f}s")
                    await handler.close(reason="heartbeat_timeout")

    # ==================================================================
    # 管理 CLI
    # ==================================================================

    async def _admin_cli(self) -> None:
        """管理命令行（stdin 读取）。"""
        loop = asyncio.get_event_loop()

        while self._running:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
            except Exception:
                break

            if not line:
                continue

            cmd = line.strip()
            if not cmd:
                continue

            if cmd == "/list":
                self._cmd_list()
            elif cmd == "/shutdown":
                await self.shutdown()
                break
            elif cmd.startswith("/kick "):
                try:
                    cid = int(cmd.split()[1])
                    self._cmd_kick(cid)
                except (ValueError, IndexError):
                    print("Usage: /kick <id>")
            elif cmd == "/stats":
                self._cmd_stats()
            elif cmd == "/help":
                print("Commands: /list /kick <id> /stats /shutdown /help")
            else:
                print(f"Unknown command: {cmd}  (type /help)")

    def _cmd_list(self) -> None:
        if not self._clients:
            print("  (no connections)")
            return
        print(f"  {'ID':<6} {'ADDR':<22} {'UPTIME(s)'}")
        print(f"  {'-'*6} {'-'*22} {'-'*10}")
        now = time.time()
        for cid, h in self._clients.items():
            uptime = int(now - h.connected_at)
            print(f"  {cid:<6} {h.addr:<22} {uptime}")

    def _cmd_kick(self, cid: int) -> None:
        handler = self._clients.get(cid)
        if handler is None:
            print(f"  Client {cid} not found")
            return
        asyncio.create_task(handler.close(reason="kicked"))
        print(f"  Kicked client {cid} ({handler.addr})")
        self._log.info("Kicked client", id=cid, addr=handler.addr)

    def _cmd_stats(self) -> None:
        print(f"  {self._stats.summary()}")
        print(f"  Connections: {len(self._clients)}/{self.max_clients}")


# ==========================================================================
# 入口
# ==========================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="飞机大战 — 游戏服务器")
    parser.add_argument("--host", default=DEFAULT_HOST, help="监听地址")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="监听端口")
    parser.add_argument("--max-clients", type=int, default=MAX_CLIENTS,
                        help="最大连接数")
    args = parser.parse_args()

    server = GameServer(args.host, args.port, args.max_clients)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # 信号处理（非 Windows）
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(
                server.shutdown()))

    try:
        loop.run_until_complete(server.start())
        # 保持运行直到 shutdown
        loop.run_forever()
    except KeyboardInterrupt:
        print("\n[Server] Interrupted")
    finally:
        try:
            loop.run_until_complete(server.shutdown())
        except Exception:
            pass
        loop.close()


if __name__ == "__main__":
    main()
