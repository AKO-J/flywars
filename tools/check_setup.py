"""
==============================================================================
FlyWars Huan Jing Jian Cha Gong Ju
Yong Fa:  python tools/check_setup.py
Jian cha Python / pygame-ce / wen jian wan zheng xing
==============================================================================
"""
import sys
import os

errors = []
warnings = []

print("=" * 55)
print("  FlyWars Huan Jing Jian Cha")
print("=" * 55)

# 1. Python version
print(f"\n  Python:     {sys.version.split()[0]}  ({sys.executable})")
if sys.version_info < (3, 10):
    errors.append(f"Python >= 3.10 needed, current {sys.version_info.major}.{sys.version_info.minor}")

# 2. pygame(-ce)
try:
    import pygame
    ver = pygame.version.ver
    print(f"  Pygame:     {ver}  [OK]")
except ImportError:
    errors.append("pygame-ce NOT installed! Run:  pip install pygame-ce")
    ver = None

# 3. Font check
font_ok = False
font_paths = [
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "msyh.ttc"),
    os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "msyhbd.ttc"),
]
for fp in font_paths:
    if os.path.exists(fp):
        print(f"  Font:       {os.path.basename(fp)}  [OK]")
        font_ok = True
        break
if not font_ok:
    if ver:
        print(f"  Font:       msyh.ttc not found (will use default)  [WARN]")
        warnings.append("msyh.ttc not found, AI overlay uses default font")
    else:
        print(f"  Font:       skipped (pygame not installed)")

# 4. Project files
required = ["main.py", "core/game.py", "systems/ai_player.py", "settings.py"]
missing = [f for f in required if not os.path.exists(f)]
if missing:
    errors.append(f"Missing files: {missing}. Run from flywars/ directory")
else:
    print(f"  Files:      {len(required)} key files exist  [OK]")

# 5. AI module test
try:
    sys.path.insert(0, ".")
    from systems.ai_player import AIPlayer, AIState
    ai = AIPlayer()
    s = AIState(player_x=300, player_y=600, screen_w=600, screen_h=800)
    a = ai.update(s)
    d = ai.get_debug_info()
    ai.close()
    print(f"  AI module:  import + run OK  [OK]")
except Exception as e:
    errors.append(f"AI module error: {e}")

# 6. Game module import-only test
try:
    sys.path.insert(0, ".")
    from core.game import Game
    print(f"  Game:       import OK  [OK]")
except Exception as e:
    errors.append(f"Game import failed: {e}")

# Results
print()
print("=" * 55)
if errors:
    print(f"  FAIL: {len(errors)} error(s):")
    for e in errors:
        print(f"     * {e}")
else:
    print(f"  ALL CHECKS PASSED!")
    print(f"  Run:  python main.py --ai")

if warnings:
    print(f"  WARN: {len(warnings)} (non-blocking):")
    for w in warnings:
        print(f"     * {w}")
print("=" * 55)
