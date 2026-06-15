"""
==============================================================================
飞机大战 — 性能分析工具
==============================================================================
轻量级帧时间分解器 — 测量游戏循环各环节的耗时。

用法：
  profiler = FrameProfiler()
  profiler.begin_frame()
  
  profiler.begin_section("events")
  handle_events()
  profiler.end_section()
  
  profiler.begin_section("update")
  update_logic()
  profiler.end_section()
  
  profiler.begin_section("render")
  render()
  profiler.end_section()
  
  profiler.end_frame()
  profiler.draw(screen)  # 显示柱状图
"""

import time
import pygame
from settings import SCREEN_WIDTH, UI_FONT_PATH, GREEN, YELLOW, RED, CYAN, WHITE


class FrameProfiler:
    """
    帧时间分解器。

    每帧记录各环节耗时，计算：
      - 每环节的耗时（ms）
      - 占比（%）
      - 每环节历史均值（平滑）
    """

    COLORS = {
        "events": (100, 200, 255),
        "update": (100, 255, 150),
        "collision": (255, 200, 100),
        "spawn": (255, 150, 100),
        "particles": (200, 100, 255),
        "render": (255, 100, 100),
        "network": (100, 200, 200),
        "ui": (200, 200, 100),
        "other": (150, 150, 150),
    }

    def __init__(self, max_samples: int = 60) -> None:
        self._max_samples = max_samples
        self._visible: bool = False
        self._sections: dict[str, float] = {}  # 当前帧各环节耗时

        # 历史记录
        self._history: dict[str, list[float]] = {}
        self._frame_times: list[float] = []  # 总帧时间历史
        self._section_order: list[str] = []

        # 当前帧状态
        self._current_section: str | None = None
        self._section_start: float = 0.0
        self._frame_start: float = 0.0
        self._wall_start: float = 0.0

    @property
    def visible(self) -> bool:
        return self._visible

    def toggle(self) -> None:
        """切换显示/隐藏。"""
        self._visible = not self._visible

    def begin_frame(self) -> None:
        """开始一帧的计时。"""
        now = time.perf_counter()
        self._wall_start = now
        self._frame_start = now
        self._sections.clear()
        self._current_section = None

    def begin_section(self, name: str) -> None:
        """开始记录一个环节。"""
        now = time.perf_counter()
        if self._current_section is not None:
            # 自动结束上一环节
            elapsed = (now - self._section_start) * 1000  # ms
            self._sections[self._current_section] = elapsed
        self._current_section = name
        self._section_start = now

    def end_section(self) -> None:
        """结束当前环节。"""
        now = time.perf_counter()
        if self._current_section is not None:
            elapsed = (now - self._section_start) * 1000
            self._sections[self._current_section] = elapsed
            self._current_section = None

    def end_frame(self) -> None:
        """结束一帧的计时，记录历史。"""
        self.end_section()
        now = time.perf_counter()
        total = (now - self._frame_start) * 1000

        # 更新历史
        for name, elapsed in self._sections.items():
            if name not in self._history:
                self._history[name] = []
                self._section_order.append(name)
            hist = self._history[name]
            hist.append(elapsed)
            if len(hist) > self._max_samples:
                hist.pop(0)

        self._frame_times.append(total)
        if len(self._frame_times) > self._max_samples:
            self._frame_times.pop(0)

    # ════════════════════════════════════════════════════════════════
    # 统计
    # ════════════════════════════════════════════════════════════════

    def _mean(self, values: list[float]) -> float:
        if not values:
            return 0.0
        return sum(values) / len(values)

    def _max_val(self, values: list[float]) -> float:
        if not values:
            return 0.0
        return max(values)

    @property
    def avg_frame_time(self) -> float:
        return self._mean(self._frame_times)

    @property
    def max_frame_time(self) -> float:
        return self._max_val(self._frame_times)

    # ════════════════════════════════════════════════════════════════
    # 渲染
    # ════════════════════════════════════════════════════════════════

    def draw(self, screen: pygame.Surface) -> None:
        """在屏幕左上角绘制帧时间分解柱状图。"""
        if not self._visible:
            return

        try:
            font = pygame.font.Font(UI_FONT_PATH, 13)
            small_font = pygame.font.Font(UI_FONT_PATH, 11)
        except Exception:
            font = pygame.font.Font(None, 13)
            small_font = pygame.font.Font(None, 11)

        x0, y0 = 8, 60
        bar_w = 140
        bar_h = 14
        spacing = 2

        # 总帧时间标题
        avg_ms = self.avg_frame_time
        max_ms = self.max_frame_time
        title = f"Frame: {avg_ms:.1f}ms (max {max_ms:.1f}ms)  FPS目标: {1000/60:.0f}ms"
        title_color = GREEN if avg_ms < 12 else (YELLOW if avg_ms < 16.7 else RED)
        title_surf = font.render(title, True, title_color)
        screen.blit(title_surf, (x0, y0))

        # 半透明背景
        n_sections = len(self._section_order)
        bg_h = 28 + n_sections * (bar_h + spacing) + 5
        bg = pygame.Surface((bar_w + 120, bg_h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 180))
        screen.blit(bg, (x0, y0))

        y = y0 + 22

        # 绘制每环节的柱状条
        max_elapsed = max(
            (self._mean(self._history.get(name, [0])) for name in self._section_order),
            default=16.7,
        )
        max_elapsed = max(max_elapsed, 1.0)

        for name in self._section_order:
            avg = self._mean(self._history.get(name, [0]))
            color = self.COLORS.get(name, (150, 150, 150))

            # 名称标签
            name_surf = small_font.render(name, True, WHITE)
            screen.blit(name_surf, (x0 + 4, y + 1))

            # 柱状条
            ratio = min(1.0, avg / 16.7)  # 以 16.7ms（60fps）为基准
            fill_w = int(bar_w * ratio)
            # 柱状背景
            pygame.draw.rect(screen, (30, 30, 30),
                           (x0 + 60, y, bar_w, bar_h))
            if fill_w > 0:
                # 颜色随占比变化
                bar_color = GREEN if ratio < 0.4 else (YELLOW if ratio < 0.7 else RED)
                pygame.draw.rect(screen, bar_color,
                               (x0 + 60, y, fill_w, bar_h))
                # 高亮
                if fill_w > 4:
                    pygame.draw.rect(screen, (255, 255, 255, 40),
                                   (x0 + 60, y, fill_w, 2))

            # 数值标签
            val_surf = small_font.render(f"{avg:.2f}ms", True, color)
            screen.blit(val_surf, (x0 + 64 + bar_w + 4, y))

            y += bar_h + spacing

        # 当前帧各环节的实时值
        y += 4
        label = "this frame:"
        label_surf = small_font.render(label, True, CYAN)
        screen.blit(label_surf, (x0 + 4, y))
        y += 14
        for name, elapsed in self._sections.items():
            color = self.COLORS.get(name, (150, 150, 150))
            line = f"  {name}: {elapsed:.2f}ms"
            line_surf = small_font.render(line, True, color)
            screen.blit(line_surf, (x0 + 4, y))
            y += 12
            if y > screen.get_height() - 20:
                break
