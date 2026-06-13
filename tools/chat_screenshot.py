"""
聊天系统 UI 截图脚本 — 使用 pygame dummy 驱动渲染并保存
"""
import os, sys
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame
pygame.init()

from settings import SCREEN_WIDTH, SCREEN_HEIGHT, UI_FONT_PATH

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
font = pygame.font.Font(UI_FONT_PATH, 16)
small_font = pygame.font.Font(UI_FONT_PATH, 14)
big_font = pygame.font.Font(UI_FONT_PATH, 28)
title_font = pygame.font.Font(UI_FONT_PATH, 42)

# ── 绘制游戏背景（模拟游戏运行中） ──
screen.fill((10, 10, 30))

# 星空背景
import random
random.seed(42)
for _ in range(80):
    x = random.randint(0, SCREEN_WIDTH)
    y = random.randint(0, SCREEN_HEIGHT)
    brightness = random.randint(100, 255)
    size = random.randint(1, 2)
    pygame.draw.circle(screen, (brightness, brightness, brightness), (x, y), size)

# 模拟玩家战机
player_x, player_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT - 120
pygame.draw.polygon(screen, (0, 200, 255), [
    (player_x, player_y - 20),
    (player_x - 15, player_y + 15),
    (player_x + 15, player_y + 15),
])
pygame.draw.polygon(screen, (0, 150, 200), [
    (player_x - 20, player_y + 5),
    (player_x - 30, player_y + 18),
    (player_x - 15, player_y + 15),
])
pygame.draw.polygon(screen, (0, 150, 200), [
    (player_x + 20, player_y + 5),
    (player_x + 30, player_y + 18),
    (player_x + 15, player_y + 15),
])

# 模拟一些子弹
for by in range(player_y - 50, 100, -60):
    pygame.draw.rect(screen, (255, 255, 0), (player_x - 2, by, 4, 12))

# 模拟敌机
for ex, ey in [(200, 150), (500, 100), (700, 200)]:
    pygame.draw.polygon(screen, (255, 80, 80), [
        (ex, ey + 15), (ex - 12, ey - 10), (ex + 12, ey - 10),
    ])

# ── HUD ──
hud_font = pygame.font.Font(UI_FONT_PATH, 18)
score_surf = hud_font.render("分数: 3580", True, (255, 215, 0))
screen.blit(score_surf, (10, 10))
level_surf = hud_font.render("关卡: 3", True, (200, 200, 255))
screen.blit(level_surf, (10, 35))

# HP bar
pygame.draw.rect(screen, (40, 40, 40), (SCREEN_WIDTH - 210, 10, 200, 16))
pygame.draw.rect(screen, (0, 200, 80), (SCREEN_WIDTH - 210, 10, 160, 16))
pygame.draw.rect(screen, (180, 180, 180), (SCREEN_WIDTH - 210, 10, 200, 16), 1)
hp_text = hud_font.render("HP", True, (255, 255, 255))
screen.blit(hp_text, (SCREEN_WIDTH - 235, 8))

# ── 远程玩家标记（模拟） ──
import math, time
t = time.time()
pulse = abs(math.sin(t * 3))
color = (0, int(200 + 55 * pulse), int(80 + 40 * pulse))
rx, ry = 350, 280
pygame.draw.circle(screen, color, (rx, ry), 14, width=2)
pygame.draw.line(screen, color, (rx-10, ry), (rx+10, ry), 2)
pygame.draw.line(screen, color, (rx, ry-10), (rx, ry+10), 2)
name_tag = small_font.render("Player2", True, color)
screen.blit(name_tag, (rx - name_tag.get_width()//2, ry + 18))

# ── 团队 HUD（模拟房间游戏中） ──
team_font = pygame.font.Font(UI_FONT_PATH, 22)
timer_text = team_font.render("01:42", True, (255, 100, 100))
screen.blit(timer_text, (SCREEN_WIDTH//2 - timer_text.get_width()//2, 10))
score_text = team_font.render("A队 30 : 20 B队", True, (0, 220, 255))
screen.blit(score_text, (SCREEN_WIDTH//2 - score_text.get_width()//2, 38))

# ── 命中反馈浮动文字（模拟 SHOT_RESULT）──
fb_font = pygame.font.Font(UI_FONT_PATH, 18)
hit_text = fb_font.render("HIT +10", True, (255, 80, 80))
hit_text.set_alpha(200)
screen.blit(hit_text, (player_x - hit_text.get_width()//2, player_y - 45))

# ── 聊天历史消息（模拟多条） ──
chat_messages = [
    {"sender": "Player2", "message": "GG!", "channel": 0},
    {"sender": "我", "message": "Nice shot!", "channel": 0},
    {"sender": "Player2", "message": "注意右边!", "channel": 1},
    {"sender": "我", "message": "收到", "channel": 1},
    {"sender": "Player3", "message": "Good luck!", "channel": 0},
]

sw, sh = SCREEN_WIDTH, SCREEN_HEIGHT
base_y = sh - 55
for i, msg in enumerate(reversed(chat_messages[-5:])):
    y = base_y - i * 20
    ch = msg["channel"]
    clr = (180, 220, 255) if ch == 0 else (150, 255, 200)
    prefix = "[全]" if ch == 0 else "[队]"
    line = f"{prefix} {msg['sender']}: {msg['message']}"
    surf = small_font.render(line, True, clr)
    bg = pygame.Surface((surf.get_width() + 6, surf.get_height() + 2), pygame.SRCALPHA)
    bg.fill((0, 0, 0, 140))
    screen.blit(bg, (8, y - 1))
    screen.blit(surf, (10, y))

# ── 聊天频道标签 ──
ch_color_global = (100, 200, 255)
ch_color_team = (100, 255, 150)

# 全局频道状态
ch_surf = small_font.render("Chat [全局]", True, ch_color_global)
screen.blit(ch_surf, (10, sh - 22))
hint = "  1:GG  2:GL  3:Nice  4:Help"
hint_surf = small_font.render(hint, True, (120, 120, 120))
screen.blit(hint_surf, (10 + ch_surf.get_width() + 5, sh - 22))

# ── 聊天输入框（激活状态）──
input_h = 28
input_y = sh - input_h - 26
input_w = 400
input_bg = pygame.Surface((input_w, input_h), pygame.SRCALPHA)
input_bg.fill((20, 20, 40, 220))
screen.blit(input_bg, (10, input_y))
pygame.draw.rect(screen, ch_color_global, (10, input_y, input_w, input_h), 1)
display_text = "[全局] Hello, nice ga|"
text_surf = font.render(display_text, True, (255, 255, 255))
screen.blit(text_surf, (15, input_y + 4))

# ── 保存截图 1: 聊天输入状态（全局频道）──
pygame.image.save(screen, r"C:\Users\26606\.qoderwork\workspace\mq88smf08p71qpya\chat_global_input.png")
print("Screenshot 1 saved: chat_global_input.png")

# ═══════════════════════════════════════════════
# 截图 2: 队伍频道 + 更多消息
# ═══════════════════════════════════════════════
# 在截图1基础上修改频道标签和输入框
screen.blit(bg, (8, base_y - 4 * 20 - 1))  # 清理旧消息区域

# 重新绘制背景
screen.fill((10, 10, 30))
for _ in range(80):
    x = random.randint(0, SCREEN_WIDTH)
    y = random.randint(0, SCREEN_HEIGHT)
    brightness = random.randint(100, 255)
    size = random.randint(1, 2)
    pygame.draw.circle(screen, (brightness, brightness, brightness), (x, y), size)

# 玩家
pygame.draw.polygon(screen, (0, 200, 255), [
    (player_x, player_y - 20), (player_x - 15, player_y + 15), (player_x + 15, player_y + 15),
])

# HUD
screen.blit(score_surf, (10, 10))
screen.blit(level_surf, (10, 35))
pygame.draw.rect(screen, (40, 40, 40), (SCREEN_WIDTH - 210, 10, 200, 16))
pygame.draw.rect(screen, (0, 200, 80), (SCREEN_WIDTH - 210, 10, 160, 16))
pygame.draw.rect(screen, (180, 180, 180), (SCREEN_WIDTH - 210, 10, 200, 16), 1)
screen.blit(hp_text, (SCREEN_WIDTH - 235, 8))

# 团队 HUD
screen.blit(timer_text, (SCREEN_WIDTH//2 - timer_text.get_width()//2, 10))
screen.blit(score_text, (SCREEN_WIDTH//2 - score_text.get_width()//2, 38))

# 队伍频道消息
team_messages = [
    {"sender": "Player2", "message": "集火Boss!", "channel": 1},
    {"sender": "我", "message": "好的，我绕后", "channel": 1},
    {"sender": "Player4", "message": "我掩护", "channel": 1},
    {"sender": "Player2", "message": "注意闪避弹幕", "channel": 1},
    {"sender": "我", "message": "快用炸弹!", "channel": 1},
    {"sender": "Player4", "message": "炸弹CD好了", "channel": 1},
    {"sender": "Player2", "message": "3 2 1 放!", "channel": 1},
    {"sender": "我", "message": "GG! 打得好!", "channel": 1},
]

base_y = sh - 55
for i, msg in enumerate(reversed(team_messages[-8:])):
    y = base_y - i * 20
    clr = (150, 255, 200)
    prefix = "[队]"
    line = f"{prefix} {msg['sender']}: {msg['message']}"
    surf = small_font.render(line, True, clr)
    bg2 = pygame.Surface((surf.get_width() + 6, surf.get_height() + 2), pygame.SRCALPHA)
    bg2.fill((0, 0, 0, 140))
    screen.blit(bg2, (8, y - 1))
    screen.blit(surf, (10, y))

# 队伍频道标签
ch_surf2 = small_font.render("Chat [队伍]", True, ch_color_team)
screen.blit(ch_surf2, (10, sh - 22))
hint_surf2 = small_font.render(hint, True, (120, 120, 120))
screen.blit(hint_surf2, (10 + ch_surf2.get_width() + 5, sh - 22))

# 队伍频道输入框
input_bg2 = pygame.Surface((input_w, input_h), pygame.SRCALPHA)
input_bg2.fill((20, 20, 40, 220))
screen.blit(input_bg2, (10, input_y))
pygame.draw.rect(screen, ch_color_team, (10, input_y, input_w, input_h), 1)
display_text2 = "[队伍] 准备放大招|"
text_surf2 = font.render(display_text2, True, (255, 255, 255))
screen.blit(text_surf2, (15, input_y + 4))

# 命中反馈
hit_text2 = fb_font.render("HIT +10", True, (255, 80, 80))
hit_text2.set_alpha(220)
screen.blit(hit_text2, (player_x - hit_text2.get_width()//2, player_y - 45))
miss_text = fb_font.render("REJECT", True, (255, 200, 0))
miss_text.set_alpha(150)
screen.blit(miss_text, (player_x + 40, player_y - 70))

pygame.image.save(screen, r"C:\Users\26606\.qoderwork\workspace\mq88smf08p71qpya\chat_team_input.png")
print("Screenshot 2 saved: chat_team_input.png")

# ═══════════════════════════════════════════════
# 截图 3: 无输入模式（仅显示频道标签和最近消息）
# ═══════════════════════════════════════════════
screen.fill((10, 10, 30))
for _ in range(80):
    x = random.randint(0, SCREEN_WIDTH)
    y = random.randint(0, SCREEN_HEIGHT)
    brightness = random.randint(100, 255)
    pygame.draw.circle(screen, (brightness, brightness, brightness), (x, y), random.randint(1,2))

pygame.draw.polygon(screen, (0, 200, 255), [
    (player_x, player_y - 20), (player_x - 15, player_y + 15), (player_x + 15, player_y + 15),
])
screen.blit(score_surf, (10, 10))
screen.blit(level_surf, (10, 35))
pygame.draw.rect(screen, (40, 40, 40), (SCREEN_WIDTH - 210, 10, 200, 16))
pygame.draw.rect(screen, (0, 200, 80), (SCREEN_WIDTH - 210, 10, 160, 16))
pygame.draw.rect(screen, (180, 180, 180), (SCREEN_WIDTH - 210, 10, 200, 16), 1)
screen.blit(hp_text, (SCREEN_WIDTH - 235, 8))
screen.blit(timer_text, (SCREEN_WIDTH//2 - timer_text.get_width()//2, 10))
screen.blit(score_text, (SCREEN_WIDTH//2 - score_text.get_width()//2, 38))

# 最近消息（无输入框）
recent_msgs = [
    {"sender": "Player2", "message": "GG!", "channel": 0},
    {"sender": "我", "message": "Good luck!", "channel": 0},
    {"sender": "Player3", "message": "Nice shot!", "channel": 0},
]
base_y = sh - 45
for i, msg in enumerate(reversed(recent_msgs)):
    y = base_y - i * 20
    ch = msg["channel"]
    clr = (180, 220, 255) if ch == 0 else (150, 255, 200)
    prefix = "[全]" if ch == 0 else "[队]"
    line = f"{prefix} {msg['sender']}: {msg['message']}"
    surf = small_font.render(line, True, clr)
    bg3 = pygame.Surface((surf.get_width() + 6, surf.get_height() + 2), pygame.SRCALPHA)
    bg3.fill((0, 0, 0, 140))
    screen.blit(bg3, (8, y - 1))
    screen.blit(surf, (10, y))

# 频道标签（无输入框）
ch_surf3 = small_font.render("Chat [全局]", True, ch_color_global)
screen.blit(ch_surf3, (10, sh - 22))
hint_surf3 = small_font.render(hint, True, (120, 120, 120))
screen.blit(hint_surf3, (10 + ch_surf3.get_width() + 5, sh - 22))

pygame.image.save(screen, r"C:\Users\26606\.qoderwork\workspace\mq88smf08p71qpya\chat_idle.png")
print("Screenshot 3 saved: chat_idle.png")

print("\nAll screenshots saved successfully!")
pygame.quit()
