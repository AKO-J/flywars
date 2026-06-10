"""
pytest 配置 — 飞机大战测试框架
"""
import os

# 必须在任何 pygame 导入之前设置，确保 CI/无头环境可用
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
