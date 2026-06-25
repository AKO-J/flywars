"""
==============================================================================
飞机大战 — 主入口
==============================================================================
支持模式：
  python main.py              — 正常游戏
  python main.py --ai         — AI 自动驾驶测试模式
  python main.py --ai --fast  — AI 模式 + 无渲染加速（×10 倍速）
"""

import sys

# ⭐ 友好错误提示：缺少 pygame-ce 时直接告诉用户怎么装
try:
    from core.game import Game
except ImportError as e:
    if "pygame" in str(e).lower():
        print()
        print("=" * 55)
        print("  \u26a0\ufe0f  pygame-ce \u672a\u5b89\u88c5\uff01")  # pygame-ce 未安装！
        print("=" * 55)
        print("  \u8bf7\u5728\u9879\u76ee\u76ee\u5f55\u4e0b\u8fd0\u884c\uff1a")  # 请在项目目录下运行：
        print()
        print("      pip install pygame-ce")
        print()
        print("  \u6216\u53cc\u51fb setup.bat \u81ea\u52a8\u5b89\u88c5")  # 或双击 setup.bat 自动安装
        print()
        print("=" * 55)
    else:
        print(f"Import error: {e}")
    sys.exit(1)

from config.config_manager import get_config

if __name__ == "__main__":
    ai_mode = "--ai" in sys.argv
    fast_mode = "--fast" in sys.argv

    config = get_config()
    print(f"[Config] 配置加载完成 — "
          f"分辨率={config.get('window.width')}x{config.get('window.height')}, "
          f"FPS={config.get('window.fps')}, "
          f"音量: 音效={config.get('audio.sfx_volume')}, "
          f"音乐={config.get('audio.bgm_volume')}")

    game = Game()
    if ai_mode:
        game.start_ai_mode()
    if fast_mode:
        game.set_fast_mode()

    game.run()
    game.quit()

    if ai_mode:
        ai = game.get_ai_player()
        if ai:
            print("\n" + ai.report())
            ai.close()
