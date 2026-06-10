"""
==============================================================================
飞机大战 — UI 系统（题12：生命值、分数与关卡显示）
==============================================================================
统一 HUD 渲染 + 飘字得分动画 + 关卡提升提示。

设计：
  - FloatingText: 分值飘字，上浮渐隐，dt 驱动
  - UISystem: 管理所有 UI 元素（HP条、分数、关卡、敌机统计、飘字、升级提示）
  - 关卡 = score // 500 + 1，升级时屏幕中央闪现提示
  - 完全使用 pygame.font 渲染，与现有精灵系统解耦
"""

from dataclasses import dataclass
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT,
    FLOATING_TEXT_SPEED, FLOATING_TEXT_LIFETIME,
    LEVEL_SCORE_BASE, LEVEL_UP_DISPLAY_TIME,
    POWERUP_DURATION, POWERUP_COLORS,
    UI_FONT_PATH,
    WHITE, YELLOW, GREEN, CYAN, GRAY, RED, ORANGE, BLACK,
    PowerUpType,
)
from sprites.player import Player


# ==========================================================================
# 飘字得分
# ==========================================================================

@dataclass
class FloatingText:
    """单条飘字：从敌机销毁位置向上浮动并渐隐。"""
    text: str
    x: float
    y: float
    alpha: int = 255
    lifetime: float = FLOATING_TEXT_LIFETIME
    _initial_lifetime: float = FLOATING_TEXT_LIFETIME
    color: tuple = WHITE  # 自定义颜色（道具拾取）

    def update(self, dt: float) -> bool:
        """返回 True 表示还活着，False 表示应移除。"""
        self.y -= FLOATING_TEXT_SPEED * dt
        self.lifetime -= dt
        if self.lifetime <= 0:
            return False
        ratio = self.lifetime / self._initial_lifetime
        # 前 70% 时间保持不透明，后 30% 渐隐
        if ratio < 0.3:
            self.alpha = int(255 * (ratio / 0.3))
        else:
            self.alpha = 255
        return True


# ==========================================================================
# UI 系统
# ==========================================================================

class UISystem:
    """
    集中式 UI 渲染器。
    ————————————————————————————————
    每帧调用 update(dt, score) → render(screen, ...)
    """

    def __init__(self) -> None:
        # 飘字列表
        self.floating_texts: list[FloatingText] = []

        # 关卡
        self._current_level: int = 1
        self._level_up_timer: float = 0.0

        # 道具指示器字体
        self._font_powerup = pygame.font.Font(UI_FONT_PATH, 16)
        # 炸弹闪屏 alpha
        self._bomb_flash_alpha: int = 0
        # F5 配置重载提示计时器
        self._config_flash_timer: float = 0.0
        self._config_flash_msg: str = ""
        # 字体（不同尺寸复用同一字体对象）
        self._font_small = pygame.font.Font(UI_FONT_PATH, 18)
        self._font_normal = pygame.font.Font(UI_FONT_PATH, 22)
        self._font_score = pygame.font.Font(UI_FONT_PATH, 26)
        self._font_big = pygame.font.Font(UI_FONT_PATH, 48)

    # ================================================================
    # 公共接口
    # ================================================================

    def add_score_text(self, x: float, y: float, score_value: int) -> None:
        """在指定位置创建飘字得分。"""
        self.floating_texts.append(
            FloatingText(f"+{score_value}", float(x), float(y))
        )

    def add_pickup_text(self, x: float, y: float, label: str, color: tuple) -> None:
        """在指定位置创建道具拾取飘字（带颜色，更大字号）。"""
        self.floating_texts.append(
            FloatingText(label, float(x), float(y), color=color,
                        lifetime=FLOATING_TEXT_LIFETIME * 1.5)
        )

    def update(self, dt: float, score: int) -> None:
        """更新飘字动画并检测关卡提升。"""
        # 移除已完成的飘字
        self.floating_texts = [
            ft for ft in self.floating_texts if ft.update(dt)
        ]

        # 关卡检测
        new_level: int = score // LEVEL_SCORE_BASE + 1
        if new_level > self._current_level:
            self._current_level = new_level
            self._level_up_timer = LEVEL_UP_DISPLAY_TIME

        # 关卡提示计时器
        if self._level_up_timer > 0:
            self._level_up_timer -= dt
            if self._level_up_timer < 0:
                self._level_up_timer = 0.0
        # 炸弹闪屏渐隐
        if self._bomb_flash_alpha > 0:
            self._bomb_flash_alpha = max(0, self._bomb_flash_alpha - int(dt * 600))
            if self._bomb_flash_alpha < 0:
                self._bomb_flash_alpha = 0
        # 配置重载提示计时器
        if self._config_flash_timer > 0:
            self._config_flash_timer -= dt
            if self._config_flash_timer < 0:
                self._config_flash_timer = 0.0

    def trigger_bomb_flash(self) -> None:
        self._bomb_flash_alpha = 200

    def trigger_config_flash(self, msg: str) -> None:
        """F5 热重载提示（屏幕中央短暂闪现）。"""
        self._config_flash_timer = 1.5
        self._config_flash_msg = msg

    def render(
        self,
        screen: pygame.Surface,
        player: Player,
        score: int,
        enemy_count: int,
        spawner_counts: dict[str, int],
        network_status: str = "",
        network_color: tuple[int, int, int] = RED,
    ) -> None:
        """绘制全部 UI 层（HUD → 道具指示器 → 飘字 → 关卡提示 → 炸弹闪屏 → 网络状态）。"""
        self._draw_hud(screen, player, score, enemy_count, spawner_counts)
        self._draw_powerup_indicator(screen, player)
        self._draw_floating_texts(screen)
        self._draw_level_up(screen)
        self._draw_network_status(screen, network_status, network_color)
        self._draw_bomb_flash(screen)
        self._draw_config_flash(screen)

    # ================================================================
    # 道具 Buff 指示器（题18）
    # ================================================================

    _POWERUP_LABELS: dict[PowerUpType, str] = {
        PowerUpType.DOUBLE_DAMAGE: "双倍伤害",
        PowerUpType.TRIPLE_SPREAD: "三向散射",
        PowerUpType.PIERCE: "穿透弹",
        PowerUpType.RAPID_FIRE: "快速蓄力",
    }

    def _draw_powerup_indicator(self, screen: pygame.Surface, player: Player) -> None:
        """在 HUD 下方显示所有激活的道具图标 + 独立倒计时条（支持叠加显示）。"""
        active = player.active_powerups
        if not active:
            return

        x0, base_y = 8, 140
        bar_w, bar_h = 140, 6
        icon_size = 12
        row_h = icon_size + bar_h + 6  # 每行高度

        for i, (ptype, remaining) in enumerate(active.items()):
            label = self._POWERUP_LABELS.get(ptype, "")
            if not label:
                continue
            color = POWERUP_COLORS.get(ptype, WHITE)
            y = base_y + i * row_h

            # 图标方块
            pygame.draw.rect(screen, color, (x0, y, icon_size, icon_size))
            pygame.draw.rect(screen, WHITE, (x0, y, icon_size, icon_size), width=1)

            # 标签文字
            label_surf = self._font_powerup.render(label, True, color)
            screen.blit(label_surf, (x0 + icon_size + 4, y - 1))

            bar_y = y + icon_size + 2
            ratio = remaining / POWERUP_DURATION
            pygame.draw.rect(screen, (30, 30, 30), (x0, bar_y, bar_w, bar_h))
            if ratio > 0:
                if ratio > 0.5:
                    bar_color = GREEN
                elif ratio > 0.25:
                    bar_color = YELLOW
                else:
                    bar_color = RED
                pygame.draw.rect(screen, bar_color, (x0, bar_y, int(bar_w * ratio), bar_h))
            pygame.draw.rect(screen, GRAY, (x0, bar_y, bar_w, bar_h), width=1)

            # 剩余秒数
            sec_text = f"{remaining:.1f}s"
            sec_surf = self._font_powerup.render(sec_text, True, WHITE)
            screen.blit(sec_surf, (x0 + bar_w + 4, bar_y - 1))

    # ================================================================
    # 炸弹闪屏（题18）
    # ================================================================

    def _draw_bomb_flash(self, screen: pygame.Surface) -> None:
        """炸弹清屏时的白色闪屏叠加。"""
        if self._bomb_flash_alpha <= 0:
            return
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((255, 255, 255, self._bomb_flash_alpha))
        screen.blit(overlay, (0, 0))

    def _draw_config_flash(self, screen: pygame.Surface) -> None:
        """F5 配置重载提示（屏幕顶部绿色飘字，渐隐）。"""
        if self._config_flash_timer <= 0:
            return
        alpha = int(255 * min(self._config_flash_timer / 0.5, 1.0))
        font = pygame.font.Font(UI_FONT_PATH, 22)
        surf = font.render(self._config_flash_msg, True, GREEN)
        surf.set_alpha(alpha)
        rect = surf.get_rect(center=(SCREEN_WIDTH // 2, 30))
        screen.blit(surf, rect)

    # ================================================================
    # 网络状态指示器（题9）
    # ================================================================

    def _draw_network_status(
        self,
        screen: pygame.Surface,
        status: str,
        color: tuple[int, int, int],
    ) -> None:
        """底部居中网络连接状态指示器。"""
        if not status:
            return
        # 状态圆点
        dot_r = 5
        font = pygame.font.Font(UI_FONT_PATH, 16)
        status_surf = font.render(status, True, color)
        # 计算总宽度（圆点 + 间距 + 文字）
        total_w = dot_r * 2 + 6 + status_surf.get_width()
        start_x = (SCREEN_WIDTH - total_w) // 2
        base_y = SCREEN_HEIGHT - 20

        # 圆点
        dot_cx = start_x + dot_r
        dot_cy = base_y + dot_r
        pygame.draw.circle(screen, color, (dot_cx, dot_cy), dot_r)
        pygame.draw.circle(screen, (100, 100, 100), (dot_cx, dot_cy), dot_r + 1, width=1)

        # 文字
        screen.blit(status_surf, (start_x + dot_r * 2 + 6, base_y))

    def reset(self) -> None:
        """重置 UI 状态（新游戏时调用）。"""
        self.floating_texts.clear()
        self._current_level = 1
        self._level_up_timer = 0.0
        self._bomb_flash_alpha = 0

    @property
    def current_level(self) -> int:
        return self._current_level

    # ================================================================
    # HUD 绘制
    # ================================================================

    def _draw_hud(
        self,
        screen: pygame.Surface,
        player: Player,
        score: int,
        enemy_count: int,
        tc: dict[str, int],
    ) -> None:
        """左上角 HUD：HP 条 → 蓄力 → 分数 → 关卡 → 敌机统计"""
        x0, y = 8, 8
        gap: int = 5

        # ── 第1行：HP 条 ──
        bar_w, bar_h = 140, 12
        hp_ratio = player.hp / max(player.max_hp, 1)

        # 深色底
        pygame.draw.rect(screen, (25, 25, 25), (x0, y, bar_w, bar_h))
        # 血量填充（颜色随比例变化）
        if hp_ratio > 0.5:
            hp_color = GREEN
        elif hp_ratio > 0.25:
            hp_color = YELLOW
        else:
            hp_color = RED
        if hp_ratio > 0:
            pygame.draw.rect(screen, hp_color, (x0, y, int(bar_w * hp_ratio), bar_h))
        # 边框
        pygame.draw.rect(screen, GRAY, (x0, y, bar_w, bar_h), width=1)
        # HP 数值覆在条上（居中）
        hp_label = self._font_small.render(
            f"HP {player.hp}/{player.max_hp}", True, WHITE
        )
        # 文字在血条右侧
        screen.blit(hp_label, (x0 + bar_w + 6, y - 1))
        y += bar_h + gap

        # ── 第2行：蓄力状态 ──
        charge_pct: int = int(player.charge_level * 100)
        charge_text = self._font_small.render(
            f"蓄力 [SPACE]: {player.charge_name} ({charge_pct}%)",
            True, (200, 200, 200)
        )
        screen.blit(charge_text, (x0, y))
        y += 18

        # ── 第3行：分数 ──
        score_surf = self._font_score.render(f"得分: {score}", True, YELLOW)
        screen.blit(score_surf, (x0, y))
        y += 22

        # ── 第4行：关卡 ──
        level_color = CYAN if self._level_up_timer > 0 else WHITE
        level_surf = self._font_normal.render(
            f"关卡: {self._current_level}", True, level_color
        )
        screen.blit(level_surf, (x0, y))
        y += 20

        # ── 第5行：敌机统计 ──
        enemy_surf = self._font_small.render(
            f"敌机: {enemy_count} | "
            f"普{tc['normal']} 快{tc['fast']} "
            f"精{tc['elite']} 追{tc['tracking']}",
            True, (160, 160, 160)
        )
        screen.blit(enemy_surf, (x0, y))

    # ================================================================
    # 飘字得分
    # ================================================================

    def _draw_floating_texts(self, screen: pygame.Surface) -> None:
        """绘制所有飘字得分（叠加在游戏画面上层）。"""
        font = pygame.font.Font(UI_FONT_PATH, 24)
        for ft in self.floating_texts:
            surf = font.render(ft.text, True, ft.color)
            surf.set_alpha(ft.alpha)
            rect = surf.get_rect(center=(int(ft.x), int(ft.y)))
            screen.blit(surf, rect)

    # ================================================================
    # 关卡提升提示
    # ================================================================

    def _draw_level_up(self, screen: pygame.Surface) -> None:
        """关卡提升时屏幕中央闪现大字提示。"""
        if self._level_up_timer <= 0:
            return

        # 渐入渐出：前 20% 渐入，后 20% 渐出，中间不透明
        total = LEVEL_UP_DISPLAY_TIME
        elapsed = total - self._level_up_timer
        if elapsed < total * 0.2:
            alpha = int(255 * elapsed / (total * 0.2))
        elif elapsed > total * 0.8:
            alpha = int(255 * (total - elapsed) / (total * 0.2))
        else:
            alpha = 255
        alpha = max(0, min(255, alpha))

        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 30

        # 主标题
        big = self._font_big.render(f"LEVEL {self._current_level}", True, CYAN)
        big.set_alpha(alpha)
        big_rect = big.get_rect(center=(cx, cy))
        screen.blit(big, big_rect)

        # 副标题
        small = self._font_normal.render("难度提升！", True, ORANGE)
        small.set_alpha(alpha)
        small_rect = small.get_rect(center=(cx, cy + 36))
        screen.blit(small, small_rect)
