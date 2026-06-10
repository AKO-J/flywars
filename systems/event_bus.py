"""
==============================================================================
飞机大战 — 事件总线（题4：消息总线与组件解耦）
==============================================================================
EventBus 单例：订阅/取消订阅/发布 + 优先级 + 异步队列 + 事件日志。

用法：
  bus = EventBus.get_instance()
  bus.subscribe(GameEvent.ENEMY_KILLED, my_handler, priority=10)
  bus.publish(Event(GameEvent.ENEMY_KILLED, {"score": 100}))
  bus.unsubscribe(GameEvent.ENEMY_KILLED, my_handler)
==============================================================================
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable

# Handler: (event) -> None
Handler = Callable[["Event"], None]


# ==========================================================================
# 事件类型枚举
# ==========================================================================

class GameEvent(Enum):
    # 状态机
    GAME_START       = auto()
    GAME_OVER        = auto()
    GAME_PAUSE       = auto()
    GAME_RESUME      = auto()
    GAME_QUIT        = auto()
    GAME_VICTORY     = auto()
    GOTO_MENU        = auto()

    # 玩家
    PLAYER_SHOOT     = auto()
    PLAYER_HIT       = auto()
    PLAYER_DEATH     = auto()
    PLAYER_POWERUP   = auto()
    PLAYER_MOVE      = auto()

    # 敌机
    ENEMY_SPAWNED    = auto()
    ENEMY_KILLED     = auto()
    BOSS_SPAWNED     = auto()
    BOSS_DEFEATED    = auto()

    # 分数与关卡
    SCORE_CHANGED    = auto()
    LEVEL_UP         = auto()

    # 系统
    CONFIG_RELOADED  = auto()
    RESOURCE_LOADED  = auto()
    RESOURCE_MISSING = auto()
    BOMB_TRIGGERED   = auto()


# ==========================================================================
# 事件数据类
# ==========================================================================

@dataclass
class Event:
    """游戏事件。"""
    type: GameEvent
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


# ==========================================================================
# EventBus 单例
# ==========================================================================

class EventBus:
    """发布-订阅消息总线。"""

    _instance: EventBus | None = None

    def __init__(self) -> None:
        # 按优先级降序排列的处理器列表
        self._handlers: dict[GameEvent, list[tuple[int, Handler]]] = (
            defaultdict(list)
        )
        # 事件日志（最近 N 条）
        self._log: list[Event] = []
        self._max_log: int = 200
        # 异步队列：本帧收集，下帧执行
        self._pending: list[Event] = []
        self._pending_lock = threading.Lock()  # 保护 _pending 的线程锁
        # 统计
        self._publish_count: dict[GameEvent, int] = defaultdict(int)

    @classmethod
    def get_instance(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ==================================================================
    # 订阅管理
    # ==================================================================

    def subscribe(
        self, event_type: GameEvent, handler: Handler, priority: int = 0,
    ) -> None:
        """订阅事件。priority 越高越先执行。"""
        handlers = self._handlers[event_type]
        # 防止重复订阅
        for _, h in handlers:
            if h is handler:
                return
        handlers.append((priority, handler))
        handlers.sort(key=lambda x: -x[0])

    def unsubscribe(self, event_type: GameEvent, handler: Handler) -> None:
        """取消订阅。"""
        self._handlers[event_type] = [
            (p, h) for (p, h) in self._handlers[event_type] if h is not handler
        ]

    # ==================================================================
    # 发布
    # ==================================================================

    def publish(self, event: Event) -> None:
        """同步发布：立即通知所有订阅者（按优先级顺序）。"""
        self._record(event)
        for _, handler in self._handlers.get(event.type, []):
            try:
                handler(event)
            except Exception as e:
                print(f"[EventBus] 处理器异常 ({event.type.name}): {e}")

    def publish_async(self, event: Event) -> None:
        """异步发布：事件进入队列，下一帧 flush_async() 时执行。线程安全。"""
        with self._pending_lock:
            self._pending.append(event)

    def flush_async(self) -> None:
        """处理所有待执行的异步事件。线程安全。"""
        with self._pending_lock:
            pending = self._pending[:]
            self._pending.clear()
        for event in pending:
            self.publish(event)

    # ==================================================================
    # 日志
    # ==================================================================

    def _record(self, event: Event) -> None:
        self._publish_count[event.type] += 1
        self._log.append(event)
        if len(self._log) > self._max_log:
            self._log = self._log[-self._max_log:]

    def get_log(
        self, event_type: GameEvent | None = None, limit: int = 50,
    ) -> list[Event]:
        """获取事件日志，可按类型过滤。"""
        if event_type is not None:
            return [e for e in self._log if e.type == event_type][-limit:]
        return self._log[-limit:]

    def get_stats(self) -> dict:
        """返回事件统计。"""
        total = sum(self._publish_count.values())
        with self._pending_lock:
            pending_count = len(self._pending)
        return {
            "total_events": total,
            "pending": pending_count,
            "log_size": len(self._log),
            "handler_count": sum(len(v) for v in self._handlers.values()),
            "by_type": {e.name: c for e, c in self._publish_count.items()},
        }
