"""
==============================================================================
飞机大战 — 玩家成长系统（⭐ 永久升级 · 可持续成长）
==============================================================================
功能：
  1. 击杀敌机获得经验值（XP），累积升级
  2. 每升一级获得 1 个强化点数
  3. 六种强化方向，自由分配点数
  4. 数据持久化到 JSON 文件，跨会话保留

强化方向：
  ┌──────────────┬──────────┬──────────────────────────┐
  │ 强化名称     │ 每级效果 │ 说明                     │
  ├──────────────┼──────────┼──────────────────────────┤
  │ ❤️ 生命强化  │ HP +1   │ 最大生命值增加           │
  │ ⚡ 火力提升  │ 伤害 +1  │ 每颗子弹伤害增加         │
  │ 🔥 蓄力加速  │ ×0.92   │ 蓄力充满时间缩短         │
  │ 💨 机动增强  │ 移速 +1  │ 基础移动速度增加         │
  │ 🌊 弹幕扩散  │ +1弹    │ 蓄力额外增加一枚子弹     │
  │ 🛡️ 护盾精通  │ 无敌延长 │ 受伤无敌时间 +0.3秒     │
  └──────────────┴──────────┴──────────────────────────┘
"""

import os
import json
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    XP_LEVEL_BASE, XP_LEVEL_SCALE, XP_LEVEL_MAX,
    UPGRADE_MAX_LEVEL, UPGRADE_POINTS_PER_LEVEL,
    PLAYER_SPEED, PLAYER_MAX_HP, PLAYER_CHARGE_TIME,
    PLAYER_BULLET_DAMAGE, PLAYER_INVINCIBLE_TIME,
    UI_FONT_PATH,
    BLACK, WHITE, RED, GREEN, YELLOW, CYAN, ORANGE,
    DARK_GRAY, GRAY,
)


# ==========================================================================
# 强化定义
# ==========================================================================

UPGRADE_DEFS: list[dict] = [
    {
        "id": "hp",
        "name": "❤️ 生命强化",
        "desc": "最大生命值 +1",
        "max_level": UPGRADE_MAX_LEVEL,
        "icon": "❤️",
        "color": (255, 60, 60),
    },
    {
        "id": "damage",
        "name": "⚡ 火力提升",
        "desc": "子弹伤害 +1",
        "max_level": UPGRADE_MAX_LEVEL,
        "icon": "⚡",
        "color": (255, 200, 50),
    },
    {
        "id": "charge_speed",
        "name": "🔥 蓄力加速",
        "desc": "蓄力时间 ×0.92",
        "max_level": UPGRADE_MAX_LEVEL,
        "icon": "🔥",
        "color": (255, 120, 30),
    },
    {
        "id": "speed",
        "name": "💨 机动增强",
        "desc": "移动速度 +1",
        "max_level": UPGRADE_MAX_LEVEL,
        "icon": "💨",
        "color": (80, 200, 255),
    },
    {
        "id": "spread",
        "name": "🌊 弹幕扩散",
        "desc": "蓄力额外 +1 弹",
        "max_level": 3,
        "icon": "🌊",
        "color": (80, 255, 180),
    },
    {
        "id": "shield",
        "name": "🛡️ 护盾精通",
        "desc": "无敌时间 +0.3秒",
        "max_level": UPGRADE_MAX_LEVEL,
        "icon": "🛡️",
        "color": (100, 150, 255),
    },
]


# ==========================================================================
# 等级与经验计算
# ==========================================================================

def xp_for_level(level: int) -> int:
    """升到下一级所需总经验"""
    return XP_LEVEL_BASE + (level - 1) * XP_LEVEL_SCALE


def calc_level(total_xp: int) -> tuple[int, int, int]:
    """
    由累计经验计算当前等级、溢出经验、下一级所需。
    返回 (level, current_xp, next_xp)
    """
    level = 1
    xp_needed = xp_for_level(level)
    while total_xp >= xp_needed and level < XP_LEVEL_MAX:
        total_xp -= xp_needed
        level += 1
        xp_needed = xp_for_level(level)
    return level, total_xp, xp_needed


# ==========================================================================
# 玩家升级数据
# ==========================================================================

class PlayerUpgradeData:
    """
    玩家成长数据（可序列化为 JSON）。
    """

    def __init__(self):
        # 累计经验值
        self.total_xp: int = 0
        # 当前等级 (从 calc_level 计算得出)
        self.level: int = 1
        # 当前等级内经验进度
        self.current_xp: int = 0
        # 升到下一级所需
        self.next_xp: int = XP_LEVEL_BASE
        # 可用强化点数
        self.points: int = 0
        # 已购强化: { "hp": 2, "damage": 1, ... }
        self.upgrades: dict[str, int] = {}
        # 总游戏次数
        self.total_plays: int = 0

    def add_xp(self, amount: int) -> int:
        """
        增加经验值，返回新获得的等级数（用于判断是否获得新点数）。
        """
        old_level = self.level
        self.total_xp += amount
        self.level, self.current_xp, self.next_xp = calc_level(self.total_xp)
        gained = self.level - old_level
        self.points += gained * UPGRADE_POINTS_PER_LEVEL
        if self.points < 0:
            self.points = 0
        return gained

    def get_upgrade_level(self, upgrade_id: str) -> int:
        return self.upgrades.get(upgrade_id, 0)

    def can_upgrade(self, upgrade_id: str) -> bool:
        if self.points <= 0:
            return False
        for d in UPGRADE_DEFS:
            if d["id"] == upgrade_id:
                return self.upgrades.get(upgrade_id, 0) < d["max_level"]
        return False

    def apply_upgrade(self, upgrade_id: str) -> bool:
        """花费 1 点强化指定属性。成功返回 True。"""
        if not self.can_upgrade(upgrade_id):
            return False
        self.points -= 1
        self.upgrades[upgrade_id] = self.upgrades.get(upgrade_id, 0) + 1
        return True

    def get_levels_for_display(self) -> list[dict]:
        """返回所有强化项及其当前等级信息（供 UI 渲染）。"""
        result = []
        for d in UPGRADE_DEFS:
            current = self.upgrades.get(d["id"], 0)
            result.append({
                "id": d["id"],
                "name": d["name"],
                "desc": d["desc"],
                "current": current,
                "max": d["max_level"],
                "color": d["color"],
            })
        return result

    # ---- 序列化 ----

    def to_dict(self) -> dict:
        return {
            "total_xp": self.total_xp,
            "upgrades": dict(self.upgrades),
            "total_plays": self.total_plays,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlayerUpgradeData":
        obj = cls()
        obj.total_xp = data.get("total_xp", 0)
        obj.upgrades = dict(data.get("upgrades", {}))
        obj.total_plays = data.get("total_plays", 0)
        obj.level, obj.current_xp, obj.next_xp = calc_level(obj.total_xp)
        # 重算可用点数
        total_gained = 0
        for lv in range(1, obj.level):
            total_gained += UPGRADE_POINTS_PER_LEVEL
        spent = sum(obj.upgrades.values())
        obj.points = total_gained - spent
        if obj.points < 0:
            obj.points = 0
        return obj


# ==========================================================================
# 持久化
# ==========================================================================

_SAVE_PATH: str = "assets/player_upgrades.json"


def load_upgrades() -> PlayerUpgradeData:
    """从 JSON 文件加载升级数据。文件不存在则返回默认数据。"""
    try:
        with open(_SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return PlayerUpgradeData.from_dict(data)
    except (FileNotFoundError, json.JSONDecodeError, Exception):
        return PlayerUpgradeData()


def save_upgrades(data: PlayerUpgradeData) -> None:
    """保存升级数据到 JSON 文件。"""
    try:
        with open(_SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data.to_dict(), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Upgrade] 保存失败: {e}")


# ==========================================================================
# 属性计算（将升级数据转化为游戏属性加成）
# ==========================================================================

def apply_upgrades_to_player(player, upgrades: PlayerUpgradeData) -> None:
    """
    根据升级数据修改玩家实体的基础属性。
    在 Player.reset() 或新游戏开始时调用。
    """
    lv_hp = upgrades.get_upgrade_level("hp")
    lv_damage = upgrades.get_upgrade_level("damage")
    lv_charge = upgrades.get_upgrade_level("charge_speed")
    lv_speed = upgrades.get_upgrade_level("speed")
    lv_shield = upgrades.get_upgrade_level("shield")

    # 生命强化
    player.max_hp = PLAYER_MAX_HP + lv_hp
    player.hp = player.max_hp

    # 火力提升
    player._extra_damage = lv_damage

    # 蓄力加速
    if lv_charge > 0:
        player._charge_time = PLAYER_CHARGE_TIME * (0.92 ** lv_charge)
    else:
        player._charge_time = PLAYER_CHARGE_TIME

    # 机动增强
    player.base_speed = PLAYER_SPEED + lv_speed

    # 护盾精通
    if lv_shield > 0:
        player._invincible_duration = PLAYER_INVINCIBLE_TIME + lv_shield * 0.3
    else:
        player._invincible_duration = PLAYER_INVINCIBLE_TIME

    # 弹幕扩散（在 player.fire() 中使用）
    player._spread_upgrade = upgrades.get_upgrade_level("spread")


# ==========================================================================
# 升级界面 UI（内联渲染，无需额外资源）
# ==========================================================================

def render_upgrade_screen(
    screen: pygame.Surface,
    data: PlayerUpgradeData,
    selected_index: int,
    show_level_up: bool,
    level_up_count: int,
) -> None:
    """
    绘制升级加点界面。
    在 Game.state == UPGRADE 时调用。
    """
    screen.fill((10, 10, 20))

    try:
        title_font = pygame.font.Font(UI_FONT_PATH, 36)
        header_font = pygame.font.Font(UI_FONT_PATH, 22)
        item_font = pygame.font.Font(UI_FONT_PATH, 18)
        small_font = pygame.font.Font(UI_FONT_PATH, 14)
    except Exception:
        title_font = pygame.font.Font(None, 36)
        header_font = pygame.font.Font(None, 22)
        item_font = pygame.font.Font(None, 18)
        small_font = pygame.font.Font(None, 14)

    # ---- 标题 ----
    title = title_font.render("🚀 机 体 强 化", True, CYAN)
    title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 45))
    screen.blit(title, title_rect)

    # ---- 等级 / 经验 / 点数 ----
    header_y = 85
    level_text = header_font.render(
        f"Lv.{data.level}   经验 {data.current_xp}/{data.next_xp}   可用点数 [ {data.points} ]",
        True, WHITE
    )
    level_rect = level_text.get_rect(center=(SCREEN_WIDTH // 2, header_y))
    screen.blit(level_text, level_rect)

    # 经验条
    bar_x, bar_y = SCREEN_WIDTH // 2 - 150, header_y + 30
    bar_w, bar_h = 300, 8
    pygame.draw.rect(screen, DARK_GRAY, (bar_x, bar_y, bar_w, bar_h))
    if data.next_xp > 0:
        fill = int(bar_w * data.current_xp / data.next_xp)
        pygame.draw.rect(screen, CYAN, (bar_x, bar_y, fill, bar_h))

    # ---- 升级提示 ----
    if show_level_up and level_up_count > 0:
        glow = (255, 255, 100) if int(pygame.time.get_ticks() / 300) % 2 == 0 else YELLOW
        lvup = header_font.render(f"⬆  升级 × {level_up_count} ！", True, glow)
        lvup_rect = lvup.get_rect(center=(SCREEN_WIDTH // 2, header_y + 55))
        screen.blit(lvup, lvup_rect)

    # ---- 强化列表 ----
    items = data.get_levels_for_display()
    start_y = header_y + 85 if show_level_up and level_up_count > 0 else header_y + 70
    item_h = 58
    item_w = 360
    total_h = len(items) * item_h + 10
    list_x = (SCREEN_WIDTH - item_w) // 2
    list_y = start_y

    for i, item in enumerate(items):
        y = list_y + i * item_h
        is_selected = (i == selected_index)
        can_up = data.can_upgrade(item["id"])

        # 背景
        if is_selected:
            bg_color = (40, 50, 80) if can_up else (30, 30, 50)
            border_color = CYAN if can_up else GRAY
        else:
            bg_color = (20, 22, 35) if can_up else (15, 15, 25)
            border_color = (40, 40, 60)

        pygame.draw.rect(screen, bg_color, (list_x, y, item_w, item_h))
        pygame.draw.rect(screen, border_color, (list_x, y, item_w, item_h), width=1)

        # 名称
        name_color = item["color"] if can_up else GRAY
        name = item_font.render(item["name"], True, name_color)
        screen.blit(name, (list_x + 12, y + 6))

        # 等级条
        dot_size = 10
        dot_gap = 4
        dots_start_x = list_x + 120
        dots_y = y + 10
        for d in range(item["max"]):
            dx = dots_start_x + d * (dot_size + dot_gap)
            if d < item["current"]:
                pygame.draw.rect(screen, item["color"], (dx, dots_y, dot_size, dot_size))
            else:
                pygame.draw.rect(screen, (40, 40, 50), (dx, dots_y, dot_size, dot_size))

        # 等级数字
        lv_label = small_font.render(f"{item['current']}/{item['max']}", True, GRAY)
        screen.blit(lv_label, (dots_start_x + item["max"] * (dot_size + dot_gap) + 4, dots_y - 1))

        # 描述
        desc = small_font.render(item["desc"], True, (140, 140, 160))
        screen.blit(desc, (list_x + 12, y + 30))

        # 选中标记
        if is_selected:
            if can_up:
                arrow = header_font.render("◄", True, CYAN)
                screen.blit(arrow, (list_x - 26, y + 12))
            else:
                max_text = small_font.render("已满级", True, GRAY)
                screen.blit(max_text, (list_x + item_w - 56, y + 18))

    # ---- 底部操作提示 ----
    hint_y = SCREEN_HEIGHT - 50
    hints = [
        "↑↓ 选择    空格/Enter 加点    ESC 返回菜单",
        "强化永久保留 · 继续战斗获得更多经验"
    ]
    for hi, hint in enumerate(hints):
        h = small_font.render(hint, True, (100, 100, 130))
        hr = h.get_rect(center=(SCREEN_WIDTH // 2, hint_y + hi * 18))
        screen.blit(h, hr)

    # ---- 属性总览（右侧面板） ----
    # 在右侧显示当前综合属性
    panel_x = list_x + item_w + 20
    panel_y = start_y
    stats = [
        f"❤️ HP: {PLAYER_MAX_HP + data.get_upgrade_level('hp')}",
        f"⚡ 伤害: {PLAYER_BULLET_DAMAGE + data.get_upgrade_level('damage')}",
        f"🔥 蓄力: {PLAYER_CHARGE_TIME * (0.92 ** data.get_upgrade_level('charge_speed')):.2f}s",
        f"💨 速度: {PLAYER_SPEED + data.get_upgrade_level('speed')}",
        f"🌊 弹幕: +{data.get_upgrade_level('spread')}",
        f"🛡️ 无敌: {PLAYER_INVINCIBLE_TIME + data.get_upgrade_level('shield') * 0.3:.1f}s",
    ]
    for si, stat in enumerate(stats):
        s = small_font.render(stat, True, (160, 170, 190))
        screen.blit(s, (panel_x, panel_y + si * 20))
