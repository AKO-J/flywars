"""
==============================================================================
飞机大战 — 结构化日志系统（题6）
==============================================================================
GameLogger 单例：分级日志 + JSON 文件输出 + 内存环形缓冲（~键面板）。

用法：
  log = GameLogger.get_instance()
  log.info("游戏开始", score=0, level=1)
  log.warning("低血量", hp=1)
  log.error("配置加载失败", path="user.json")
==============================================================================
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class LogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


@dataclass
class LogEntry:
    """单条日志记录。"""
    timestamp: float = field(default_factory=time.time)
    level: LogLevel = LogLevel.INFO
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "ts": self.timestamp,
            "level": self.level.name,
            "msg": self.message,
            **self.data,
        }, ensure_ascii=False)

    def format_onscreen(self, max_msg: int = 80) -> str:
        t = time.strftime("%H:%M:%S", time.localtime(self.timestamp))
        tag = f"[{self.level.name[:4]}]"
        tail = f" | {self.data}" if self.data else ""
        msg = self.message[:max_msg]
        return f"{t} {tag:8s} {msg}{tail}"


class GameLogger:
    """结构化日志单例。"""

    _instance: GameLogger | None = None

    def __init__(self, log_dir: str = "logs") -> None:
        self._log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._configure_console_encoding()

        # JSON 文件
        self._file_path = os.path.join(
            log_dir, f"game_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
        )
        self._file = open(self._file_path, "w", encoding="utf-8")

        # 环形缓冲（~键面板显示用，保留最近 N 条）
        self._buffer: deque[LogEntry] = deque(maxlen=200)
        # 面板开关
        self._panel_visible: bool = False

        # 统计
        self._counts: dict[LogLevel, int] = {lv: 0 for lv in LogLevel}

    @classmethod
    def get_instance(cls) -> "GameLogger":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ==================================================================
    # 公共 API
    # ==================================================================

    def debug(self, msg: str, **data: Any) -> None:
        self._log(LogLevel.DEBUG, msg, data)

    def info(self, msg: str, **data: Any) -> None:
        self._log(LogLevel.INFO, msg, data)

    def warning(self, msg: str, **data: Any) -> None:
        self._log(LogLevel.WARNING, msg, data)

    def error(self, msg: str, **data: Any) -> None:
        self._log(LogLevel.ERROR, msg, data)

    def critical(self, msg: str, **data: Any) -> None:
        self._log(LogLevel.CRITICAL, msg, data)

    # ==================================================================
    # 内部
    # ==================================================================
    def _configure_console_encoding(self) -> None:
        """在 Windows 终端强制使用 UTF-8，避免中文乱码。"""
        if sys.platform != "win32":
            return
        for stream in (sys.stdout, sys.stderr):
            if stream is None:
                continue
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is None:
                continue
            encoding = getattr(stream, "encoding", None)
            if encoding and encoding.lower() == "utf-8":
                continue
            reconfigure(encoding="utf-8", errors="replace")

    def _log(self, level: LogLevel, msg: str, data: dict[str, Any]) -> None:
        entry = LogEntry(level=level, message=msg, data=data)
        self._counts[level] += 1
        self._buffer.append(entry)

        # JSON 行写入文件
        self._file.write(entry.to_json() + "\n")
        self._file.flush()

        # 控制台同步输出
        print(f"[{level.name:8s}] {msg} {data if data else ''}".strip())

    # ==================================================================
    # ~ 面板
    # ==================================================================

    def toggle_panel(self) -> None:
        self._panel_visible = not self._panel_visible

    @property
    def panel_visible(self) -> bool:
        return self._panel_visible

    def get_recent(self, count: int = 30) -> list[LogEntry]:
        items = list(self._buffer)
        return items[-count:]

    def get_stats(self) -> dict:
        total = sum(self._counts.values())
        return {
            "total": total,
            "by_level": {lv.name: c for lv, c in self._counts.items()},
            "buffer_size": len(self._buffer),
            "log_file": self._file_path,
        }

    # ==================================================================
    # 清理
    # ==================================================================

    def close(self) -> None:
        self._file.close()
