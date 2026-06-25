# FlyWars — AI Context for Agents

## Overview

Python + pygame-ce 纵版射击游戏。单人闯关 + 多人 TCP 对战。
ARM64 Windows (Surface) 开发，`pygame-ce` 兼容 x86-64 和 ARM64。

```python
main.py --ai          # AI 自动驾驶演示（有画面，循环打关）
python main.py        # 正常游戏（键盘操控）
python main.py --ai --fast  # AI 无头加速测试（×10 速）
```

## 项目结构

```
flywars/
├── main.py                    ← 入口
├── core/game.py               ← 主循环 + 状态机 + 渲染 + 网络
├── settings.py                ← 全局常量
├── config/                    ← JSON 配置 + 校验
├── entities/
│   ├── player.py              ← 玩家（移动/蓄力/道具/升级/复活/判定点）
│   └── enemy.py               ← 敌机 4种 + Boss 3阶段 + 加权弹幕
├── systems/
│   ├── ai_player.py           ← AI 决策引擎 + get_debug_info()
│   ├── spawner.py             ← 波次生成器
│   ├── collision.py           ← 碰撞系统
│   ├── audio.py               ← 15 种程序化音效
│   ├── ui.py                  ← HUD
│   ├── player_upgrades.py     ← 6 种永久升级
│   ├── network_client.py      ← TCP 客户端（asyncio 后台线程）
│   ├── event_bus.py           ← 发布-订阅事件总线
│   ├── protocol.py            ← 二进制消息协议
│   ├── profiler.py            ← 性能分析器
│   ├── replay.py              ← 回放系统
│   └── background.py          ← 视差星空背景
├── server/server.py           ← TCP 游戏服务器
├── sprites/                   ← 精灵渲染
├── tools/
│   ├── check_setup.py         ← [新] 环境诊断
│   └── quick_test.py          ← 多人测试
├── setup.bat                  ← [新] 双击安装
└── run.bat                    ← [新] 双击运行 AI 演示
```

## 核心架构

### 状态机 (core/game.py)
```
MENU → PLAYING ⇄ PAUSED → GAME_OVER → UPGRADE → MENU
       ↓                          ↑
       VICTORY ───────────────────┘
```

### 主循环 (Game.run)
```
每帧: handle_events() → update() → render()
- update():  AI输入(AI模式) / 键盘 → 玩家移动 → 子弹碰撞 → 生成敌机
- render(): 背景 → 精灵(脏矩形优化) → UI → AI叠加层 → flip
```

### AI 模式 (systems/ai_player.py)
`AIPlayer.update(AIState)` → 返回动作字典。优先级：
```
1. 💨 躲避子弹（最近威胁垂直方向闪避）
2. ⚔️ 攻击敌机（朝向最近敌机移动+射击）
3. 👑 Boss 战（侧边站位，不站正下方）
4. 📦 拾取道具（150px 内主动飞过去）
```

每帧通过 `get_debug_info()` 暴露全量状态给 `_render_ai_overlay()`。

## 近期修复记录 (2025-06)

### Bug 1: AI 不能移动玩家
**根因**: `_ai_input()` 写入 `self.player.move_left`（属性不存在），
而 `Player._read_input()` 只读 `pygame.key.get_pressed()`。

**修复**: Player 加 `_ai_controlled` 标志；`_read_input()` 检测到后
跳过键盘、使用 AI 设定的 `_move_*_flag`。
涉及文件: `entities/player.py:180-184,310-319`

### Bug 2: 敌机残影
**根因**: `LayeredDirty.clear(self.screen, self.screen)` 自拷贝不擦除旧位置。

**修复**: 新增 `_bg_snapshot` 每帧在画精灵前保存干净背景，
`clear()` 用它擦除旧位置，无残影。
涉及文件: `core/game.py:1429-1432,1614-1617`

### Bug 3: 黑屏
**根因**: `_use_dirty_rects=False` 时 `_render_full()` 调用
`LayeredDirty.draw()` 只画脏精灵，背景重绘后干净精灵不重画。

**修复**: `_render_full()` 改为手动 `blit` 所有精灵。
涉及文件: `core/game.py:1504-1513`

### Bug 4: 打完 Boss 退出
**根因**: AI 模式循环内 `self.running = False` 导致退出。

**修复**: 改为 `_start_game() + continue` 循环重开第 1 关。
涉及文件: `core/game.py:2917-2923`

### Bug 5: main.py 调用 ai.summary() 不存在
**根因**: AIPlayer 只有 `report()`，main.py 调了 `summary()`。

**修复**: `summary()` → `report()`。
涉及文件: `main.py:38`

### Bug 6: 字体缺失崩溃
**根因**: `_render_ai_overlay()` 直接 `Font(UI_FONT_PATH)` 无回退。

**修复**: `try/except` + `pygame.font.Font(None, size)` 回退。
涉及文件: `core/game.py:2324-2345`

## 键位

| 键 | 功能 |
|:--:|------|
| WASD/方向键 | 移动 |
| 空格 | 按住连射，松开蓄力 |
| Q | 炸弹 |
| F1 | 显示 4px 判定点 |
| F3 | 切换脏矩形/全渲染 |
| F12 | 倍速 1x→2x→3x |
| F10 | 网络连接 |

## 核心数值

| 参数 | 值 |
|------|:---:|
| PLAYER_MAX_HP | 8 |
| PLAYER_AUTO_FIRE_INTERVAL | 0.18s |
| PLAYER_MAX_BOMBS | 3 |
| FPS | 60 |
| SCREEN | 600×820 |
| 第 5 关 Boss HP | ~75 |
| 第 9 关 Boss HP | ~229 |
| WAVE_REST_DURATION | 1.2s |

## 多人对战

- `server/server.py` → asyncio TCP 服务器
- `systems/network_client.py` → 客户端（后台线程 + EventBus）
- 协议: `systems/protocol.py` → 二进制头 (12B) + JSON/二进制负载
- 房间: 创建/加入/准备/对战/结算
- 游戏: 120s 限时，队伍积分

## 依赖

```
pygame-ce>=2.5       # ARM64/x86-64 兼容
pytest>=7.0          # 测试
```

## 已知限制

- 音效全部为程序化合成（无外部 wav 文件）
- 多人模式需要先启动 `python server/server.py`
- AI 在 `--fast` 模式下跳过渲染，仅用于快速测试
- `setup.bat` 安装时需管理员权限（如有，仅字体检查需要）
