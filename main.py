"""
==============================================================================
飞机大战 — 主入口
==============================================================================
项目唯一入口，委托 core.game.Game 启动游戏。

启动流程：
  ① ConfigManager 加载 JSON 配置（default.json ← user.json 覆盖）
  ② ConfigManager 校验并同步到 settings 模块变量
  ③ Game() 构造时从 settings 读取配置（已是 JSON 合并后的值）
  ④ Game.run() 进入主循环，F5 热重载配置
"""
from config.config_manager import get_config
from core.game import Game

if __name__ == "__main__":
    # ① 加载配置系统（JSON → settings 模块同步）
    config = get_config()
    print(f"[Config] 配置加载完成 — "
          f"分辨率={config.get('window.width')}x{config.get('window.height')}, "
          f"FPS={config.get('window.fps')}, "
          f"音量: 音效={config.get('audio.sfx_volume')}, "
          f"音乐={config.get('audio.bgm_volume')}")

    # ② 启动游戏
    game = Game()
    game.run()
    game.quit()
