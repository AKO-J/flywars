"""
==============================================================================
飞机大战 — UI 绘制辅助工具
==============================================================================
提供面板、进度条、文字等通用绘制方法，供 UISystem 和 Game 共用。
"""

import pygame
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, UI_FONT_PATH


# ── 颜色常量 ──
PANEL_BG = (12, 12, 22)
PANEL_BORDER = (50, 55, 75)
PANEL_BORDER_LIGHT = (70, 80, 110)
ACCENT_GOLD = (255, 215, 80)
ACCENT_CYAN = (0, 200, 220)
TEXT_DIM = (130, 130, 145)
TEXT_NORMAL = (195, 195, 210)
TEXT_BRIGHT = (235, 235, 245)


# ── 字体缓存 ──
_font_cache: dict[tuple[str, int], pygame.font.Font] = {}


def get_font(size: int, path: str = UI_FONT_PATH) -> pygame.font.Font:
    key = (path, size)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.Font(path, size)
    return _font_cache[key]


def draw_panel(
    screen: pygame.Surface,
    rect: pygame.Rect | tuple,
    bg_color: tuple = PANEL_BG,
    border_color: tuple = PANEL_BORDER,
    border_width: int = 1,
    alpha: int = 230,
) -> None:
    """绘制半透明面板（带底色 + 边框）。"""
    if not isinstance(rect, pygame.Rect):
        rect = pygame.Rect(rect)
    if alpha < 255:
        panel = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        panel.fill((*bg_color, alpha))
        screen.blit(panel, (rect.x, rect.y))
    else:
        pygame.draw.rect(screen, bg_color, rect)
    if border_width > 0:
        pygame.draw.rect(screen, border_color, rect, width=border_width)


def draw_text_centered(
    screen: pygame.Surface,
    text: str,
    center: tuple[int, int],
    font: pygame.font.Font,
    color: tuple = TEXT_BRIGHT,
    shadow: bool = False,
    shadow_color: tuple = (0, 0, 0),
    shadow_offset: int = 2,
) -> pygame.Rect:
    """绘制居中文字，可选阴影。"""
    if shadow:
        s = font.render(text, True, shadow_color)
        screen.blit(s, s.get_rect(center=(center[0] + shadow_offset, center[1] + shadow_offset)))
    surf = font.render(text, True, color)
    r = surf.get_rect(center=center)
    screen.blit(surf, r)
    return r


def draw_text_left(
    screen: pygame.Surface,
    text: str,
    pos: tuple[int, int],
    font: pygame.font.Font,
    color: tuple = TEXT_BRIGHT,
) -> pygame.Rect:
    """绘制左对齐文字。"""
    surf = font.render(text, True, color)
    r = surf.get_rect(topleft=pos)
    screen.blit(surf, r)
    return r


def draw_separator(
    screen: pygame.Surface,
    y: int,
    x_start: int,
    x_end: int,
    color: tuple = (60, 65, 85),
    width: int = 1,
) -> None:
    """绘制水平分隔线。"""
    pygame.draw.line(screen, color, (x_start, y), (x_end, y), width)


def draw_progress_bar(
    screen: pygame.Surface,
    rect: pygame.Rect | tuple,
    ratio: float,
    bar_color: tuple,
    bg_color: tuple = (30, 30, 40),
    border_color: tuple = (70, 75, 95),
) -> None:
    """绘制进度条。"""
    if not isinstance(rect, pygame.Rect):
        rect = pygame.Rect(rect)
    pygame.draw.rect(screen, bg_color, rect)
    fill_w = max(0, int(rect.w * min(1.0, ratio)))
    if fill_w > 0:
        pygame.draw.rect(screen, bar_color, (rect.x, rect.y, fill_w, rect.h))
    pygame.draw.rect(screen, border_color, rect, width=1)
