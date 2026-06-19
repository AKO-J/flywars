"""
==============================================================================
AI 自动驾驶 + 测试闭环系统
==============================================================================
每帧读取游戏状态 → 决策（躲避/攻击/拾取）→ 驱动玩家。
详细日志输出到文件，跑完后可读报告分析问题。
"""

import math
import random
import time
from dataclasses import dataclass, field


@dataclass
class AIState:
    player_x: float = 0.0
    player_y: float = 0.0
    player_hp: int = 8
    player_max_hp: int = 8
    player_xp: int = 0          # ⭐ 当前经验
    player_xp_next: int = 100   # ⭐ 升级所需
    player_w: int = 32
    player_h: int = 32
    screen_w: int = 600
    screen_h: int = 800
    enemies: list = field(default_factory=list)
    enemy_bullets: list = field(default_factory=list)
    powerups: list = field(default_factory=list)
    boss_active: bool = False
    boss_x: float = 0.0
    boss_y: float = 0.0
    boss_hp_pct: float = 0.0   # Boss HP 百分比
    level: int = 1
    score: int = 0
    combo: int = 0
    kills_this_frame: int = 0


class AIPlayer:
    """AI 自动驾驶 + 测试报告。"""

    def __init__(self, log_file: str = "ai_test_log.txt"):
        self._f = open(log_file, "w", encoding="utf-8")
        self._t0 = time.time()
        self._last_level = 1
        self._deaths = 0
        self._kills = 0
        self._max_combo = 0
        self._boss_seen = False
        self._boss_killed = False
        self._max_level = 1
        self._level_times: dict[int, float] = {}
        self._level_hp: dict[int, int] = {}
        self._level_start = time.time()
        self._px, self._py = 0.0, 0.0  # ⭐ 玩家位置缓存
        self._log("START", "AI 自动驾驶测试开始")
        self._log("CONFIG", "HP=8 无敌=2s 升关回血 波间0.6s")

    # ── 公开 API ──

    def log(self, tag: str, msg: str = ""):
        t = time.time() - self._t0
        line = f"[{t:5.0f}s] {tag:8s} {msg}"
        print(line)
        self._f.write(line + "\n")
        self._f.flush()

    def _log(self, tag: str, msg: str = ""):
        self.log(tag, msg)

    def elapsed(self) -> float:
        return time.time() - self._t0

    def update(self, s: AIState) -> dict:
        """每帧决策：返回动作字典。"""
        # 关卡变化
        if s.level != self._last_level:
            now = time.time()
            if self._last_level in self._level_times:
                pass
            self._level_times[self._last_level] = now - self._level_start
            self._level_hp[self._last_level] = s.player_hp
            self._log("LEVEL", f"{self._last_level}→{s.level}  HP={s.player_hp}/{s.player_max_hp}  得分={s.score}  击杀={self._kills}")
            self._last_level = s.level
            self._max_level = max(self._max_level, s.level)
            self._level_start = now

        self._kills += s.kills_this_frame
        self._max_combo = max(self._max_combo, s.combo)

        # Boss 状态
        if s.boss_active and not self._boss_seen:
            self._boss_seen = True
            self._log("BOSS", f"出现！HP={s.boss_hp_pct:.0%}")
        if self._boss_seen and not s.boss_active and not self._boss_killed and s.level == self._last_level:
            self._boss_killed = True
            self._log("BOSS", "击败！")

        a = {"move_left": False, "move_right": False,
             "move_up": False, "move_down": False,
             "shoot": False, "charge": False}

        px, py = s.player_x, s.player_y
        self._px, self._py = px, py  # ⭐ 保存给 _nearest 系列方法用

        # 1. 躲避子弹
        threat = self._nearest_threat(s)
        dvx, dvy = 0.0, 0.0
        if threat:
            tx, ty, tvx, tvy = threat
            if abs(px - tx) < 120 and abs(py - ty) < 200:
                spd = (tvx**2 + tvy**2)**0.5
                if spd > 0:
                    perp = (-tvy / spd, tvx / spd)
                    sign = 1 if px < s.screen_w / 2 else -1
                    dvx, dvy = sign * abs(perp[0]), perp[1]

        # 2. 攻击敌机
        near = self._nearest(s.enemies)
        avx, avy = 0.0, 0.0
        if near and not s.boss_active:
            dx, dy = near[0] - px, near[1] - py
            d = max((dx**2 + dy**2)**0.5, 1)
            avx, avy = dx / d, dy / d * 0.4

        # 3. Boss 战 — ⭐ 不站正下方，躲侧边持续输出
        if s.boss_active:
            bx = s.boss_x
            # 保持偏左或偏右（不在 Boss 正下方吃弹幕）
            prefer_left = (bx > s.screen_w / 2)  # Boss在右边就站左边
            target_x = 80 if prefer_left else s.screen_w - 80
            dx = target_x - px
            avx = (1.0 if dx > 0 else -1.0) if abs(dx) > 30 else 0
            # 保持下 1/3 位置，不要靠 Boss 太近
            target_y = s.screen_h * 0.65
            dy = target_y - py
            avy = (0.5 if dy > 0 else -0.5) if abs(dy) > 20 else 0
            # 加强躲避
            dvx *= 2.0; dvy *= 2.0
            a["shoot"] = True

        # 4. 拾取
        cvx, cvy = 0.0, 0.0
        pu = self._nearest_pos(s.powerups)
        if pu:
            dx, dy = pu[0] - px, pu[1] - py
            d = max((dx**2 + dy**2)**0.5, 1)
            if d < 250:
                cvx, cvy = dx / d * 0.6, dy / d * 0.6

        # 5. 合并
        vx = dvx * 0.5 + cvx * 0.3 + avx * 0.2
        vy = dvy * 0.5 + cvy * 0.3 + avy * 0.2
        if abs(vx) > 0.15: a["move_left"], a["move_right"] = vx < 0, vx > 0
        if abs(vy) > 0.08: a["move_up"], a["move_down"] = vy < 0, vy > 0

        if not s.boss_active:
            a["shoot"] = near is not None
        return a

    def _nearest_threat(self, s):
        best, bd = None, float("inf")
        for bx, by, bvx, bvy in s.enemy_bullets:
            if (bvx * (s.player_x - bx) + bvy * (s.player_y - by)) <= 0:
                continue
            d = (s.player_x - bx)**2 + (s.player_y - by)**2
            if d < bd and d < 40000:
                bd, best = d, (bx, by, bvx, bvy)
        return best

    def _nearest(self, items):
        best, bd = None, float("inf")
        for it in items:
            d = (it[0] - self._px)**2 + (it[1] - self._py)**2
            if d < bd:
                bd, best = d, it
        return best

    def _nearest_pos(self, items):
        best, bd = None, float("inf")
        for it in items:
            d = (it[0] - self._px)**2 + (it[1] - self._py)**2
            if d < bd:
                bd, best = d, it
        return best

    def on_death(self):
        self._deaths += 1
        self._log("DEATH", f"#{self._deaths}  重开中...")

    def on_restart(self):
        self._last_level = 1
        self._level_start = time.time()

    def report(self) -> str:
        """生成完整测试报告。"""
        t = time.time() - self._t0
        lines = [
            "",
            "=" * 50,
            "  AI 自动驾驶测试报告",
            "=" * 50,
            f"  总耗时:     {t:5.1f}s",
            f"  到达关卡:   {self._max_level}",
            f"  死亡次数:   {self._deaths}",
            f"  击杀数:     {self._kills}",
            f"  最高连击:   {self._max_combo}",
            f"  Boss出现:   {'是' if self._boss_seen else '否'}",
            f"  Boss击败:   {'是' if self._boss_killed else '否'}",
            "",
            "  各关详情:",
        ]
        for lv in sorted(self._level_times):
            dt = self._level_times[lv]
            hp = self._level_hp.get(lv, 0)
            bar = "=" * max(1, min(40, int(dt * 2)))
            lines.append(f"    Lv{lv}: {dt:5.1f}s {bar} HP={hp}")
        lines.append("=" * 50)
        report = "\n".join(lines)
        self._log("REPORT", report.replace("\n", "\n              "))
        return report

    def close(self):
        self._log("END", self.report().replace("\n", "\n  "))
        self._f.close()
