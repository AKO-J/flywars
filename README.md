# Fly Wars (飞机大战)

一款基于 Python + Pygame 的经典纵版射击游戏。玩家操控战机躲避弹幕、击毁敌机、挑战 Boss，支持蓄力射击、道具系统、多人联网对战。

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Pygame](https://img.shields.io/badge/Pygame-2.x-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 游戏特色

- **四种敌机**：普通、快速（斜向飞行）、精英（正弦波走位）、追踪（锁定玩家）
- **Boss 战**：第 3 关起出现 Boss，拥有圆形弹幕、瞄准弹幕、螺旋弹幕、扇形弹幕等多种攻击模式，击败第 9 关最终 Boss 通关
- **蓄力射击**：长按空格蓄力，40% 双发、80% 三发散射
- **道具系统**：生命恢复、清屏炸弹、双倍伤害、三向散射、穿透弹、快速蓄力
- **难度递增**：每升一级敌机更快、更密、更耐打
- **多人联网**：基于 asyncio TCP 服务器，支持房间匹配、团队对战（最多 8 人）
- **配置热重载**：修改 JSON 配置后按 F5 即时生效，无需重启

## 快速开始

### 环境要求

- Python 3.10+
- Pygame

### 安装与运行

```bash
# 克隆仓库
git clone https://github.com/AKO-J/flywars.git
cd flywars

# 安装依赖
pip install pygame

# 启动游戏
python main.py
```

### 启动服务器（多人模式）

```bash
python server/server.py --host 127.0.0.1 --port 8888 --max-clients 10
```

## 操作说明

| 按键 | 功能 |
|------|------|
| 方向键 / WASD | 移动战机 |
| 空格（长按蓄力） | 射击 / 蓄力射击 |
| Shift | 加速移动 |
| P / ESC | 暂停 / 继续 |
| R | 游戏结束后重新开始 |
| F5 | 热重载配置文件 |
| F2 | 性能测试（批量生成敌机） |
| F9 | 协议编解码演示 |

## 项目结构

```
project/
├── main.py                 # 游戏入口
├── settings.py             # 全局常量与配置
├── config/
│   ├── config_manager.py   # 配置管理器（JSON 加载 / 校验 / 热重载）
│   ├── default.json        # 默认配置
│   └── user.json           # 用户自定义配置（覆盖 default）
├── core/
│   └── game.py             # 游戏主循环与状态机
├── entities/
│   ├── player.py           # 玩家实体
│   ├── bullet.py           # 子弹实体
│   └── enemy.py            # 敌机与 Boss 实体
├── sprites/
│   ├── player.py           # 玩家精灵（渲染 / 动画）
│   ├── bullet.py           # 子弹精灵
│   ├── enemy.py            # 敌机精灵
│   ├── explosion.py        # 爆炸动画
│   └── powerup.py          # 道具精灵
├── systems/
│   ├── audio.py            # 音效系统（外部音频 + 程序化波形降级）
│   ├── background.py       # 视差滚动背景
│   ├── collision.py        # 碰撞检测
│   ├── event_bus.py        # 事件总线
│   ├── leaderboard.py      # 排行榜
│   ├── logger.py           # 日志系统
│   ├── network_client.py   # 网络客户端
│   ├── protocol.py         # 自定义二进制协议
│   ├── spawner.py          # 敌机生成器
│   └── ui.py               # UI 系统（HUD / 菜单 / 飘字）
├── server/
│   └── server.py           # 异步 TCP 游戏服务器
├── tests/                  # 单元测试
├── tools/                  # 调试与测试工具
├── assets/                 # 游戏素材
└── utils/
    └── resource_manager.py # 资源管理器
```

## 游戏状态机

```
MENU ──[SPACE]──→ PLAYING ──[死亡]──→ GAME_OVER
                    ↑    ↓                ↓
                    │    ├──[P/ESC]→ PAUSED ├──[R]──→ PLAYING
                    │    └──[P/ESC]←        └──[ESC]──→ MENU
                    └──[击败最终Boss]──→ VICTORY
```

## 网络协议

采用自定义二进制帧协议：`4 字节大端长度前缀 + Message 载荷`。

支持的消息类型包括：CONN（连接）、MOVE（移动）、SHOOT（射击）、HIT（命中）、CHAT（聊天）、HEARTBEAT（心跳）、SYNC（状态同步）、ROOM 系列（房间管理）等。服务器内置射击合法性校验（坐标越界、位置偏差、射速限制）以防止作弊。

## 配置系统

游戏使用双层 JSON 配置：`default.json` 提供默认值，`user.json` 覆盖自定义项。配置管理器支持格式校验（类型 + 值域）和 F5 热重载。可配置的参数涵盖窗口、玩家、子弹、敌机、Boss、难度、音效、道具、网络等所有模块。

## 测试

```bash
pip install pytest
pytest tests/
```

## License

MIT
