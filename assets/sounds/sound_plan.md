# FlyWars 音效规划

## 目录结构

```
assets/sounds/
├── sound_plan.md          ← 本文档
├── shoot.wav              ← 玩家射击（已存在）
├── explosion.wav          ← 敌机爆炸（已存在）
├── bgm.ogg                ← 背景音乐（已存在）
├── hit.wav                ← 玩家受伤
├── death.wav              ← 玩家死亡
├── enemy_shoot.wav        ← 敌机射击
├── boss_alert.wav         ← Boss 登场
├── boss_hit.wav           ← Boss 受伤
├── boss_death.wav         ← Boss 击毁
├── powerup.wav            ← 拾取道具
├── bomb.wav               ← 炸弹引爆
├── level_up.wav           ← 关卡过渡
├── wave_start.wav         ← 新波次开始
├── revive.wav             ← 玩家复活
└── menu_select.wav        ← 菜单选择
```

## 音效设计说明

| 文件 | 类型 | 风格 | 时长 | 说明 |
|------|------|------|:----:|------|
| `shoot.wav` | SFX | 高频激光 | 0.12s | 玩家普通射击，清脆的电子音 |
| `explosion.wav` | SFX | 低频爆炸 | 0.3s | 普通敌机爆炸，短促白噪 |
| `hit.wav` | SFX | 中频撞击 | 0.15s | 玩家受伤，金属碰撞感 |
| `death.wav` | SFX | 低频下坠 | 0.6s | 玩家死亡，音调骤降 |
| `enemy_shoot.wav` | SFX | 中低频 | 0.1s | 敌机射击，比玩家射击更低沉 |
| `boss_alert.wav` | SFX | 上升警报 | 0.8s | Boss登场提示，音调渐升 |
| `boss_hit.wav` | SFX | 重击声 | 0.2s | Boss 受伤反馈，厚重 |
| `boss_death.wav` | SFX | 多重爆炸 | 1.0s | Boss 毁灭，多个低频叠加 |
| `powerup.wav` | SFX | 上升悦音 | 0.2s | 拾取道具，愉快的音阶上升 |
| `bomb.wav` | SFX | 全屏冲击 | 0.5s | 炸弹引爆，低频轰鸣 |
| `level_up.wav` | SFX | 辉煌上升 | 0.6s | 关卡过渡，和弦琶音上升 |
| `wave_start.wav` | SFX | 短促脉冲 | 0.3s | 新波次开始，警示脉冲 |
| `revive.wav` | SFX | 希望上升 | 0.5s | 复活音效，温暖音色 |
| `menu_select.wav` | SFX | 清脆点击 | 0.08s | 菜单操作反馈 |
| `bgm.ogg` | BGM | 电子/合成波 | 循环 | 背景音乐，节奏感强 |

## 音效分类

```
玩家相关:   shoot.wav  hit.wav  death.wav  revive.wav  bomb.wav
敌机相关:   enemy_shoot.wav  explosion.wav  boss_alert.wav  boss_hit.wav  boss_death.wav
道具相关:   powerup.wav
关卡相关:   level_up.wav  wave_start.wav
UI 相关:    menu_select.wav
背景音乐:   bgm.ogg
```

## 生成方式

音效使用程序化合成生成（`tools/generate_sounds.py`），
基于 pygame.sndarray + numpy 生成 PCM 波形数据，
保存为 44100Hz 16bit mono WAV 文件。

如需替换为真实录音，将同名 WAV 文件放入 `assets/sounds/` 即可自动加载。
