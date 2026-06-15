# FlyWars 项目结构文档

> 用于 AI 助手快速了解项目布局。
> 最后更新: 2026-06-15

---

## 顶层文件

| 文件 | 行数 | 作用 |
|------|:----:|------|
| `main.py` | 28 | 游戏入口，加载配置 → 创建 Game → run() |
| `settings.py` | 343 | 全局常量、枚举、关卡波次配置、难度参数 |
| `pyproject.toml` | — | 项目元数据、依赖、pytest/ruff 配置 |
| `requirements.txt` | — | pip 依赖（pygame, pytest） |
| `Makefile` | — | 常用命令（install/test/run/lint） |
| `README.md` | — | 项目说明文档 |
| `.gitignore` | — | Git 忽略规则 |
| `.pre-commit-config.yaml` | — | 提交前代码质量钩子 |
| `MANIFEST.in` | — | 源码发行版文件清单 |

---

## 目录结构

```
flywars/
├── main.py                  ← 唯一入口
├── settings.py              ← 全局配置/常量
│
├── config/                  ← JSON 配置系统
│   ├── config_manager.py    ← 加载/校验/合并/热重载 JSON 配置
│   ├── default.json         ← 默认配置（被 settings.py 的 _sync 覆盖）
│   └── user.json            ← 用户自定义覆盖
│
├── core/
│   └── game.py (2722行)     ← 游戏主循环、状态机、渲染、输入、关卡推进
│
├── entities/                ← 游戏实体（逻辑层）
│   ├── player.py (1037行)   ← 玩家：移动/蓄力/道具/升级/复活/判定点
│   ├── enemy.py (836行)     ← 敌机：4种小怪 + Boss（多阶段+加权弹幕）
│   └── bullet.py (406行)    ← 子弹：3种蓄力外观 + 4种敌机样式
│
├── sprites/                 ← 精灵层（渲染/动画）
│   ├── particles.py (346行) ← 粒子系统（尾焰/火花/爆炸/升级光环）
│   ├── explosion.py (163行) ← 爆炸帧动画（spark/normal/big/huge）
│   ├── powerup.py (160行)   ← 道具精灵（6种类型+下落+脉冲）
│   ├── player.py (5行)      ← 垫片 → entities.player
│   ├── enemy.py (12行)      ← 垫片 → entities.enemy
│   └── bullet.py (5行)      ← 垫片 → entities.bullet
│
├── systems/                 ← 子系统
│   ├── spawner.py (506行)   ← 波次制敌机生成器（LEVEL_WAVES 驱动）
│   ├── collision.py (367行) ← 碰撞检测（子弹vs敌机/玩家vs敌机/玩家vs子弹）
│   ├── audio.py (700行)     ← 音效系统（加载WAV/程序化合成降级）
│   ├── background.py (540行)← 视差星空+星云+流星+天体+关卡主题
│   ├── ui.py (549行)        ← HUD、飘字、炸弹闪屏、道具指示器
│   ├── ui_helpers.py (116行)← UI 绘制工具函数
│   ├── player_upgrades.py (579行) ← 升级系统（经验/6种强化/持久化/界面）
│   ├── network_client.py (833行)← TCP 网络客户端
│   ├── protocol.py (375行)  ← 二进制协议编解码
│   ├── server.py → server/  ← 异步 TCP 游戏服务器
│   ├── event_bus.py (186行) ← 事件总线（同步+异步发布订阅）
│   ├── leaderboard.py (155行)← 排行榜 Top5 JSON 持久化
│   ├── logger.py (167行)    ← 结构化日志 JSONL
│   ├── frame_io.py (43行)   ← 帧读写（4字节长度前缀）
│   ├── profiler.py (234行)  ← 性能分析器
│   ├── replay.py (300行)    ← 回放系统
│   └── spatial_hash.py (161行) ← 空间哈希（当前已禁用）
│
├── server/
│   └── server.py            ← asyncio TCP 游戏服务器
│
├── levels/                  ← 关卡数据
│   ├── waves.py             ← 波次配置
│   ├── formations.py        ← 阵型配置
│   └── themes.py            ← 背景主题
│
├── utils/
│   └── resource_manager.py  ← 资源加载缓存（图片/字体/音效）
│
├── config/                  ← JSON 配置
│
├── assets/
│   ├── images/              ← 游戏素材图片
│   ├── sounds/              ← 音效文件（WAV）和 sound_plan.md
│   └── leaderboard.json     ← 排行榜数据
│
├── tests/                   ← 单元测试（pytest）
│   ├── conftest.py          ← 无头 CI 配置
│   ├── test_bullet.py       ← 子弹创建/移动/越界/穿透
│   ├── test_collision.py    ← 碰撞检测
│   ├── test_config.py       ← 配置加载/校验/热重载
│   ├── test_enemy.py        ← 敌机移动/伤害/Boss
│   ├── test_event_bus.py    ← 事件总线
│   ├── test_network_client.py ← 网络客户端
│   ├── test_player.py       ← 玩家移动/蓄力/射击/伤害/道具
│   ├── test_protocol.py     ← 协议编解码
│   ├── test_resource.py     ← 资源管理
│   ├── test_server.py       ← 服务器
│   └── test_spawner.py      ← 波次生成器
│
├── tools/                   ← 工具脚本
│   ├── generate_sounds.py   ← 程序化音效生成器
│   ├── test_multiplayer.bat ← 多人测试启动器
│   ├── headless_client.py   ← 无头客户端
│   ├── test_client.py       ← 交互测试客户端
│   └── chat_screenshot.py   ← 聊天截图
│
└── docs/                    ← 文档
    └── FlyWars_Technical_Documentation.docx
```

---

## 核心架构

### 游戏状态机 (`core/game.py`)

```
MENU ──[SPACE]──→ PLAYING ──[死亡]──→ GAME_OVER ──→ UPGRADE ──→ MENU
                    ↑    ↓                   ↑
                    │    ├──[P/ESC]→ PAUSED   └──[R]──→ PLAYING
                    │    └──[P/ESC]←
                    └──[击败最终Boss]──→ VICTORY
```

### 关卡系统 (`systems/spawner.py` + `settings.py`)

- 每关由 **N 个波次** 组成（LEVEL_WAVES 定义）
- 每波有敌机编队（随机排列），逐架生成
- 波次清空 → 1.2 秒休息 → 下一波
- 所有波次完成 → 清场 → Boss 出现
- 击败 Boss → 关卡过渡 → 下一关

### 玩家成长 (`systems/player_upgrades.py`)

- 击杀敌机获得经验值（XP）
- 升级获得强化点数（6 种方向）
- 数据持久化到 `assets/player_upgrades.json`
- 强化：❤️生命 ⚡火力 🔥蓄力 💨速度 🌊弹幕扩散 🛡️护盾精通

### Boss 战斗 (`entities/enemy.py`)

- **Phase 1** (HP>70%): 标准速度/弹幕
- **Phase 2** (70%≥HP>30%): 速度×1.35, 射速×0.65, 新增交叉弹幕
- **Phase 3** (HP≤30%): 速度×1.8, 射速×0.4, 狂暴模式
- 弹幕：加权随机选择（基于玩家位置+HP阶段）
- 第9关 Boss HP ≈ 229

---

## 测试

- pytest 配置在 `pyproject.toml` 中
- 无头模式：`conftest.py` 设置 SDL_VIDEODRIVER=dummy
- 运行：`pytest tests/`（186 个测试）

## 构建/部署

- `pip install -e .` 可安装
- CI：`.github/workflows/ci.yml`（3 Python × 2 OS 矩阵）
- 音效生成：`python tools/generate_sounds.py`
