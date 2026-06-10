"""
==============================================================================
飞机大战 — 排行榜系统（题16：JSON 数据持久化）
==============================================================================
使用 json 模块实现本地 Top 5 排行榜持久化。

功能：
  - 保存/加载 Top 5 成绩（玩家姓名 + 分数 + 日期）
  - 检查分数是否可上榜
  - 添加新记录并自动排序截断
  - JSON 文件缺失/损坏/权限异常 → 降级为空榜

文件路径：project/assets/leaderboard.json
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LeaderboardEntry:
    """单条排行记录"""
    name: str
    score: int
    date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))

    def to_dict(self) -> dict:
        return {"name": self.name, "score": self.score, "date": self.date}

    @classmethod
    def from_dict(cls, d: dict) -> "LeaderboardEntry":
        return cls(
            name=d.get("name", "???"),
            score=d.get("score", 0),
            date=d.get("date", ""),
        )


class Leaderboard:
    """
    Top 5 排行榜（JSON 持久化）。

    用法：
        lb = Leaderboard()
        if lb.is_high_score(850):
            lb.add_score("玩家名", 850)
        for entry in lb.entries:
            print(f"{entry.name}: {entry.score}")
    """

    MAX_ENTRIES: int = 5

    def __init__(self, filepath: str | None = None) -> None:
        if filepath is None:
            filepath = os.path.join(
                os.path.dirname(__file__), "..", "assets", "leaderboard.json"
            )
        self._filepath: str = os.path.normpath(filepath)
        self._entries: list[LeaderboardEntry] = []
        self._load()

    # ================================================================
    # 公共接口
    # ================================================================

    @property
    def entries(self) -> list[LeaderboardEntry]:
        """返回按分数降序排列的记录列表。"""
        return list(self._entries)

    def is_high_score(self, score: int) -> bool:
        """
        判断分数是否有资格上榜。

        条件：
          1. 分数 > 0
          2. 排行榜未满 5 人，或分数高于最低记录
        """
        if score <= 0:
            return False
        if len(self._entries) < self.MAX_ENTRIES:
            return True
        return score > self._entries[-1].score

    def add_score(self, name: str, score: int) -> LeaderboardEntry | None:
        """
        添加新记录，保持 Top 5 降序排列，自动保存。

        返回值：
            新创建的 LeaderboardEntry（上榜成功）
            None（分数不足以上榜）
        """
        if not self.is_high_score(score):
            return None

        entry = LeaderboardEntry(name=name.strip() or "无名", score=score)
        self._entries.append(entry)
        self._entries.sort(key=lambda e: e.score, reverse=True)
        if len(self._entries) > self.MAX_ENTRIES:
            self._entries.pop()
        self._save()
        return entry

    # ================================================================
    # JSON 持久化
    # ================================================================

    def _load(self) -> None:
        """
        从 JSON 文件加载排行榜。

        异常处理：
          - 文件不存在 → 初始化为空列表（首次运行）
          - JSON 格式错误 → 打印警告，初始化为空列表
          - 权限/IO 错误 → 打印警告，初始化为空列表
        """
        try:
            if not os.path.exists(self._filepath):
                return
            with open(self._filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                print(f"[Leaderboard] 文件格式异常，已重置")
                return
            self._entries = [
                LeaderboardEntry.from_dict(item)
                for item in data
                if isinstance(item, dict)
            ]
            self._entries.sort(key=lambda e: e.score, reverse=True)
            if len(self._entries) > self.MAX_ENTRIES:
                self._entries = self._entries[:self.MAX_ENTRIES]
        except FileNotFoundError:
            pass
        except json.JSONDecodeError as e:
            print(f"[Leaderboard] JSON 解析失败: {e}，已重置为空白榜")
        except (PermissionError, OSError) as e:
            print(f"[Leaderboard] 文件读取失败: {e}")

    def _save(self) -> None:
        """
        将排行榜写入 JSON 文件。

        异常处理：
          - 权限/磁盘满/IO 错误 → 打印警告，游戏继续运行
        """
        try:
            os.makedirs(os.path.dirname(self._filepath), exist_ok=True)
            data = [e.to_dict() for e in self._entries]
            with open(self._filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except (PermissionError, OSError) as e:
            print(f"[Leaderboard] 保存失败: {e}")
