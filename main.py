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
from config.config_manager import get_config
from core.game import Game

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
            print("\n" + ai.summary())
            ai.close()
