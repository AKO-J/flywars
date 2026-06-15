"""
==============================================================================
飞机大战 — 主入口模块（题13：状态机 — 开始/暂停/结束状态切换）
==============================================================================
使用 GameState 枚举实现四态状态机：

  MENU  ──[SPACE]──→ PLAYING  ──[死亡]──→ GAME_OVER
                    ↑    ↓                   ↓
                    │    ├──[P/ESC]──→ PAUSED    ├──[R]──→ PLAYING
                    │    └──[P/ESC]──←          └──[ESC]──→ MENU
                    │
                    └────[Q]────  PAUSED ──→ MENU

不同状态渲染不同界面：菜单画面 / 游戏画面 / 暂停遮罩 / 结束画面。
"""

import sys
import math
import collections
import pygame
from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, GAME_TITLE, FPS,
    BLACK, WHITE, YELLOW, RED, GREEN, CYAN, GRAY, ORANGE,
    UI_FONT_PATH, GameState, LEVEL_SCORE_BASE,
    FPS_SAMPLE_WINDOW, PERF_TEST_ENEMY_COUNT,
    BOSS_EXPLOSION_DELAY, FINAL_BOSS_LEVEL,
)
from entities.player import Player
from entities.bullet import Bullet
from sprites.explosion import Explosion
from entities.enemy import BossEnemy, NormalEnemy, FastEnemy, EliteEnemy, TrackingEnemy
from sprites.powerup import PowerUp
from settings import PowerUpType
from systems.background import ScrollingBackground, BackgroundCallback
from systems.spawner import Spawner
from systems.collision import CollisionSystem
from systems.ui import UISystem
from systems.audio import AudioSystem
from systems.leaderboard import Leaderboard
from config.config_manager import get_config
from utils.resource_manager import ResourceManager
from systems.event_bus import EventBus, GameEvent, Event
from systems.logger import GameLogger, LogLevel
from systems.protocol import make_move, make_shoot, Message, TrafficStats
from systems.network_client import NetworkClient, ConnectionState
from systems.ui_helpers import (
    draw_panel, draw_text_centered, draw_text_left, draw_separator,
    draw_progress_bar, get_font,
    PANEL_BG, PANEL_BORDER, PANEL_BORDER_LIGHT,
    ACCENT_GOLD, ACCENT_CYAN, TEXT_DIM, TEXT_NORMAL, TEXT_BRIGHT,
)
# ⭐ 粒子特效系统
from sprites.particles import ParticleEmitter
# ⭐ 回放系统
from systems.replay import ReplayRecorder, ReplayPlayer
# ⭐ 性能分析工具
from systems.profiler import FrameProfiler
# ⭐ 玩家成长系统
from systems.player_upgrades import (
    PlayerUpgradeData, load_upgrades, save_upgrades,
    apply_upgrades_to_player, render_upgrade_screen,
)


_proto_stats = TrafficStats()


def _demo_protocol_encode_decode(player) -> None:
    """F9: 演示二进制协议编解码 — 玩家当前位置 → 打包 → 解包 → 日志。"""
    gl = GameLogger.get_instance()
    gl.info("=== 协议演示: 打包当前玩家位置 ===")

    # 1. 创建消息
    m = make_move(
        x=float(player.rect.centerx), y=float(player.rect.centery),
        dx=0.0, dy=0.0, seq=42,
    )
    gl.info("1. 创建 MOVE 消息", payload=str(m.payload))

    # 2. 编码为二进制
    data = m.encode()
    gl.info("2. 编码为二进制", size=len(data), hex=data.hex()[:60] + "...")

    # 3. 解码
    decoded = Message.decode(data)
    gl.info("3. 解码还原", payload=str(decoded.payload))

    # 4. 流量统计
    global _proto_stats
    _proto_stats.record_send(m, len(data))
    _proto_stats.record_recv(decoded, len(data))
    gl.info("4. 流量累计", stats=_proto_stats.summary())

    gl.info("=== 演示完成: 收发成功 ===")
    # 自动打开面板
    if not gl.panel_visible:
        gl.toggle_panel()


def _print_resource_stats() -> None:
    """按 F6 打印资源统计到终端。"""
    s = ResourceManager.get_instance().get_stats()
    c = s["cache"]
    a = s["access"]
    m = s["memory"]
    print(f"[Resource] 缓存: 图片{c['images']} | 音效{c['sounds']} | 字体{c['fonts']}")
    print(f"[Resource] 访问: 加载{a['loads']} | 命中{a['hits']} | 缺失{a['misses']} | 命中率{a['hit_rate']}")
    print(f"[Resource] 显存估算: {m['image_estimate_mb']} MB | 总缓存条目: {m['total_cache_entries']}")


def _print_event_stats() -> None:
    """按 F7 打印事件总线统计和最近日志到终端。"""
    bus = EventBus.get_instance()
    s = bus.get_stats()
    print(f"[EventBus] 总事件: {s['total_events']} | 待处理: {s['pending']} | 日志: {s['log_size']} | 处理器: {s['handler_count']}")
    print(f"[EventBus] 按类型: {s['by_type']}")
    recent = bus.get_log(limit=5)
    if recent:
        print(f"[EventBus] 最近 {len(recent)} 条:")
        for e in recent:
            print(f"  {e.type.name:20s} data={e.data}")


class Game:
    """游戏主控制器 — 状态机驱动"""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.init()

        self.screen: pygame.Surface = pygame.display.set_mode(
            (SCREEN_WIDTH, SCREEN_HEIGHT)
        )
        pygame.display.set_caption(GAME_TITLE)

        self.clock: pygame.time.Clock = pygame.time.Clock()
        self.running: bool = False

        # ---- 精灵组 ----
        self.all_sprites: pygame.sprite.LayeredDirty = pygame.sprite.LayeredDirty()
        self.bullets: pygame.sprite.Group = pygame.sprite.Group()
        self.enemies: pygame.sprite.Group = pygame.sprite.Group()
        self.explosions: pygame.sprite.Group = pygame.sprite.Group()
        self.powerups: pygame.sprite.Group = pygame.sprite.Group()

        # ---- 游戏系统 ----
        self.player: Player = Player()
        self.all_sprites.add(self.player)
        self.spawner: Spawner = Spawner()
        self.spawner.set_player(self.player)
        self.collision: CollisionSystem = CollisionSystem()
        self.ui: UISystem = UISystem()
        self.audio: AudioSystem = AudioSystem()
        # 应用 JSON 配置中的音频音量（覆盖 AudioSystem 默认值）
        cfg = get_config()
        self.audio.set_sfx_volume(float(cfg.get("audio.sfx_volume", 0.5)))
        self.audio.set_bgm_volume(float(cfg.get("audio.bgm_volume", 0.3)))
        self.background: ScrollingBackground = ScrollingBackground()

        # ---- 事件总线订阅（题4 + 题6日志） ----
        self._event_bus = EventBus.get_instance()
        self._event_bus.subscribe(GameEvent.ENEMY_KILLED, self._on_event_enemy_killed, priority=50)
        self._event_bus.subscribe(GameEvent.LEVEL_UP, self._on_event_level_up, priority=50)

        # 订阅来自网络的控制事件（START / STOP / PAUSE / RESUME）
        self._event_bus.subscribe(GameEvent.GAME_START, self._on_network_start, priority=100)
        self._event_bus.subscribe(GameEvent.GOTO_MENU, lambda e: self._go_to_menu(), priority=100)
        self._event_bus.subscribe(GameEvent.GAME_PAUSE, lambda e: setattr(self, 'state', GameState.PAUSED), priority=100)
        self._event_bus.subscribe(GameEvent.GAME_RESUME, lambda e: setattr(self, 'state', GameState.PLAYING), priority=100)

        # 订阅来自网络的游戏同步事件（MOVE / SHOOT / HIT）
        self._event_bus.subscribe(GameEvent.PLAYER_MOVE, self._on_network_move, priority=80)
        self._event_bus.subscribe(GameEvent.PLAYER_SHOOT, self._on_network_shoot, priority=80)
        self._event_bus.subscribe(GameEvent.PLAYER_HIT, self._on_network_hit, priority=90)
        self._event_bus.subscribe(GameEvent.SHOT_FEEDBACK, self._on_shot_feedback, priority=80)
        self._event_bus.subscribe(GameEvent.CHAT_MESSAGE, self._on_chat_message, priority=80)

        # 订阅房间事件（网络→游戏）
        self._event_bus.subscribe(GameEvent.CONFIG_RELOADED, self._on_room_event, priority=50)

        # ── 团队积分状态 ──
        self._team_score_a: int = 0
        self._team_score_b: int = 0
        self._game_timer_remaining: float = 0.0
        self._battle_result: dict | None = None
        self._in_room_game: bool = False     # 是否在房间对战中
        self._remote_player_pos: tuple[float, float] | None = None  # 对方位置（目标）
        self._remote_display_pos: tuple[float, float] | None = None  # 对方位置（插值显示）
        self._remote_lerp_speed: float = 10.0  # 插值速度（越大越快跟上）

        # ── 射击反馈浮动文字（题11）──
        self._shot_feedbacks: list[dict] = []  # [{text, color, timer, x, y}]

        # ── 聊天系统（题13）──
        self._chat_input_active: bool = False      # 是否正在输入聊天
        self._chat_input_buffer: str = ""          # 当前输入文本
        self._chat_channel: int = 0                # 0=全局, 1=队伍
        self._chat_history: list[dict] = []        # [{sender, message, channel, time}]
        self._chat_max_history: int = 50           # 最大历史记录数
        self._chat_max_length: int = 100           # 消息最大长度
        self._chat_display_timer: float = 0.0      # 最近消息后的显示计时
        self._chat_display_duration: float = 8.0   # 无输入时消息显示时长
        self._chat_quick_messages: list[str] = [   # 快捷消息（1-4键）
            "GG!", "Good luck!", "Nice shot!", "Help!",
        ]

        # 日志通过事件总线记录关键操作（题6）
        self._setup_event_logging()

        # 启动日志
        GameLogger.get_instance().info("引擎初始化完成", fps=FPS)

        # ---- Boss 追踪 ----
        self._boss: BossEnemy | None = None

        # ---- Boss 死亡序列（题19：连续爆炸特效） ----
        self._boss_dying: bool = False
        self._boss_dying_timer: float = 0.0
        self._boss_dying_positions: list[tuple[int, int]] = []
        self._boss_dying_level: int = 0

        # ---- 排行榜 ----
        self.leaderboard: Leaderboard = Leaderboard()

        # ---- 网络客户端（题9） ----
        self.network: NetworkClient = NetworkClient(
            host=cfg.get("network.server_host", "127.0.0.1"),
            port=cfg.get("network.server_port", 8888),
            auto_reconnect=True,
            reconnect_base_delay=float(cfg.get("network.reconnect_base_delay", 1.0)),
            reconnect_max_delay=float(cfg.get("network.reconnect_max_delay", 30.0)),
            heartbeat_interval=float(cfg.get("network.heartbeat_interval", 5.0)),
            heartbeat_timeout=float(cfg.get("network.heartbeat_timeout", 15.0)),
        )
        self._network_auto_connect = bool(cfg.get("network.auto_connect", False))

        # ---- ⭐ 粒子特效系统 ----
        self.particles: ParticleEmitter = ParticleEmitter()

        # ---- ⭐ 游戏手柄支持 ----
        self._joystick: pygame.joystick.Joystick | None = None
        self._joystick_deadzone: float = 0.25
        self._init_joystick()

        # ---- ⭐ 关卡通提示效果 ----
        self._level_transition_alpha: float = 0.0       # 过渡遮罩透明度
        self._level_transition_timer: float = 0.0       # 过渡持续计时
        self._level_transition_text: str = ""           # 显示的关卡文字
        self._level_transition_scale: float = 0.0       # 文字缩放动画

        # ---- ⭐ 回放系统 ----
        self._replay_recorder: ReplayRecorder = ReplayRecorder()
        self._replay_player: ReplayPlayer | None = None
        self._replay_status_text: str = ""

        # ---- ⭐ 性能分析工具 ----
        self._profiler: FrameProfiler = FrameProfiler()

        # ---- 脏矩形背景回调（LayeredDirty.clear 使用）----
        self._bg_callback: BackgroundCallback = BackgroundCallback(self.background)

        # ---- FPS 追踪 ----
        self._fps_samples: collections.deque = collections.deque(maxlen=FPS_SAMPLE_WINDOW)
        self._fps_accum: float = 0.0
        self._fps_frame_count: int = 0
        self._fps_display: float = 60.0
        self._use_dirty_rects: bool = True  # 可切换对比

        # ---- 已销毁精灵的 rect（用于脏矩形 clean-up）----
        self._killed_rects: list[pygame.Rect] = []

        # ---- 姓名输入子状态（GAME_OVER 内） ----
        self._entering_name: bool = False
        self._name_buffer: str = ""

        # ---- 状态机 ----
        self.state: GameState = GameState.MENU

        # ⭐ 玩家成长系统
        self.upgrade_data: PlayerUpgradeData = load_upgrades()
        self._upgrade_selected: int = 0          # 升级界面选中项
        self._upgrade_show_levelup: bool = False # 显示升级提示
        self._upgrade_levelup_count: int = 0     # 新获得等级数
        self._xp_this_run: int = 0               # 本局获得经验

        # ---- 帧计数 / Delta-Time ----
        self.frame_count: int = 0
        self.dt: float = 0.0

        # ---- 菜单闪烁计时器 ----
        self._menu_blink: float = 0.0

        # ---- 屏幕震动 ----
        self._screen_shake: float = 0.0

        # ---- 网络同步发送节流 ----
        self._net_send_interval: int = 3  # 每 N 帧发送一次 MOVE（~20/s @ 60fps）
        self._last_sent_x: float = 0.0
        self._last_sent_y: float = 0.0

        # ---- 房间系统状态 ----
        self._room_list: list[dict] = []      # 服务器返回的房间列表
        self._my_room: dict | None = None      # 当前所在房间信息
        self._entering_password: bool = False   # 密码输入模式
        self._password_buffer: str = ""         # 密码输入缓冲
        self._join_target_rid: str = ""         # 要加入的房间ID
        self._room_list_dirty: bool = True     # 需要刷新列表
        self._room_timer: float = 0.0          # 列表刷新节流

        # ---- 菜单按钮（用于鼠标点击）----
        self._menu_buttons: list[tuple[pygame.Rect, str, str]] = []  # (rect, label, action)

    # ================================================================
    # 事件处理（状态感知）
    # ================================================================

    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if event.type == pygame.KEYDOWN:
                self._handle_keydown(event)
            elif event.type == pygame.KEYUP:
                self._handle_keyup(event)
            elif event.type == pygame.TEXTINPUT:
                if self._entering_name:
                    self._handle_name_text(event)
                elif self._entering_password:
                    self._handle_password_text(event)
                elif self._chat_input_active:
                    # 聊天文本输入（题13）
                    if len(self._chat_input_buffer) < self._chat_max_length:
                        self._chat_input_buffer += event.text
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_menu_click(event.pos)
            # ⭐ 手柄按钮事件
            elif event.type == pygame.JOYBUTTONDOWN:
                self._handle_joystick_button(event)

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        key = event.key

        # ── 调试：GAME_OVER/VICTORY 状态打印所有按键 ──
        if self.state in (GameState.GAME_OVER, GameState.VICTORY):
            print(f"[KEYDBG] key={key} state={self.state.name}")

        # ═══════════════════════════════════════════════════
        # 全局按键（所有状态生效）
        # ═══════════════════════════════════════════════════
        if key == pygame.K_F4 and (pygame.key.get_mods() & pygame.KMOD_ALT):
            self.running = False
            return
        if key == pygame.K_F1:
            self.player.toggle_hitbox_visible()
            return
        if key == pygame.K_F2:
            self._spawn_stress_test_enemies()
            return
        if key == pygame.K_F3:
            self._use_dirty_rects = not self._use_dirty_rects
            return
        if key == pygame.K_F5:
            self._reload_config()
            return
        if key == pygame.K_F6:
            _print_resource_stats()
            return
        if key == pygame.K_F7:
            _print_event_stats()
            return
        if key == pygame.K_BACKQUOTE:  # ~ 键切换日志面板
            GameLogger.get_instance().toggle_panel()
            return

        # ── 聊天系统快捷键（题13）──
        if self._chat_input_active:
            if key == pygame.K_RETURN:
                # 发送聊天消息
                text = self._chat_input_buffer.strip()
                if text and self.network.is_connected:
                    self.network.send_chat(text, channel=self._chat_channel)
                    # 本地也添加到历史
                    self._add_chat_history("我", text, self._chat_channel)
                self._chat_input_active = False
                self._chat_input_buffer = ""
                return
            if key == pygame.K_ESCAPE:
                # 取消输入
                self._chat_input_active = False
                self._chat_input_buffer = ""
                return
            if key == pygame.K_TAB:
                # 切换频道
                self._chat_channel = 1 - self._chat_channel
                return
            if key == pygame.K_BACKSPACE:
                self._chat_input_buffer = self._chat_input_buffer[:-1]
                return
            return  # 聊天输入模式下拦截其他按键

        # Enter 键打开聊天输入（PLAYING 或 MENU 状态）
        if key == pygame.K_RETURN and self.state in (GameState.PLAYING, GameState.MENU):
            self._chat_input_active = True
            self._chat_input_buffer = ""
            return
        # Tab 键快速切换频道（不在输入模式时）
        if key == pygame.K_TAB and self.state in (GameState.PLAYING, GameState.MENU):
            self._chat_channel = 1 - self._chat_channel
            ch = "队伍" if self._chat_channel == 1 else "全局"
            print(f"[CHAT] 频道切换 → {ch}")
            return
        # 快捷消息 1-4（PLAYING 状态，连接中）
        if self.state == GameState.PLAYING and self.network.is_connected:
            if key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                idx = key - pygame.K_1
                if idx < len(self._chat_quick_messages):
                    text = self._chat_quick_messages[idx]
                    self.network.send_chat(text, channel=self._chat_channel)
                    self._add_chat_history("我", text, self._chat_channel)
                return
        if key == pygame.K_F9:
            _demo_protocol_encode_decode(self.player)
            return
        if key == pygame.K_F10:
            self._toggle_network()
            return
        # ⭐ F11 性能分析工具
        if key == pygame.K_F11:
            self._profiler.toggle()
            print(f"[PROFILER] {'显示' if self._profiler.visible else '隐藏'}")
            return
        # ⭐ 回放热键: F3=录制, F4=回放
        if key == pygame.K_F3:
            if not self._replay_recorder.is_recording and self._replay_player is None:
                # 如果在游戏中，立即开始录制
                if self.state == GameState.PLAYING:
                    self._replay_recorder.start()
                    self._replay_status_text = "⏺ 录制中..."
                    gl = GameLogger.get_instance()
                    gl.info("回放录制开始", frame=self.frame_count)
                    print(f"[REPLAY] 📹 开始录制 (frame={self.frame_count})")
            else:
                # 停止录制
                if self._replay_recorder.is_recording:
                    data = self._replay_recorder.stop()
                    gl = GameLogger.get_instance()
                    gl.info("回放录制结束", frames=len(data.frames),
                            duration=f"{data.duration_seconds:.1f}s")
                    self._replay_status_text = f"✅ 录制完成 ({len(data.frames)}帧)"
                    print(f"[REPLAY] 📹 录制结束: {len(data.frames)}帧 "
                          f"{data.duration_seconds:.1f}s")
            return
        if key == pygame.K_F4:
            if self._replay_player is not None and self._replay_player.is_playing:
                self._replay_player.stop()
                self._replay_player = None
                self._replay_status_text = ""
                print(f"[REPLAY] ⏹ 回放停止")
            elif self._replay_recorder._data.frames:
                # 从录制数据创建回放
                self._replay_player = ReplayPlayer(self._replay_recorder._data)
                self._replay_player.start()
                self._replay_status_text = "▶ 回放中..."
                gl = GameLogger.get_instance()
                gl.info("回放开始", frames=len(self._replay_player._data.frames))
                print(f"[REPLAY] ▶ 开始回放 ({len(self._replay_player._data.frames)}帧)")
            return

        # ═══════════════════════════════════════════════════
        # 状态：MENU
        # ═══════════════════════════════════════════════════
        if self.state == GameState.MENU:
            # 密码输入模式拦截
            if self._entering_password:
                if key == pygame.K_RETURN:
                    pwd = self._password_buffer.strip()
                    self._entering_password = False
                    if self._join_target_rid:
                        self.network.send_room_join(self._join_target_rid, pwd)
                        print(f"[MENU] 加入房间 #{self._join_target_rid} (密码='{pwd}')")
                        self._join_target_rid = ""
                    else:
                        self._room_create(password=pwd)
                        print(f"[MENU] 房间已创建 (密码='{pwd}')")
                    return
                if key == pygame.K_ESCAPE:
                    self._entering_password = False
                    self._join_target_rid = ""
                    return
                    self._entering_password = False
                    print("[MENU] 取消创建房间")
                    return
                if key == pygame.K_BACKSPACE:
                    self._password_buffer = self._password_buffer[:-1]
                    return
                return  # 其他按键忽略

            if key in (pygame.K_SPACE, pygame.K_RETURN):
                # 在房间中 → 自动准备 + 如果双方都准备则开始
                if self._my_room:
                    self.network.send_room_ready()
                    print("[MENU] 已发送准备，等待对方也准备...")
                    return
                self._start_game()
                return
            if key in (pygame.K_ESCAPE, pygame.K_q):
                self.running = False
                return
            # ── 房间操作 ──
            if self.network.is_connected:
                if key == pygame.K_r:
                    self._entering_password = True
                    self._password_buffer = ""
                    print("[MENU] 创建房间 — 请输入密码 (ENTER确认, ESC取消, 空密码=无密码)")
                    return
                if key == pygame.K_j and self._room_list:
                    r = self._room_list[0]
                    if r.get("has_password"):
                        self._entering_password = True
                        self._password_buffer = ""
                        self._join_target_rid = r.get("id", "")
                        print(f"[MENU] 加入房间 #{self._join_target_rid} — 请输入密码")
                    else:
                        self._room_join_first("")
                    return
                if key == pygame.K_y:
                    self.network.send_room_ready()
                    return
                if key == pygame.K_l:
                    self.network.send_room_leave()
                    self._my_room = None
                    self._room_list_dirty = True
                    return
                if key == pygame.K_SLASH:
                    self.network.send_room_list()
                    self._room_list_dirty = True
                    return
            else:
                # 未连接时按下房间按键 → 提示
                if key in (pygame.K_r, pygame.K_j, pygame.K_y, pygame.K_l):
                    print("[MENU] ⚠ 请先按 F10 连接服务器")

        # ═══════════════════════════════════════════════════
        # 状态：PLAYING
        # ═══════════════════════════════════════════════════
        elif self.state == GameState.PLAYING:
            # 暂停
            if key in (pygame.K_p, pygame.K_ESCAPE, pygame.K_q):
                self.state = GameState.PAUSED
                return
            # ⭐ 自动连射：由 update() 中的 update_auto_fire 统一处理
            # 空格 KEYDOWN 只设置 _is_firing 标记
            if key == pygame.K_SPACE:
                # 由 handle_keydown 设置 _is_firing
                self.audio.play_shoot()
            # 使用炸弹（Q 键）
            if key == pygame.K_q:
                if self.player.use_bomb():
                    self._trigger_bomb()
            # 玩家移动标记
            self.player.handle_keydown(event)

        # ═══════════════════════════════════════════════════
        # 状态：PAUSED
        # ═══════════════════════════════════════════════════
        elif self.state == GameState.PAUSED:
            if key in (pygame.K_p, pygame.K_ESCAPE):
                self.state = GameState.PLAYING
                return
            if key == pygame.K_q:
                self._go_to_menu()
                return

        # ═══════════════════════════════════════════════════
        # 状态：GAME_OVER
        # ═══════════════════════════════════════════════════
        elif self.state == GameState.GAME_OVER:
            if self._entering_name:
                self._handle_name_input(event)
                return
            if key == pygame.K_r:
                print(f"[KEYDBG] GAME_OVER R handler reached, score={self.collision.score}, is_high={self.leaderboard.is_high_score(self.collision.score)}")
                if self.leaderboard.is_high_score(self.collision.score):
                    self._entering_name = True
                    self._name_buffer = ""
                    print(f"[GAME] 🏆 高分录入! score={self.collision.score}")
                else:
                    print(f"[GAME] 分数不足以录入 ({self.collision.score})")
                    self._start_game()
                return
            if key in (pygame.K_ESCAPE, pygame.K_q):
                self._go_to_menu()
                return

        # ═══════════════════════════════════════════════════
        # 状态：VICTORY（题19：通关胜利）
        # ═══════════════════════════════════════════════════
        elif self.state == GameState.VICTORY:
            if self._entering_name:
                self._handle_name_input(event)
                return
            if key == pygame.K_r:
                if self.leaderboard.is_high_score(self.collision.score):
                    self._entering_name = True
                    self._name_buffer = ""
                else:
                    self._go_to_upgrade()  # ⭐ 先去升级界面
                return
            if key in (pygame.K_ESCAPE, pygame.K_q):
                self._go_to_upgrade()  # ⭐ 先去升级界面
                return

        # ═══════════════════════════════════════════════════
        # 状态：UPGRADE（⭐ 升级加点界面）
        # ═══════════════════════════════════════════════════
        elif self.state == GameState.UPGRADE:
            if key == pygame.K_UP or key == pygame.K_w:
                self._upgrade_selected = max(0, self._upgrade_selected - 1)
            elif key == pygame.K_DOWN or key == pygame.K_s:
                items = self.upgrade_data.get_levels_for_display()
                self._upgrade_selected = min(len(items) - 1, self._upgrade_selected + 1)
            elif key in (pygame.K_SPACE, pygame.K_RETURN):
                items = self.upgrade_data.get_levels_for_display()
                if 0 <= self._upgrade_selected < len(items):
                    uid = items[self._upgrade_selected]["id"]
                    if self.upgrade_data.apply_upgrade(uid):
                        save_upgrades(self.upgrade_data)
                        print(f"[UPGRADE] 已强化 {items[self._upgrade_selected]['name']}")
                        if self.upgrade_data.points <= 0:
                            self.state = GameState.MENU  # 都用完了，直接回菜单
            elif key == pygame.K_ESCAPE or key == pygame.K_q:
                self.state = GameState.MENU  # 直接回菜单，无需再次清理

    # ════════════════════════════════════════════════════════════════
    # ⭐ 游戏手柄支持
    # ════════════════════════════════════════════════════════════════

    def _init_joystick(self) -> None:
        """初始化第一个可用手柄。"""
        try:
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                joy = pygame.joystick.Joystick(0)
                joy.init()
                self._joystick = joy
                gl = GameLogger.get_instance()
                gl.info("手柄已连接", name=joy.get_name(),
                        axes=joy.get_numaxes(), buttons=joy.get_numbuttons())
                print(f"[JOY] 手柄已连接: {joy.get_name()}"
                      f" (axis={joy.get_numaxes()} btn={joy.get_numbuttons()})")
        except Exception as e:
            self._joystick = None
            print(f"[JOY] 手柄初始化失败: {e}")

    def _handle_joystick(self) -> None:
        """每帧读取手柄状态 → 转换为键盘等效操作。"""
        if self._joystick is None or self.state != GameState.PLAYING:
            return

        try:
            # 左摇杆 → 方向移动
            axis_x = self._joystick.get_axis(0)
            axis_y = self._joystick.get_axis(1)

            # 死区过滤
            if abs(axis_x) < self._joystick_deadzone:
                axis_x = 0
            if abs(axis_y) < self._joystick_deadzone:
                axis_y = 0

            # 模拟按键事件给 player
            keys = pygame.key.get_pressed()
            if axis_x < 0:
                self.player.move_left = True
            elif axis_x > 0:
                self.player.move_right = True
            if axis_y < 0:
                self.player.move_up = True
            elif axis_y > 0:
                self.player.move_down = True

            # ⭐ LT/RT/L2/R2 扳机 → 射击 / 加速（轴 2/5 或 4/5 视手柄而定）
            if self._joystick.get_numaxes() >= 5:
                trigger_l = self._joystick.get_axis(2)  # LT
                trigger_r = self._joystick.get_axis(5)  # RT
                if trigger_r > 0.3:
                    self.player._is_firing = True
                if trigger_l > 0.3:
                    # 加速（等同于 Shift）
                    keys_boost = True
                    self.player.move_speed_mult = self.player.BOOST_MULTIPLIER
                else:
                    self.player.move_speed_mult = 1.0

            # ⭐ 右摇杆 → 快速移动（瞄准方向）
            if self._joystick.get_numaxes() >= 4:
                rx = self._joystick.get_axis(3)  # 右摇杆 X
                ry = self._joystick.get_axis(4)  # 右摇杆 Y
                if abs(rx) < self._joystick_deadzone:
                    rx = 0
                if abs(ry) < self._joystick_deadzone:
                    ry = 0
                # 右摇杆提供额外移动向量（与左摇杆叠加）
                if abs(rx) > 0.2 or abs(ry) > 0.2:
                    self.player._joy_rx = rx
                    self.player._joy_ry = ry
                else:
                    self.player._joy_rx = 0.0
                    self.player._joy_ry = 0.0

        except Exception:
            pass  # 手柄拔出等异常静默处理

    def _handle_joystick_button(self, event: pygame.event.Event) -> None:
        """手柄按钮事件 → 映射为键盘按键。"""
        if self._joystick is None:
            return
        if event.type == pygame.JOYBUTTONDOWN:
            btn = event.button
            # A → 空格（射击/确认）
            if btn == 0:
                new_ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE)
                self._handle_keydown(new_ev)
            # B → ESC（暂停/取消）
            elif btn == 1:
                new_ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
                self._handle_keydown(new_ev)
            # X → R（重新开始）
            elif btn == 2:
                if self.state in (GameState.GAME_OVER, GameState.VICTORY):
                    new_ev = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r)
                    self._handle_keydown(new_ev)
            # Y → 聊天快捷消息
            elif btn == 3:
                if self.state == GameState.PLAYING and self.network.is_connected:
                    self._chat_channel = 1 - self._chat_channel
            # LB (左肩) → Tab（聊天频道切换）
            elif btn == 4:
                if self.state == GameState.PLAYING:
                    self._chat_input_active = not self._chat_input_active
                    self._chat_input_buffer = ""
            # RB (右肩) → Enter（发送聊天）
            elif btn == 5:
                if self._chat_input_active and self._chat_input_buffer.strip():
                    text = self._chat_input_buffer.strip()
                    self.network.send_chat(text, channel=self._chat_channel)
                    self._add_chat_history("我", text, self._chat_channel)
                    self._chat_input_active = False
                    self._chat_input_buffer = ""
            # Start → P（暂停）
            elif btn == 7:
                if self.state == GameState.PLAYING:
                    self.state = GameState.PAUSED
                elif self.state == GameState.PAUSED:
                    self.state = GameState.PLAYING
            # D-Pad Up → 菜单上
            elif btn == 11:
                if self.state == GameState.UPGRADE:
                    self._upgrade_selected = max(0, self._upgrade_selected - 1)
            # D-Pad Down → 菜单下
            elif btn == 12:
                if self.state == GameState.UPGRADE:
                    items = self.upgrade_data.get_levels_for_display()
                    self._upgrade_selected = min(len(items) - 1, self._upgrade_selected + 1)
            # D-Pad Left → 快捷消息 1
            elif btn == 13:
                if self.state == GameState.PLAYING and self.network.is_connected:
                    self._handle_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1))
            # D-Pad Right → 快捷消息 2
            elif btn == 14:
                if self.state == GameState.PLAYING and self.network.is_connected:
                    self._handle_keydown(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2))

    def _handle_keyup(self, event: pygame.event.Event) -> None:
        if self.state == GameState.PLAYING:
            self.player.handle_keyup(event)
            # ⭐ 松开空格 → 发射蓄力强击（如果有蓄力）
            if event.key == pygame.K_SPACE:
                charge = self.player.charge_level
                if charge >= 0.40:  # 至少双发阈值
                    new_bullets = self.player.fire()
                    for bullet in new_bullets:
                        self.bullets.add(bullet)
                        self.all_sprites.add(bullet)
                    self.audio.play_shoot()
                    # 网络同步
                    if self.network.is_connected and self._my_room:
                        self.network.send_shoot(
                            float(self.player.rect.centerx),
                            float(self.player.rect.top),
                            charge,
                        )

    def _handle_name_input(self, event: pygame.event.Event) -> None:
        """处理姓名输入（GAME_OVER / VICTORY 子状态）。"""
        if event.key == pygame.K_RETURN:
            name = self._name_buffer.strip() or "无名"
            entry = self.leaderboard.add_score(name, self.collision.score)
            print(f"[GAME] 📝 排行榜已保存: {name} = {self.collision.score} (上榜={entry is not None})")
            self._entering_name = False
            self._name_buffer = ""
            self._go_to_upgrade()  # ⭐ 先去升级界面
        elif event.key in (pygame.K_ESCAPE, pygame.K_q):
            self._entering_name = False
            self._name_buffer = ""
            self._go_to_upgrade()
        elif event.key == pygame.K_r:
            # 取消姓名输入，直接重新开始
            self._entering_name = False
            self._name_buffer = ""
            self._start_game()
        elif event.key == pygame.K_BACKSPACE:
            self._name_buffer = self._name_buffer[:-1]
        elif event.key == pygame.K_SPACE:
            self._name_buffer += " "

    def _handle_menu_click(self, pos: tuple[int, int]) -> None:
        """处理菜单画面的鼠标点击。"""
        mx, my = pos
        for rect, label, action in self._menu_buttons:
            if rect.collidepoint(mx, my):
                if action == "start":
                    self._start_game()
                elif action == "quit":
                    self.running = False
                elif action == "net":
                    self._toggle_network()
                elif action == "create":
                    if self.network.is_connected:
                        self._entering_password = True
                        self._password_buffer = ""
                    else:
                        print("[MENU] ⚠ 请先连接服务器 (F10)")
                elif action == "join":
                    if self.network.is_connected and self._room_list:
                        r = self._room_list[0]
                        if r.get("has_password"):
                            self._entering_password = True
                            self._password_buffer = ""
                            self._join_target_rid = r.get("id", "")
                        else:
                            self._room_join_first("")
                    elif not self.network.is_connected:
                        print("[MENU] ⚠ 请先连接服务器 (F10)")
                elif action == "ready":
                    if self.network.is_connected:
                        self.network.send_room_ready()
                elif action == "leave":
                    if self.network.is_connected:
                        self.network.send_room_leave()
                        self._my_room = None
                        self._room_list_dirty = True
                elif action == "refresh":
                    if self.network.is_connected:
                        self.network.send_room_list()
                        self._room_list_dirty = True
                return

    def _handle_name_text(self, event: pygame.event.Event) -> None:
        """处理姓名输入的文字（TEXTINPUT 事件）。"""
        if len(self._name_buffer) >= 12:
            return
        char = event.text
        if char.isprintable() and char not in ('\r', '\n', '\t'):
            self._name_buffer += char

    def _handle_password_text(self, event: pygame.event.Event) -> None:
        """处理密码输入的文字。"""
        if len(self._password_buffer) >= 12:
            return
        char = event.text
        if char.isprintable() and char not in ('\r', '\n', '\t', ' '):
            self._password_buffer += char

    # ================================================================
    # 更新逻辑（状态感知）
    # ================================================================

    def update(self) -> None:
        self.frame_count += 1

        # 异步事件处理（题4：上帧排队的事件在本帧执行）
        self._event_bus.flush_async()

        # 房间列表自动刷新（连接后每 3 秒查一次）
        if self.network.is_connected and self.state == GameState.MENU:
            self._room_timer += self.dt
            if self._room_timer > 2.0 or self._room_list_dirty:
                self._room_timer = 0.0
                self.network.send_room_list()
                self._room_list_dirty = False

        # FPS 追踪
        self._track_fps(self.dt)

        # 背景始终滚动（菜单/暂停也有动态感）
        self.background.update(self.dt)

        # ⭐ 粒子特效更新
        self.particles.update(self.dt)

        # 菜单闪烁计时器
        self._menu_blink += self.dt
        if self._menu_blink > 2.0:
            self._menu_blink -= 2.0

        # 屏幕震动衰减
        if self._screen_shake > 0:
            self._screen_shake = max(0.0, self._screen_shake - self.dt * 20)

        # ⭐ 关卡通提示动画
        if self._level_transition_timer > 0:
            self._level_transition_timer -= self.dt
            # 透明度：先闪入再渐出
            if self._level_transition_timer > 2.0:
                self._level_transition_alpha = min(200,
                    self._level_transition_alpha + self.dt * 300)
            elif self._level_transition_timer < 1.5:
                self._level_transition_alpha = max(0,
                    self._level_transition_alpha - self.dt * 150)
            # 文字缩放动画：从 0 → 1.2 → 1.0
            if self._level_transition_timer > 2.0:
                self._level_transition_scale = min(1.2,
                    self._level_transition_scale + self.dt * 1.5)
            else:
                self._level_transition_scale = max(0.8,
                    self._level_transition_scale - self.dt * 0.3)
            if self._level_transition_timer <= 0:
                self._level_transition_timer = 0
                self._level_transition_alpha = 0
                self._level_transition_text = ""

        # ── 远程玩家位置插值平滑（题10）──
        if (self._remote_player_pos and self._remote_display_pos
                and self.state == GameState.PLAYING):
            tx, ty = self._remote_player_pos
            dx, dy = self._remote_display_pos
            lerp_factor = min(1.0, self._remote_lerp_speed * self.dt)
            nx = dx + (tx - dx) * lerp_factor
            ny = dy + (ty - dy) * lerp_factor
            self._remote_display_pos = (nx, ny)

        # ── 射击反馈浮动文字更新（题11）──
        for fb in self._shot_feedbacks:
            fb["timer"] -= self.dt
            fb["y"] -= 40 * self.dt  # 向上飘
        self._shot_feedbacks = [fb for fb in self._shot_feedbacks if fb["timer"] > 0]

        # ---- Boss 死亡序列（题19：独立状态，即使在 GAME_OVER 也会完成） ----
        if self._boss_dying:
            self._boss_dying_timer += self.dt
            while self._boss_dying_positions and self._boss_dying_timer >= BOSS_EXPLOSION_DELAY:
                self._boss_dying_timer -= BOSS_EXPLOSION_DELAY
                pos = self._boss_dying_positions.pop(0)
                exp = Explosion(pos[0], pos[1], "huge")
                self.explosions.add(exp)
                self.all_sprites.add(exp)
                self.audio.play_explosion()
            # 更新爆炸动画
            self.explosions.update(self.dt)
            if not self._boss_dying_positions:
                self._boss_dying = False
                if self._boss_dying_level >= FINAL_BOSS_LEVEL:
                    self.state = GameState.VICTORY
                    self.audio.stop_bgm()

        # 仅 PLAYING 状态更新游戏逻辑
        if self.state != GameState.PLAYING:
            if self.state in (GameState.GAME_OVER, GameState.VICTORY):
                self.ui.update(self.dt, self.collision.score)
            return

        # ---- 保存更新前精灵集合（用于追踪被 kill 的精灵 rect）----
        if self._use_dirty_rects:
            _pre_sprites: set = set(self.all_sprites.sprites())

        # ---- 波次/关卡推进（⭐ 波次制替代分数制） ----
        if self.spawner.level_complete:
            new_level = self.spawner.level + 1
            if new_level > FINAL_BOSS_LEVEL:
                # 通关第9关 → 胜利
                self.state = GameState.VICTORY
                self._event_bus.publish(Event(GameEvent.GAME_OVER, {
                    "victory": True, "score": self.collision.score,
                }))
                self.audio.stop_bgm()
            else:
                self.spawner.set_level(new_level)
                self.collision.current_level = new_level  # ⭐ 同步关卡到碰撞系统
                self._event_bus.publish(Event(GameEvent.LEVEL_UP, {
                    "level": new_level, "score": self.collision.score,
                }))
                self.particles.level_up_ring(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
                if self.background.set_theme_by_level(new_level):
                    gl = GameLogger.get_instance()
                    gl.info("背景主题切换", level=new_level,
                            theme=self.background.current_theme.name)
                self._level_transition_alpha = 200
                self._level_transition_timer = 2.5
                self._level_transition_text = f"—— 第 {new_level} 关 ——"
                self._level_transition_scale = 0.0
                self._screen_shake = max(self._screen_shake, 4.0)

        # ---- 生成敌机 / Boss ----
        new_boss = self.spawner.update(self.dt, self.enemies, self.all_sprites)
        if new_boss is not None:
            self._boss = new_boss
            self._boss.set_player(self.player)

        # ⭐ 玩家自动连射
        auto_bullets = self.player.update_auto_fire(self.dt)
        for b in auto_bullets:
            self.bullets.add(b)
            self.all_sprites.add(b)

        # ⭐ 引擎尾焰粒子（玩家底部中心）
        self.particles.set_engine(
            True,
            float(self.player.rect.centerx),
            float(self.player.rect.bottom),
        )

        # ⭐ 手柄输入处理（每帧更新）
        self._handle_joystick()

        # ---- Boss 弹幕 ----
        if self._boss is not None and self._boss.alive():
            boss_bullets = self._boss.fire(self.dt)
            for b in boss_bullets:
                self.bullets.add(b)
                self.all_sprites.add(b)

        # ⭐ 敌机弹幕：遍历所有存活敌机，收集其发射的子弹
        for enemy in self.enemies:
            if not enemy.alive():
                continue
            enemy_bullets = enemy.fire(self.dt)
            for b in enemy_bullets:
                self.bullets.add(b)
                self.all_sprites.add(b)

        # ---- 更新精灵 ----
        self.all_sprites.update(self.dt)

        # ── 网络同步：发送 MOVE（仅当在房间+游戏中，每 N 帧，位移 > 0.5px）──
        if (self.network.is_connected and self._my_room
                and self.frame_count % self._net_send_interval == 0):
            px = float(self.player.rect.centerx)
            py = float(self.player.rect.centery)
            dx = px - self._last_sent_x
            dy = py - self._last_sent_y
            if abs(dx) > 0.5 or abs(dy) > 0.5:
                self.network.send_move(px, py, dx, dy)
                self._last_sent_x = px
                self._last_sent_y = py

        # ---- 碰撞检测 ----
        _hp_before = self.player.hp
        alive: bool = self.collision.handle_all(
            self.bullets, self.enemies, self.player,
            dt=self.dt if self.dt > 0 else 1.0 / 60.0,
        )
        # ── 网络同步：击杀敌人时通知服务器加分 ──
        if self.network.is_connected and self._my_room and self.collision.kills_this_frame > 0:
            for _ in range(self.collision.kills_this_frame):
                self.network.send_hit(
                    target_id=0,
                    damage=10,  # 每个击杀 +10 分
                    x=float(self.player.rect.centerx),
                    y=float(self.player.rect.centery),
                )
            print(f"[GAME] ⚔ 击杀 {self.collision.kills_this_frame} 敌机 → +{self.collision.kills_this_frame * 10}分")
        # Boss 击毁检测（题19：启动连续爆炸死亡序列）
        if self.collision.boss_defeated:
            self.spawner.on_boss_defeated()
            self._boss_dying = True
            self._boss_dying_positions = list(self.collision.boss_death_positions)
            self._boss_dying_timer = 0.0
            self._boss_dying_level = self.spawner.level
            self._boss = None
            self.audio.play_explosion()
            self._event_bus.publish(Event(GameEvent.ENEMY_KILLED, {
                "is_boss": True, "score": 1000, "level": self.spawner.level,
            }))

        # 生成爆炸
        if self.collision.explosion_positions:
            self.audio.play_explosion()
        for pos in self.collision.explosion_positions:
            esize = pos[2] if len(pos) > 2 else "normal"
            exp = Explosion(pos[0], pos[1], esize)
            # ⭐ 通知 spawner 记录击杀（用于波次清空检测）
            self.spawner.on_enemy_killed()
            if esize == "big":
                self._screen_shake = max(self._screen_shake, 3)
            elif esize == "huge":
                self._screen_shake = max(self._screen_shake, 8)
            else:
                self._screen_shake = max(self._screen_shake, 1.5)
            self.explosions.add(exp)
            self.all_sprites.add(exp)
            # ⭐ 粒子爆发
            self.particles.burst_explosion(pos[0], pos[1], esize)
            # Boss 死亡额外粒子爆发
            if esize == "huge":
                self.particles.boss_death(pos[0], pos[1])
            self._event_bus.publish_async(Event(GameEvent.ENEMY_KILLED, {
                "is_boss": False, "size": esize,
                "x": pos[0], "y": pos[1],
            }))
        # ⭐ 命中火花：粒子爆发 + 屏幕震动
        for sx, sy, intensity in self.collision.hit_sparks:
            self.particles.hit_spark(sx, sy, intensity)
            self._screen_shake = max(self._screen_shake, 1.0)
        # 飘字得分
        for x, y, sv in self.collision.floating_texts:
            self.ui.add_score_text(x, y, sv)
            self._event_bus.publish_async(Event(GameEvent.SCORE_CHANGED, {
                "amount": sv, "total": self.collision.score,
            }))
        # ⭐ Combo 加分飘字（金色）
        for cx, cy, bonus in self.collision.combo_bonus_texts:
            self.ui.add_pickup_text(cx, cy, f"+{bonus}", (255, 215, 80))

        # ⭐ Combo 断开提示
        if self.collision.combo_just_broke and self.collision.combo_peak >= 3:
            sw = SCREEN_WIDTH
            self.particles.burst(sw // 2, SCREEN_HEIGHT // 2 - 30,
                                 count=8, speed=100, gravity=0, lifetime=0.6,
                                 colors=[(255, 80, 80), (255, 150, 50)],
                                 size_range=(3, 6), spread=2 * math.pi)

        # ---- 道具掉落生成（题18） ----
        for dx, dy, ptype in self.collision.drops:
            pu = PowerUp(dx, dy, ptype)
            self.powerups.add(pu)
            self.all_sprites.add(pu)

        # ---- 道具拾取检测 ----
        self._handle_powerup_collection()

        if not alive:
            self.state = GameState.GAME_OVER
            self._event_bus.publish(Event(GameEvent.GAME_OVER, {
                "score": self.collision.score, "level": self.ui.current_level,
            }))

        # ---- 收集被 kill 的精灵 rect（用于 dirty rect clean-up）----
        if self._use_dirty_rects:
            self._killed_rects.clear()
            for s in _pre_sprites:
                if not s.alive():
                    self._killed_rects.append(s.rect.copy())

        # ---- UI 更新 ----
        self.ui.update(self.dt, self.collision.score)

        # ⭐ 回放录制：记录当前帧玩家输入
        if self._replay_recorder.is_recording:
            self._replay_recorder.record_frame(self.frame_count, self.player)

        # ⭐ 回放播放：应用录制的输入到玩家
        if self._replay_player is not None and self._replay_player.is_playing:
            inp = self._replay_player.play_frame(self.frame_count)
            if inp is not None:
                inp.apply_to(self.player)
                self._replay_status_text = (
                    f"▶ 回放 {self._replay_player.progress * 100:.0f}%"
                )
            else:
                self._replay_player = None
                self._replay_status_text = "⏹ 回放结束"
                gl = GameLogger.get_instance()
                gl.info("回放播放完成")
                print(f"[REPLAY] ⏹ 回放播放完成")

    # ================================================================
    # 道具拾取处理（题18）
    # ================================================================

    def _handle_powerup_collection(self) -> None:
        """检测玩家与道具碰撞，触发效果 + 飘字反馈。"""
        hits: list[PowerUp] = pygame.sprite.spritecollide(
            self.player, self.powerups, dokill=True
        )
        from settings import POWERUP_COLORS
        _PICKUP_LABELS: dict[PowerUpType, str] = {
            PowerUpType.HEALTH: "+1 HP",
            PowerUpType.BOMB: "💣 +1",
            PowerUpType.DOUBLE_DAMAGE: "双倍伤害",
            PowerUpType.TRIPLE_SPREAD: "三向散射",
            PowerUpType.PIERCE: "穿透弹",
            PowerUpType.RAPID_FIRE: "快速蓄力",
        }
        for pu in hits:
            result = self.player.apply_powerup(pu.powerup_type)
            # 拾取飘字
            label = _PICKUP_LABELS.get(pu.powerup_type, "")
            if result == "bomb_full":
                label = "💣 MAX"
            if label:
                color = POWERUP_COLORS.get(pu.powerup_type, WHITE)
                if result == "bomb_full":
                    color = (80, 80, 80)
                self.ui.add_pickup_text(pu.rect.centerx, pu.rect.centery, label, color)
            # 拾取光圈
            glow = Explosion(pu.rect.centerx, pu.rect.centery, "normal")
            self.explosions.add(glow)
            self.all_sprites.add(glow)
            # ⭐ 粒子光晕
            pu_color = POWERUP_COLORS.get(pu.powerup_type, (100, 255, 100))
            self.particles.pickup_glow(pu.rect.centerx, pu.rect.centery, pu_color)

            if result == "bomb":
                pass  # 已通过飘字显示 💣 +1
            elif result == "health":
                self.audio.play_shoot()
            elif result == "buff":
                self.audio.play_shoot()

    def _trigger_bomb(self) -> None:
        """清屏炸弹：消灭所有敌机，生成爆炸 + 闪屏 + 震屏。"""
        self.ui.trigger_bomb_flash()
        self._screen_shake = max(self._screen_shake, 6)
        for enemy in list(self.enemies):
            if enemy.alive() and not isinstance(enemy, BossEnemy):
                self.collision.score += enemy.score_value
                self.collision.floating_texts.append(
                    (enemy.rect.centerx, enemy.rect.centery, enemy.score_value)
                )
                exp = Explosion(enemy.rect.centerx, enemy.rect.centery, "big")
                self.explosions.add(exp)
                self.all_sprites.add(exp)
                enemy.kill()
        # Boss 受到重大伤害但不直接死亡
        if self._boss is not None and self._boss.alive():
            self._boss.take_damage(15)
            exp = Explosion(self._boss.rect.centerx, self._boss.rect.centery, "big")
            self.explosions.add(exp)
            self.all_sprites.add(exp)
        self.audio.play_explosion()
        self._event_bus.publish(Event(GameEvent.BOMB_TRIGGERED, {
            "enemies_cleared": sum(1 for e in list(self.enemies) if e.alive()),
        }))

    # ================================================================
    # 渲染（状态感知）
    # ================================================================

    def render(self) -> None:
        self.screen.fill(BLACK)
        self.background.draw(self.screen)
        # ⭐ 粒子特效渲染（在最底层，背景之上、精灵之下）
        self.particles.draw(self.screen)

        # ── 游戏画面（PLAYING / PAUSED / GAME_OVER / VICTORY 都显示）──
        if self.state not in (GameState.MENU,):
            if self._use_dirty_rects and self.state == GameState.PLAYING:
                self._render_dirty_rects()
            else:
                self._render_full()

        # ── 状态专属界面 ──
        if self.state == GameState.MENU:
            self._draw_menu_screen()
        elif self.state == GameState.PAUSED:
            self._draw_pause_overlay()
        elif self.state == GameState.GAME_OVER:
            self._draw_game_over()
        elif self.state == GameState.VICTORY:
            self._draw_victory()
        elif self.state == GameState.UPGRADE:
            render_upgrade_screen(
                self.screen, self.upgrade_data,
                self._upgrade_selected,
                self._upgrade_show_levelup, self._upgrade_levelup_count,
            )

        # ── FPS 显示（右上角，所有状态可见，必须在 flip/update 之前绘制）──
        self._draw_fps()

        # 屏幕震动效果
        if self._screen_shake > 0:
            import random
            sx = int(random.uniform(-1, 1) * self._screen_shake)
            sy = int(random.uniform(-1, 1) * self._screen_shake)
            shaken = self.screen.copy()
            self.screen.fill(BLACK)
            self.screen.blit(shaken, (sx, sy))

        # ⭐ 关卡通提示：闪屏 + 大字
        if self._level_transition_timer > 0 and self._level_transition_alpha > 0:
            # 全屏闪白
            flash = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            flash_alpha = min(180, int(self._level_transition_alpha * 0.6))
            flash.fill((255, 255, 255, flash_alpha))
            self.screen.blit(flash, (0, 0))
            # 大字 "第 N 关"
            try:
                big_font = pygame.font.Font(UI_FONT_PATH, max(36, int(60 * self._level_transition_scale)))
            except Exception:
                big_font = pygame.font.Font(None, max(36, int(60 * self._level_transition_scale)))
            # 根据背景主题用不同颜色
            theme = self.background.current_theme
            text_color = theme.accent_color if hasattr(theme, 'accent_color') else (100, 200, 255)
            text_surf = big_font.render(self._level_transition_text, True, text_color)
            text_rect = text_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 20))
            # 发光效果
            glow_surf = big_font.render(self._level_transition_text, True, (255, 255, 255))
            glow_surf.set_alpha(40)
            glow_rect = glow_surf.get_rect(center=(SCREEN_WIDTH // 2 + 3, SCREEN_HEIGHT // 2 - 17))
            self.screen.blit(glow_surf, glow_rect)
            self.screen.blit(text_surf, text_rect)

        self._draw_log_panel()
        self._draw_chat_ui()  # 聊天系统 UI（题13）
        # ⭐ 性能分析叠加显示
        self._profiler.draw(self.screen)
        pygame.display.flip()

    def _render_full(self) -> None:
        """全屏渲染（PAUSED / GAME_OVER 或 F3 切换关闭脏矩形时使用）。"""
        if not self.player.is_invincible or self.frame_count % 8 < 4:
            self.all_sprites.draw(self.screen)
        else:
            for sprite in self.all_sprites:
                if sprite != self.player:
                    self.screen.blit(sprite.image, sprite.rect)

        self.player.draw_charge_bar(self.screen)
        self.player.draw_powerup_glow(self.screen)
        self.player.draw_hitbox(self.screen)

        if self._boss is not None and self._boss.alive():
            self._boss.draw_hp_bar(self.screen)

        self.ui.render(
            self.screen, self.player, self.collision.score,
            len(self.enemies), self.spawner.type_counts,
            network_status=self.network.status_text() if self.network.running else "",
            network_color=self.network.status_color() if self.network.running else RED,
        )

        # ── 团队积分 / 计时器 ──
        self._draw_team_hud()
        # ── 波次信息 ──
        self._draw_wave_info()
        # ── 远程玩家 ──
        self._draw_remote_player()

    def _draw_remote_player(self) -> None:
        """在屏幕上绘制远程玩家的位置标记（使用插值平滑位置）。"""
        if not self._remote_display_pos:
            return
        if self.state != GameState.PLAYING:
            return
        rx, ry = self._remote_display_pos
        import math, time
        t = time.time()
        # 脉冲绿圈 + 十字
        pulse = abs(math.sin(t * 3))
        color = (0, int(200 + 55 * pulse), int(80 + 40 * pulse))
        pygame.draw.circle(self.screen, color, (int(rx), int(ry)), 14, width=2)
        pygame.draw.line(self.screen, color, (int(rx)-10, int(ry)), (int(rx)+10, int(ry)), 2)
        pygame.draw.line(self.screen, color, (int(rx), int(ry)-10), (int(rx), int(ry)+10), 2)

    def _draw_shot_feedbacks(self) -> None:
        """绘制服务器射击结果反馈浮动文字（题11）。"""
        if not self._shot_feedbacks:
            return
        font = pygame.font.Font(UI_FONT_PATH, 18)
        for fb in self._shot_feedbacks:
            alpha = min(255, int(fb["timer"] * 255 / 1.2))
            text_surf = font.render(fb["text"], True, fb["color"])
            if alpha < 255:
                text_surf.set_alpha(alpha)
            self.screen.blit(text_surf, (int(fb["x"]) - text_surf.get_width() // 2,
                                         int(fb["y"])))

    def _draw_team_hud(self) -> None:
        """绘制团队积分和倒计时（PLAYING 状态 + 房间游戏中）。"""
        if not self._in_room_game:
            return
        font = pygame.font.Font(UI_FONT_PATH, 22)
        cx = SCREEN_WIDTH // 2
        # 倒计时
        if self._game_timer_remaining > 0:
            mins = int(self._game_timer_remaining // 60)
            secs = int(self._game_timer_remaining % 60)
            color = RED if self._game_timer_remaining < 30 else YELLOW
            t = font.render(f"⏱ {mins}:{secs:02d}", True, color)
            self.screen.blit(t, (cx - t.get_width() // 2, 4))
        # 队伍积分
        score_text = f"A队 {self._team_score_a}  :  {self._team_score_b} B队"
        t2 = font.render(score_text, True, CYAN)
        self.screen.blit(t2, (cx - t2.get_width() // 2, 28))
        # 战斗结果
        if self._battle_result:
            winner = self._battle_result.get("winner", "?")
            result_text = f"🏆 {'A队胜' if winner == 'A' else 'B队胜' if winner == 'B' else '平局'}"
            big_font = pygame.font.Font(UI_FONT_PATH, 36)
            t3 = big_font.render(result_text, True, YELLOW)
            self.screen.blit(t3, (cx - t3.get_width() // 2, SCREEN_HEIGHT // 2 - 60))
            # ── 战后统计 ──
            stats = self._battle_result.get("stats", [])
            small = pygame.font.Font(UI_FONT_PATH, 18)
            sy = SCREEN_HEIGHT // 2 - 20
            for s in stats:
                cid = s.get("cid", "?")
                kills = s.get("kills", 0)
                deaths = s.get("deaths", 0)
                line = f"  Player#{cid}: 击杀 {kills}  死亡 {deaths}"
                t4 = small.render(line, True, (200, 200, 200))
                self.screen.blit(t4, (cx - t4.get_width() // 2, sy))
                sy += 22
            hint = small.render("按 ESC 返回主菜单", True, (150, 150, 150))
            self.screen.blit(hint, (cx - hint.get_width() // 2, sy + 10))

    def _render_dirty_rects(self) -> None:
        """脏矩形优化渲染（PLAYING 状态专用）。

        clear/draw/update 完整循环：
          1. clear()  → 擦除精灵旧位置（bg_callback 局部重绘星空）
          2. draw()   → Laye-dirty 精灵 → 敌机 → 子弹 → 玩家 → Boss → 爆炸
          3. 叠加 UI 元素（蓄力条/Boss血条/HUD/飘字）
          4. display.update(all_rects) → 只刷新变化的屏幕区域
        """
        # ① 擦除旧精灵位置 → 恢复为背景
        # pygame 2.6.1 LayeredDirty.draw expects a Surface bgd, not a callback.
        clear_rects: list[pygame.Rect] = self.all_sprites.clear(
            self.screen, self.screen
        )

        # ② 擦除已销毁精灵的旧位置（killed 后已不在 all_sprites 中，需手动清理）
        for rect in self._killed_rects:
            self._bg_callback(self.screen, rect)
        killed_clip = [r.clip(self.screen.get_rect()) for r in self._killed_rects
                       if r.clip(self.screen.get_rect()).width > 0]

        # ③ 绘制 dirty 精灵（按 layer 顺序：敌机→子弹→玩家→Boss→爆炸）
        if not self.player.is_invincible or self.frame_count % 8 < 4:
            draw_rects = self.all_sprites.draw(self.screen)
        else:
            player_was_dirty = self.player.dirty
            self.player.dirty = 0
            draw_rects = self.all_sprites.draw(self.screen)
            self.player.dirty = player_was_dirty

        # ④ 叠加 UI 元素
        self.player.draw_charge_bar(self.screen)
        self.player.draw_powerup_glow(self.screen)
        self.player.draw_hitbox(self.screen)
        charge_rect = pygame.Rect(
            self.player.rect.left - 1,
            self.player.rect.top - 15,
            self.player.rect.width + 55,
            22,
        )

        if self._boss is not None and self._boss.alive():
            self._boss.draw_hp_bar(self.screen)
            boss_rect = pygame.Rect(
                (SCREEN_WIDTH - 320) // 2 - 2, 0, 326, 24
            )
        else:
            boss_rect = None

        # HUD 区域（左上角固定区域，增高以容纳叠加道具显示）
        hud_rect = pygame.Rect(0, 0, 250, 230)
        self.ui.render(
            self.screen, self.player, self.collision.score,
            len(self.enemies), self.spawner.type_counts,
            network_status=self.network.status_text() if self.network.running else "",
            network_color=self.network.status_color() if self.network.running else RED,
            combo_text=self.collision.combo_display_text,
            combo_count=self.collision.combo_count,
            combo_multiplier=self.collision.combo_multiplier,
        )

        # ── 团队积分 / 计时器 ──
        self._draw_team_hud()
        # ── 波次信息 ──
        self._draw_wave_info()
        # ── 远程玩家 ──
        self._draw_remote_player()

        # ── 射击反馈浮动文字（题11）──
        self._draw_shot_feedbacks()

        # 飘字区域
        ft_rects: list[pygame.Rect] = []
        for ft in self.ui.floating_texts:
            ft_rects.append(pygame.Rect(int(ft.x) - 35, int(ft.y) - 12, 70, 24))

        # ⑤ clear/draw 流程保证了精灵旧位置擦除 + 层级排序 + dirty 追踪
        #    最终 flip 由 render() 统一调用，确保 FPS 文字等也一并刷新

    def _draw_wave_info(self) -> None:
        """在屏幕右上角显示关卡/波次信息。"""
        if self.state not in (GameState.PLAYING, GameState.PAUSED):
            return
        s = self.spawner
        if s.total_waves <= 0:
            return
        try:
            font = pygame.font.Font(UI_FONT_PATH, 18)
        except Exception:
            font = pygame.font.Font(None, 18)
        level_text = font.render(f"第 {s.level} 关", True, (200, 220, 255))
        lr = level_text.get_rect(topright=(SCREEN_WIDTH - 12, 8))
        self.screen.blit(level_text, lr)
        if s.all_waves_done:
            wave_str = "⚔ BOSS" if s.boss_active else "✓ 通关"
        elif s.is_resting:
            wave_str = f"波次 {s.current_wave + 1}/{s.total_waves} ⏳"
        else:
            wave_str = f"波次 {s.current_wave + 1}/{s.total_waves}"
        wave_color = (100, 255, 100) if s.is_resting else (255, 220, 100)
        wave_text = font.render(wave_str, True, wave_color)
        wr = wave_text.get_rect(topright=(SCREEN_WIDTH - 12, 30))
        self.screen.blit(wave_text, wr)
        remaining = len(self.enemies) + (len(s._spawn_queue) if hasattr(s, '_spawn_queue') else 0)
        if remaining > 0 and not s.all_waves_done:
            rem_text = font.render(f"残敌 {remaining}", True, (180, 180, 200))
            rr = rem_text.get_rect(topright=(SCREEN_WIDTH - 12, 50))
            self.screen.blit(rem_text, rr)

    def _draw_fps(self) -> None:
        """在屏幕左上角绘制 FPS、脏矩形状态和 ⭐ 回放状态。"""
        font = pygame.font.Font(UI_FONT_PATH, 16)
        fps_text = f"FPS: {self._fps_display:.0f}"
        color = GREEN if self._fps_display >= 55 else (YELLOW if self._fps_display >= 30 else RED)
        surf = font.render(fps_text, True, color)
        self.screen.blit(surf, (SCREEN_WIDTH - 90, 4))

        mode = "DirtyRect" if self._use_dirty_rects else "Full"
        mode_surf = font.render(mode, True, (150, 150, 150))
        self.screen.blit(mode_surf, (SCREEN_WIDTH - 90, 20))

        # ⭐ 回放状态
        if self._replay_status_text:
            replay_surf = font.render(self._replay_status_text, True, (100, 255, 100))
            self.screen.blit(replay_surf, (SCREEN_WIDTH - 200, 36))

    # ================================================================
    # 主菜单界面
    # ================================================================

    def _draw_menu_screen(self) -> None:
        """绘制主菜单界面（优化版：更清晰的视觉层次）"""
        # 半透明遮罩
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH // 2
        font_title = pygame.font.Font(UI_FONT_PATH, 56)
        font_text  = pygame.font.Font(UI_FONT_PATH, 22)
        font_hint  = pygame.font.Font(UI_FONT_PATH, 30)

        # ── 标题（带阴影增加立体感）──
        draw_text_centered(self.screen, "飞机大战", (cx, 120), font_title,
                           ACCENT_GOLD, shadow=True, shadow_color=(80, 60, 0))

        # 副标题
        sub = font_text.render("—  Shmup  —", True, ACCENT_CYAN)
        self.screen.blit(sub, sub.get_rect(center=(cx, 172)))

        # ── 装饰分隔线 ──
        draw_separator(self.screen, 200, cx - 120, cx + 120, PANEL_BORDER_LIGHT)

        # ── 操作说明（紧凑卡片）──
        instr_y = 220
        label_font = pygame.font.Font(UI_FONT_PATH, 18)
        card_w, card_h = 300, 135
        draw_panel(self.screen, (cx - card_w // 2, instr_y - 8, card_w, card_h), alpha=180)

        draw_text_centered(self.screen, "操作说明", (cx, instr_y + 6), label_font, TEXT_NORMAL)
        instr_y += 28
        controls = [
            ("WASD / 方向键", "移动"),
            ("Shift", "加速"),
            ("Space (长按蓄力)", "射击"),
            ("P / ESC", "暂停"),
        ]
        for key_name, action in controls:
            line = label_font.render(f"{key_name}  →  {action}", True, TEXT_DIM)
            self.screen.blit(line, line.get_rect(center=(cx, instr_y)))
            instr_y += 24

        # ── 排行榜（右侧面板）──
        self._draw_leaderboard_panel(instr_y + 10)

        # ── 房间信息面板（左侧）──
        self._draw_room_panel(instr_y + 10)

        # ── 密码输入对话框 ──
        if self._entering_password:
            self._draw_password_dialog(cx)

        # ── 按钮区域 ──
        self._menu_buttons.clear()
        btn_font = pygame.font.Font(UI_FONT_PATH, 24)
        btn_y = 520
        btn_gap = 42
        btn_w, btn_h = 240, 36

        def _draw_btn(label: str, action: str, y_pos: int, accent: tuple):
            r = pygame.Rect(cx - btn_w // 2, y_pos, btn_w, btn_h)
            hover = r.collidepoint(pygame.mouse.get_pos())
            # 按钮背景
            if hover:
                bg = (accent[0] // 4, accent[1] // 4, accent[2] // 4, 200)
            else:
                bg = (20, 20, 35, 180)
            b_surf = pygame.Surface((btn_w, btn_h), pygame.SRCALPHA)
            b_surf.fill(bg)
            border_color = accent if hover else (60, 65, 85)
            pygame.draw.rect(b_surf, border_color, (0, 0, btn_w, btn_h), width=2)
            t = btn_font.render(label, True, accent if hover else TEXT_NORMAL)
            tx = (btn_w - t.get_width()) // 2
            ty = (btn_h - t.get_height()) // 2
            b_surf.blit(t, (tx, ty))
            self.screen.blit(b_surf, (r.x, r.y))
            self._menu_buttons.append((r, label, action))

        _draw_btn("开始游戏", "start", btn_y, ACCENT_GOLD)
        btn_y += btn_gap
        net_label = f"{'断开' if self.network.is_connected else '连接服务器 (F10)'}"
        net_color = GREEN if self.network.is_connected else TEXT_DIM
        _draw_btn(net_label, "net", btn_y, net_color)
        btn_y += btn_gap

        # 房间按钮
        room_ok = self.network.is_connected
        room_color = ACCENT_CYAN if room_ok else (80, 80, 95)
        _draw_btn("创建房间 (R)", "create", btn_y, room_color)
        btn_y += btn_gap
        _draw_btn("加入房间 (J)", "join", btn_y, room_color)
        btn_y += btn_gap

        if self._my_room:
            _draw_btn("准备/取消 (Y)", "ready", btn_y, ACCENT_GOLD if room_ok else (80, 80, 95))
            btn_y += btn_gap
            _draw_btn("离开房间 (L)", "leave", btn_y, RED if room_ok else (80, 80, 95))
            btn_y += btn_gap

        _draw_btn("退出游戏", "quit", btn_y, RED)
        btn_y += btn_gap + 6

        # 快捷键提示（底部，极简）
        q_hint = label_font.render("R=创房  J=加入  Y=准备  ESC=返回", True, TEXT_DIM)
        self.screen.blit(q_hint, q_hint.get_rect(center=(cx, btn_y + 8)))

        # 上一局得分（如果刚结束一局）
        if self.collision.score > 0:
            prev = label_font.render(
                f"上一局得分: {self.collision.score}", True, TEXT_DIM
            )
            self.screen.blit(prev, prev.get_rect(center=(cx, btn_y + 28)))

    def _draw_leaderboard_panel(self, start_y: int) -> None:
        """在菜单右侧绘制排行榜面板（带面板背景）。"""
        entries = self.leaderboard.entries

        panel_x = SCREEN_WIDTH - 200
        panel_w = 190
        panel_y = start_y - 8
        line_h = 24
        panel_h = 34 + line_h * max(len(entries), 1) + 10

        # 面板背景
        draw_panel(self.screen, (panel_x, panel_y, panel_w, panel_h), alpha=190)

        font_title = pygame.font.Font(UI_FONT_PATH, 20)
        font_entry = pygame.font.Font(UI_FONT_PATH, 17)

        # 标题
        title = font_title.render("TOP 5", True, ACCENT_GOLD)
        self.screen.blit(title, (panel_x + 10, panel_y + 6))

        # 分隔线
        draw_separator(self.screen, panel_y + 30, panel_x + 10, panel_x + panel_w - 10)

        # 排名列表
        if entries:
            rank_colors = {0: ACCENT_GOLD, 1: (192, 192, 192), 2: ORANGE}
            for i, entry in enumerate(entries):
                ey = panel_y + 36 + i * line_h
                rank_color = rank_colors.get(i, TEXT_DIM)
                rank_surf = font_entry.render(f"#{i + 1}", True, rank_color)
                self.screen.blit(rank_surf, (panel_x + 10, ey))
                name_surf = font_entry.render(entry.name[:8], True, TEXT_NORMAL)
                self.screen.blit(name_surf, (panel_x + 38, ey))
                score_surf = font_entry.render(str(entry.score), True, ACCENT_CYAN)
                score_rect = score_surf.get_rect(topright=(panel_x + panel_w - 10, ey))
                self.screen.blit(score_surf, score_rect)
        else:
            empty = font_entry.render("暂无记录", True, TEXT_DIM)
            self.screen.blit(empty, (panel_x + 10, panel_y + 36))

    def _draw_password_dialog(self, cx: int) -> None:
        """绘制密码输入对话框（带面板背景）。"""
        cy = SCREEN_HEIGHT // 2 - 70
        dw, dh = 320, 140
        dx = cx - dw // 2
        draw_panel(self.screen, (dx, cy, dw, dh), bg_color=(15, 15, 35), border_color=ACCENT_CYAN, border_width=2, alpha=240)

        font = pygame.font.Font(UI_FONT_PATH, 22)
        small = pygame.font.Font(UI_FONT_PATH, 16)
        if self._join_target_rid:
            title_text = f"加入房间 #{self._join_target_rid} — 输入密码"
        else:
            title_text = "创建房间 — 输入密码"
        draw_text_centered(self.screen, title_text, (cx, cy + 20), font, ACCENT_GOLD)

        # 输入框
        input_w, input_h = 240, 32
        ix = cx - input_w // 2
        iy = cy + 50
        pygame.draw.rect(self.screen, (25, 25, 40), (ix, iy, input_w, input_h))
        pygame.draw.rect(self.screen, ACCENT_GOLD, (ix, iy, input_w, input_h), width=2)

        cursor = "|" if int(self._menu_blink * 3) % 2 == 0 else ""
        display = "*" * len(self._password_buffer) + cursor
        t2 = font.render(display or "|", True, TEXT_BRIGHT)
        self.screen.blit(t2, (ix + 8, iy + 4))

        draw_text_centered(self.screen, "ENTER=确认  ESC=取消  空密码=无密码",
                           (cx, cy + 105), small, TEXT_DIM)

    def _draw_room_panel(self, start_y: int) -> None:
        """在菜单左下绘制房间面板（带面板背景）。"""
        panel_x = 6
        panel_w = 280
        line_h = 19
        font_s = pygame.font.Font(UI_FONT_PATH, 14)
        font_h = pygame.font.Font(UI_FONT_PATH, 16)
        y = start_y + 10
        online = self.network.is_connected

        # 面板背景
        panel_h = 190
        draw_panel(self.screen, (panel_x, y, panel_w, panel_h), alpha=190)

        inner_x = panel_x + 10
        draw_text_left(self.screen, "多人房间", (inner_x, y + 4), font_h, ACCENT_CYAN)
        y += 24

        # 状态
        status = f"{self.network.status_text()}" if online else "未连接"
        surf = font_s.render(status, True, GREEN if online else RED)
        self.screen.blit(surf, (inner_x, y)); y += line_h

        if not online:
            self.screen.blit(font_s.render("点「连接服务器」或按 F10", True, TEXT_DIM), (inner_x, y))
            return

        # 我的房间
        if self._my_room:
            room = self._my_room
            rname = room.get("name", "?")
            rid = room.get("id", "?")
            pcount = room.get("player_count", 0)
            ready_n = len(room.get("ready", []))
            self.screen.blit(font_h.render(f"{rname} (#{rid})", True, ACCENT_GOLD), (inner_x, y))
            y += line_h
            self.screen.blit(font_s.render(f"人数:{pcount}/8  准备:{ready_n}", True, TEXT_NORMAL), (inner_x, y))
            y += line_h
            ta = room.get("team_a", [])
            tb = room.get("team_b", [])
            if ta:
                self.screen.blit(font_s.render(f"A队:{ta}", True, (100, 200, 255)), (inner_x, y)); y += line_h
            if tb:
                self.screen.blit(font_s.render(f"B队:{tb}", True, (255, 140, 100)), (inner_x, y)); y += line_h
        else:
            self.screen.blit(font_s.render("未加入房间", True, TEXT_DIM), (inner_x, y)); y += line_h

        y += 2
        if self._room_list:
            draw_text_left(self.screen, "可加入:", (inner_x, y), font_h, TEXT_NORMAL); y += line_h
            for r in self._room_list[:4]:
                lock = "[锁]" if r.get("has_password") else "[ ]"
                line = f"  {lock} #{r['id']} {r['name']} ({r['player_count']}/8)"
                self.screen.blit(font_s.render(line, True, TEXT_DIM), (inner_x, y)); y += line_h
        else:
            self.screen.blit(font_s.render("暂无房间 (按R创建)", True, TEXT_DIM), (inner_x, y)); y += line_h

        y += 4
        self.screen.blit(font_s.render("R=创建  J=加入  Y/SPACE=准备", True, (100, 200, 100)), (inner_x, y))

    # ================================================================
    # 暂停遮罩
    # ================================================================

    def _draw_pause_overlay(self) -> None:
        """绘制暂停遮罩（带居中卡片）"""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        cx, cy = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2

        # 居中卡片
        card_w, card_h = 300, 180
        draw_panel(self.screen, (cx - card_w // 2, cy - card_h // 2, card_w, card_h),
                   bg_color=(15, 15, 30), border_color=PANEL_BORDER_LIGHT, border_width=2, alpha=240)

        font_big = pygame.font.Font(UI_FONT_PATH, 44)
        font_mid = pygame.font.Font(UI_FONT_PATH, 22)
        font_sml = pygame.font.Font(UI_FONT_PATH, 18)

        draw_text_centered(self.screen, "游戏暂停", (cx, cy - 40), font_big,
                           TEXT_BRIGHT, shadow=True, shadow_color=(0, 0, 0))

        # 分隔线
        draw_separator(self.screen, cy - 6, cx - 100, cx + 100, PANEL_BORDER_LIGHT)

        draw_text_centered(self.screen, "按 P / ESC  继续游戏", (cx, cy + 20), font_mid, GREEN)
        draw_text_centered(self.screen, "按 Q  返回主菜单", (cx, cy + 52), font_sml, ORANGE)

    # ================================================================
    # 游戏结束画面
    # ================================================================

    def _draw_game_over(self) -> None:
        """绘制半透明游戏结束画面（带卡片 + 统计数据）"""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        cx = SCREEN_WIDTH // 2
        font_big = pygame.font.Font(UI_FONT_PATH, 52)
        font_mid = pygame.font.Font(UI_FONT_PATH, 28)
        font_sml = pygame.font.Font(UI_FONT_PATH, 20)

        if self._entering_name:
            self._draw_name_entry(cx, font_big, font_mid, font_sml)
            return

        # 居中卡片
        card_w, card_h = 360, 240
        card_y = SCREEN_HEIGHT // 2 - card_h // 2 - 10
        draw_panel(self.screen, (cx - card_w // 2, card_y, card_w, card_h),
                   bg_color=(18, 10, 10), border_color=(120, 50, 50), border_width=2, alpha=240)

        cy = card_y + 30

        # 标题
        draw_text_centered(self.screen, "游戏结束", (cx, cy), font_big,
                           RED, shadow=True, shadow_color=(60, 0, 0))
        cy += 50

        # 分隔线
        draw_separator(self.screen, cy, cx - 130, cx + 130, (100, 50, 50))
        cy += 18

        # 统计数据
        draw_text_centered(self.screen, f"最终得分: {self.collision.score}", (cx, cy), font_mid, ACCENT_GOLD)
        cy += 34
        stats_font = pygame.font.Font(UI_FONT_PATH, 18)
        draw_text_centered(self.screen, f"关卡: {self.ui.current_level}", (cx, cy), stats_font, TEXT_NORMAL)
        cy += 26
        draw_text_centered(self.screen, f"击毁敌机: {self.spawner.total_spawned} 架", (cx, cy), stats_font, TEXT_DIM)
        cy += 36

        # 分隔线
        draw_separator(self.screen, cy, cx - 130, cx + 130, (100, 50, 50))
        cy += 16

        # 操作提示
        if self.leaderboard.is_high_score(self.collision.score):
            draw_text_centered(self.screen, "按 R  录入排行榜", (cx, cy), font_sml, GREEN)
        else:
            draw_text_centered(self.screen, "按 R  重新开始", (cx, cy), font_sml, TEXT_NORMAL)
        cy += 28
        draw_text_centered(self.screen, "按 ESC / Q  返回主菜单", (cx, cy), font_sml, TEXT_DIM)

    def _draw_name_entry(
        self,
        cx: int,
        font_big: pygame.font.Font,
        font_mid: pygame.font.Font,
        font_sml: pygame.font.Font,
    ) -> None:
        """绘制姓名输入界面（带卡片背景）"""
        cy = SCREEN_HEIGHT // 2

        # 卡片背景
        card_w, card_h = 340, 200
        draw_panel(self.screen, (cx - card_w // 2, cy - 100, card_w, card_h),
                   bg_color=(20, 15, 10), border_color=ACCENT_GOLD, border_width=2, alpha=240)

        # 标题
        draw_text_centered(self.screen, "新纪录!", (cx, cy - 70), font_big, ACCENT_GOLD,
                           shadow=True, shadow_color=(80, 60, 0))

        # 分数
        draw_text_centered(self.screen, f"得分: {self.collision.score}", (cx, cy - 20), font_mid, ACCENT_CYAN)

        # 输入提示
        draw_text_centered(self.screen, "请输入您的姓名:", (cx, cy + 15), font_sml, TEXT_NORMAL)

        # 输入框
        input_w, input_h = 260, 36
        input_x = cx - input_w // 2
        input_y = cy + 32
        pygame.draw.rect(self.screen, (25, 25, 40), (input_x, input_y, input_w, input_h))
        pygame.draw.rect(self.screen, ACCENT_GOLD, (input_x, input_y, input_w, input_h), width=2)

        display_text = self._name_buffer
        cursor_visible = int(self._menu_blink * 3) % 2 == 0
        if cursor_visible:
            display_text += "|"
        text_surf = font_sml.render(display_text or "|", True, TEXT_BRIGHT)
        text_rect = text_surf.get_rect(midleft=(input_x + 10, input_y + input_h // 2))
        self.screen.blit(text_surf, text_rect)

        draw_text_centered(self.screen, "ENTER 确认    ESC 跳过", (cx, cy + 78), font_sml, TEXT_DIM)

    # ================================================================
    # 通关胜利界面（题19）
    # ================================================================

    def _draw_victory(self) -> None:
        """绘制通关胜利界面（带卡片 + 统计数据）。"""
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        if self._entering_name:
            cx = SCREEN_WIDTH // 2
            font_big = pygame.font.Font(UI_FONT_PATH, 56)
            font_mid = pygame.font.Font(UI_FONT_PATH, 36)
            font_sml = pygame.font.Font(UI_FONT_PATH, 22)
            self._draw_name_entry(cx, font_big, font_mid, font_sml)
            return

        cx = SCREEN_WIDTH // 2
        font_title = pygame.font.Font(UI_FONT_PATH, 48)
        font_sub = pygame.font.Font(UI_FONT_PATH, 24)
        font_info = pygame.font.Font(UI_FONT_PATH, 20)
        font_hint = pygame.font.Font(UI_FONT_PATH, 22)
        font_sml = pygame.font.Font(UI_FONT_PATH, 18)

        # 居中卡片
        card_w, card_h = 380, 340
        card_y = SCREEN_HEIGHT // 2 - card_h // 2 - 10
        draw_panel(self.screen, (cx - card_w // 2, card_y, card_w, card_h),
                   bg_color=(15, 15, 25), border_color=ACCENT_GOLD, border_width=2, alpha=240)

        cy = card_y + 25

        # 标题（金色 + 脉冲缩放）
        pulse = 1.0 + 0.05 * math.sin(self._menu_blink * 3.0)
        title = font_title.render("恭喜通关!", True, ACCENT_GOLD)
        title = pygame.transform.rotozoom(title, 0, pulse)
        title_rect = title.get_rect(center=(cx, cy + 10))
        # 阴影
        shadow = font_title.render("恭喜通关!", True, (80, 60, 0))
        shadow = pygame.transform.rotozoom(shadow, 0, pulse)
        self.screen.blit(shadow, shadow.get_rect(center=(cx + 2, cy + 12)))
        self.screen.blit(title, title_rect)
        cy += 55

        draw_text_centered(self.screen, "— 你击败了最终 Boss —", (cx, cy), font_sub, ACCENT_CYAN)
        cy += 40

        # 分隔线
        draw_separator(self.screen, cy, cx - 140, cx + 140, ACCENT_GOLD)
        cy += 20

        # 最终数据
        draw_text_centered(self.screen, f"最终得分: {self.collision.score}", (cx, cy), font_info, ACCENT_GOLD)
        cy += 28
        draw_text_centered(self.screen, f"通关关卡: {self.ui.current_level}", (cx, cy), font_info, TEXT_NORMAL)
        cy += 28
        kills = self.spawner.total_spawned
        draw_text_centered(self.screen, f"击毁敌机: {kills} 架", (cx, cy), font_info, TEXT_NORMAL)
        cy += 38

        # 分隔线
        draw_separator(self.screen, cy, cx - 140, cx + 140, ACCENT_GOLD)
        cy += 18

        # 操作提示
        if self.leaderboard.is_high_score(self.collision.score):
            draw_text_centered(self.screen, "按 R  录入排行榜", (cx, cy), font_hint, GREEN)
        else:
            draw_text_centered(self.screen, "按 R  再来一局", (cx, cy), font_hint, TEXT_NORMAL)
        cy += 28
        draw_text_centered(self.screen, "按 ESC  返回主菜单", (cx, cy), font_sml, TEXT_DIM)

    # ================================================================
    # 性能测试（F2：一键生成 N 架敌机用于压测）
    # ================================================================

    def _spawn_stress_test_enemies(self) -> None:
        """在 PLAYING 状态下按 F2 生成 100 架敌机用于 FPS 压测。"""
        if self.state != GameState.PLAYING:
            return
        import random
        types = [NormalEnemy, FastEnemy, EliteEnemy, TrackingEnemy]
        for _ in range(PERF_TEST_ENEMY_COUNT):
            enemy_type = random.choice(types)
            if enemy_type == TrackingEnemy:
                e = TrackingEnemy(self.player)
            else:
                e = enemy_type()
            self.enemies.add(e)
            self.all_sprites.add(e)
            self.spawner.total_spawned += 1
            key_map = {
                NormalEnemy: "normal", FastEnemy: "fast",
                EliteEnemy: "elite", TrackingEnemy: "tracking",
            }
            self.spawner.type_counts[key_map[enemy_type]] += 1

    # ================================================================
    # FPS 追踪
    # ================================================================

    def _track_fps(self, dt: float) -> None:
        """收集 FPS 样本，每秒刷新显示值。"""
        if dt <= 0:
            return
        instant_fps = 1.0 / dt
        self._fps_samples.append(instant_fps)
        self._fps_accum += instant_fps
        self._fps_frame_count += 1
        if self._fps_frame_count >= FPS_SAMPLE_WINDOW:
            self._fps_display = self._fps_accum / self._fps_frame_count
            self._fps_accum = 0.0
            self._fps_frame_count = 0

    # ================================================================
    # F5 配置热重载（题2）
    # ================================================================

    def _reload_config(self) -> None:
        """按 F5 热重载 JSON 配置，无需重启游戏。"""
        cfg = get_config()
        changes = cfg.reload()
        if not changes:
            print("[Config] 热重载: 配置无变更")
            return
        print(f"[Config] 热重载: 检测到 {len(changes)} 项变更 → {list(changes.keys())}")
        self._event_bus.publish(Event(GameEvent.CONFIG_RELOADED, {
            "changes": list(changes.keys()),
        }))
        self._apply_config_changes(changes)
        # 更新 FPS 采样窗口（如果变更）
        if "window.fps" in changes:
            import settings as _s
            self._fps_samples = collections.deque(maxlen=_s.FPS)
        # 短暂闪屏提示
        self.ui.trigger_config_flash("配置已重载")

    def _apply_config_changes(self, changes: dict[str, object]) -> None:
        """将热重载变更应用到运行中的游戏对象。"""
        import settings as _s

        # ---- 玩家属性 ----
        if "player.speed" in changes:
            self.player.base_speed = _s.PLAYER_SPEED
        if "player.boost_multiplier" in changes:
            self.player.boost_multiplier = _s.PLAYER_BOOST_MULTIPLIER
        if "player.max_hp" in changes:
            self.player.max_hp = _s.PLAYER_MAX_HP
            if self.player.hp > self.player.max_hp:
                self.player.hp = self.player.max_hp
        if "player.invincible_time" in changes:
            self.player._invincible_duration = _s.PLAYER_INVINCIBLE_TIME
        if "player.charge_time" in changes:
            self.player._charge_time = _s.PLAYER_CHARGE_TIME

        # ---- 音频音量 ----
        if "audio.sfx_volume" in changes:
            self.audio.set_sfx_volume(float(changes["audio.sfx_volume"]))
        if "audio.bgm_volume" in changes:
            self.audio.set_bgm_volume(float(changes["audio.bgm_volume"]))

        # ---- 敌机生成（基础间隔 / 难度比例变更时重建） ----
        if any(k.startswith("enemy.") or k.startswith("difficulty.")
               for k in changes):
            self._update_spawner_config()

        # ---- 背景速度 ----
        if "background.base_speed" in changes:
            self._rebuild_background_layers()

    def _update_spawner_config(self) -> None:
        """从 settings 重新读取敌机生成配置，应用到当前 Spawner。"""
        import settings as _s
        # 波次制 spawner 无需重算间隔，只需重新设置关卡
        self.spawner.set_level(self.spawner.level)

    def _rebuild_background_layers(self) -> None:
        """从 settings 重新计算背景每层的星星速度。"""
        import settings as _s
        from settings import BACKGROUND_LAYERS
        for i, layer in enumerate(self.background._layers):
            if i < len(BACKGROUND_LAYERS):
                new_speed = _s.BACKGROUND_BASE_SPEED * BACKGROUND_LAYERS[i][3]
                for star in layer:
                    star.speed = new_speed

    # ================================================================
    # 日志面板（题6：~ 键开关）
    # ================================================================

    def _draw_log_panel(self) -> None:
        gl = GameLogger.get_instance()
        if not gl.panel_visible:
            return

        # 半透明背景面板
        pw, ph = 440, 340
        px, py = (SCREEN_WIDTH - pw) // 2, (SCREEN_HEIGHT - ph) // 2
        panel = pygame.Surface((pw, ph), pygame.SRCALPHA)
        panel.fill((0, 0, 0, 210))
        self.screen.blit(panel, (px, py))

        # 标题
        font_title = pygame.font.Font(UI_FONT_PATH, 18)
        stats = gl.get_stats()
        title = font_title.render(
            f"LOG  [{stats['total']}条]  {stats['log_file']}",
            True, CYAN
        )
        self.screen.blit(title, (px + 8, py + 6))

        # 分隔线
        pygame.draw.line(self.screen, (80, 80, 80),
                         (px + 8, py + 28), (px + pw - 8, py + 28))

        # 日志条目
        font_log = pygame.font.Font(UI_FONT_PATH, 13)
        entries = gl.get_recent(20)
        level_colors = {
            LogLevel.DEBUG: (128, 128, 128),
            LogLevel.INFO: (200, 200, 200),
            LogLevel.WARNING: (255, 200, 50),
            LogLevel.ERROR: (255, 80, 80),
            LogLevel.CRITICAL: (255, 0, 0),
        }
        for i, entry in enumerate(reversed(entries)):
            y = py + 32 + i * 15
            if y > py + ph - 8:
                break
            color = level_colors.get(entry.level, (160, 160, 160))
            text = entry.format_onscreen(72)
            surf = font_log.render(text, True, color)
            self.screen.blit(surf, (px + 8, y))

        # 底部操作提示
        hint = font_log.render("F8 关闭面板", True, (128, 128, 128))
        self.screen.blit(hint, (px + 8, py + ph - 18))

    def _setup_event_logging(self) -> None:
        """题6：通过事件总线记录关键操作到 GameLogger。"""
        gl = GameLogger.get_instance()

        def _log(e: Event) -> None:
            t = e.type
            if t == GameEvent.GAME_START:
                gl.info("游戏开始")
            elif t == GameEvent.GAME_OVER:
                gl.info("游戏结束", score=e.data.get("score", 0),
                        level=e.data.get("level", 1))
            elif t == GameEvent.ENEMY_KILLED and e.data.get("is_boss"):
                gl.info("Boss击毁", level=e.data.get("level", 0))
            elif t == GameEvent.LEVEL_UP:
                gl.info("关卡升级", level=e.data.get("level", 0),
                        score=e.data.get("score", 0))
            elif t == GameEvent.BOMB_TRIGGERED:
                gl.info("清屏炸弹", cleared=e.data.get("enemies_cleared", 0))
            elif t == GameEvent.CONFIG_RELOADED:
                gl.info("配置重载", changes=e.data.get("changes", []))

        self._event_bus.subscribe(GameEvent.GAME_START, _log, priority=0)
        self._event_bus.subscribe(GameEvent.GAME_OVER, _log, priority=0)
        self._event_bus.subscribe(GameEvent.ENEMY_KILLED, _log, priority=0)
        self._event_bus.subscribe(GameEvent.LEVEL_UP, _log, priority=0)
        self._event_bus.subscribe(GameEvent.BOMB_TRIGGERED, _log, priority=0)
        self._event_bus.subscribe(GameEvent.CONFIG_RELOADED, _log, priority=0)

    # ================================================================
    # 事件处理器（题4）
    # ================================================================

    def _on_event_enemy_killed(self, e: Event) -> None:
        """敌机击杀事件 → 音效反馈。"""
        # 得分和爆炸已在 CollisionSystem 中处理，此处仅做音效
        if e.data.get("is_boss"):
            self.audio.play_explosion()

    def _on_event_level_up(self, e: Event) -> None:
        """关卡升级事件 → 调整生成器 + 播放音效。"""
        new_level = e.data.get("level", self.spawner.level)
        self.spawner.set_level(new_level)
        self.audio.play_shoot()

    # ================================================================
    # 状态转换
    # ================================================================

    def _on_network_start(self, e: Event) -> None:
        """处理来自事件总线的 GAME_START 事件（网络 / 本地触发）。

        守卫：PLAYING 状态下直接返回，防止重复初始化。
        同时解决 _start_game() 末尾 publish(GAME_START) 导致的递归环：
          _start_game() → publish(GAME_START) → _on_network_start → _start_game()
        第二圈时 state 已经是 PLAYING，守卫拦截，不再递归。
        """
        gl = GameLogger.get_instance()
        gl.info("GAME_START event received",
                current_state=self.state.name,
                source=e.data.get("source", "unknown"))
        print(f"[GAME] 📩 GAME_START event  current_state={self.state.name}"
              f"  source={e.data.get('source', 'unknown')}")
        if self.state == GameState.PLAYING:
            gl.warning("GAME_START ignored: already PLAYING",
                       frame=self.frame_count)
            print(f"[GAME] ⚠ GAME_START 忽略 (已在 PLAYING, frame={self.frame_count})")
            return
        self._start_game()

    def _on_network_move(self, e: Event) -> None:
        """处理来自网络的远程玩家移动事件 → 更新对方位置标记。"""
        if self.state != GameState.PLAYING:
            return
        # 处理 SYNC 批量同步数据
        sync_players = e.data.get("sync_players")
        if sync_players:
            for sp in sync_players:
                self._remote_player_pos = (sp["x"], sp["y"])
                if self._remote_display_pos is None:
                    self._remote_display_pos = (sp["x"], sp["y"])
            return
        x = e.data.get("x", 0)
        y = e.data.get("y", 0)
        self._remote_player_pos = (x, y)
        if self._remote_display_pos is None:
            self._remote_display_pos = (x, y)

    def _on_network_shoot(self, e: Event) -> None:
        """处理来自网络的远程玩家射击事件 → 生成子弹。"""
        if self.state != GameState.PLAYING:
            return
        x = e.data.get("x", 0)
        y = e.data.get("y", 0)
        charge = e.data.get("charge", 0.5)
        print(f"[GAME] 📩 PLAYER_SHOOT from network: x={x:.1f} y={y:.1f} charge={charge:.2f}")

    def _on_network_hit(self, e: Event) -> None:
        """处理来自网络的命中事件。仅当不在房间中时才扣血（房间中由本地碰撞系统处理）。"""
        if self.state != GameState.PLAYING:
            return
        target_id = e.data.get("target_id", 0)
        damage = e.data.get("damage", 1)
        # 在房间中：HIT 仅用于团队积分统计（本地碰撞已处理，不重复扣血）
        if self._my_room is not None:
            print(f"[GAME] HIT in room (积分已由服务器统计): target={target_id} damage={damage}")
            return
        print(f"[GAME] 💔 PLAYER_HIT from network: target_id={target_id} damage={damage}")
        died = self.player.take_damage(damage)
        print(f"[GAME] 💔 网络 HIT 生效: hp={self.player.hp}/{self.player.max_hp} died={died}")
        if died:
            self.state = GameState.GAME_OVER

    def _on_shot_feedback(self, e: Event) -> None:
        """处理服务器射击结果反馈 → 显示浮动文字（题11）。"""
        result = e.data.get("result", 1)
        damage = e.data.get("damage", 0)
        if result == 0:  # HIT
            text = f"HIT +{damage}"
            color = (255, 80, 80)
        elif result == 2:  # REJECT
            text = "REJECT"
            color = (255, 200, 0)
        else:  # MISS
            text = "MISS"
            color = (180, 180, 180)
        # 在玩家位置附近显示
        px = self.player.rect.centerx if self.player else 400
        py = self.player.rect.top - 10 if self.player else 300
        self._shot_feedbacks.append({
            "text": text, "color": color,
            "timer": 1.2, "x": px, "y": py,
        })

    # ── 聊天系统方法（题13）────────────────────────────

    def _on_chat_message(self, e: Event) -> None:
        """处理来自网络的聊天消息 → 添加到历史记录。"""
        sender = e.data.get("sender", "???")
        message = e.data.get("message", "")
        channel = e.data.get("channel", 0)
        self._add_chat_history(sender, message, channel)

    def _add_chat_history(self, sender: str, message: str, channel: int) -> None:
        """添加一条消息到聊天历史。"""
        import time as _t
        self._chat_history.append({
            "sender": sender,
            "message": message,
            "channel": channel,
            "time": _t.time(),
        })
        # 限制历史记录数量
        if len(self._chat_history) > self._chat_max_history:
            self._chat_history = self._chat_history[-self._chat_max_history:]
        self._chat_display_timer = 0.0  # 重置显示计时

    def _draw_chat_ui(self) -> None:
        """绘制聊天系统 UI：消息历史 + 输入框（题13）。"""
        sw, sh = self.screen.get_size()
        font = pygame.font.Font(UI_FONT_PATH, 16)
        small_font = pygame.font.Font(UI_FONT_PATH, 14)

        # ── 频道标签（始终显示）──
        ch_text = "[全局]" if self._chat_channel == 0 else "[队伍]"
        ch_color = (100, 200, 255) if self._chat_channel == 0 else (100, 255, 150)
        ch_surf = small_font.render(f"Chat {ch_text}", True, ch_color)
        self.screen.blit(ch_surf, (10, sh - 22))

        # 快捷消息提示
        if self.state == GameState.PLAYING and self.network.is_connected:
            hint = "  1:GG  2:GL  3:Nice  4:Help"
            hint_surf = small_font.render(hint, True, (120, 120, 120))
            self.screen.blit(hint_surf, (10 + ch_surf.get_width() + 5, sh - 22))

        # ── 输入框（激活时显示）──
        if self._chat_input_active:
            input_h = 28
            input_y = sh - input_h - 26
            input_w = min(400, sw - 20)
            # 背景
            input_bg = pygame.Surface((input_w, input_h), pygame.SRCALPHA)
            input_bg.fill((20, 20, 40, 220))
            self.screen.blit(input_bg, (10, input_y))
            pygame.draw.rect(self.screen, ch_color, (10, input_y, input_w, input_h), 1)
            # 频道 + 文本
            ch_prefix = f"[{'队伍' if self._chat_channel else '全局'}] "
            display_text = ch_prefix + self._chat_input_buffer + "|"
            text_surf = font.render(display_text, True, (255, 255, 255))
            # 限制显示宽度
            if text_surf.get_width() > input_w - 10:
                text_surf = text_surf.subsurface(
                    (text_surf.get_width() - input_w + 10, 0,
                     input_w - 10, text_surf.get_height()))
            self.screen.blit(text_surf, (15, input_y + 4))

        # ── 消息历史（有输入框时显示更多，否则仅显示最近消息）──
        if not self._chat_history:
            return

        # 判断是否应显示历史（输入模式 或 最近有消息）
        self._chat_display_timer += self.dt if hasattr(self, 'dt') else 0.016
        show_count = 8 if self._chat_input_active else 5
        if not self._chat_input_active and self._chat_display_timer > self._chat_display_duration:
            return  # 超时隐藏

        recent = self._chat_history[-show_count:]
        base_y = sh - 55 if self._chat_input_active else sh - 45
        for i, msg in enumerate(reversed(recent)):
            y = base_y - i * 20
            if y < 10:
                break
            ch = msg["channel"]
            color = (180, 220, 255) if ch == 0 else (150, 255, 200)
            prefix = "[全]" if ch == 0 else "[队]"
            line = f"{prefix} {msg['sender']}: {msg['message']}"
            surf = small_font.render(line, True, color)
            # 半透明背景
            bg = pygame.Surface((surf.get_width() + 6, surf.get_height() + 2),
                                pygame.SRCALPHA)
            bg.fill((0, 0, 0, 140))
            self.screen.blit(bg, (8, y - 1))
            self.screen.blit(surf, (10, y))

    def _room_create(self, password: str = "") -> None:
        """在 MENU 状态创建房间。R=无密码, K=密码1234。"""
        import random
        rid = str(random.randint(1000, 9999))
        name = f"Room_{rid}"
        self.network.send_room_create(name, password)
        pwd_info = f" 密码={password}" if password else ""
        print(f"[MENU] 创建房间: {name}{pwd_info}")
        self._room_list_dirty = True

    def _room_join_first(self, password: str = "") -> None:
        """加入列表中的第一个房间。"""
        if self._room_list:
            rid = self._room_list[0].get("id", "")
            self.network.send_room_join(rid, password)
            print(f"[MENU] 加入房间: {rid} 密码={'***' if password else '无'}")

    def _on_room_event(self, e: Event) -> None:
        """处理来自网络的房间事件（通过 CONFIG_RELOADED 传递）。"""
        if e.data.get("source") != "network":
            return
        text = e.data.get("text", "")
        room_data = e.data.get("room_data", {})

        # ── 团队积分/计时（始终更新，不跳过 PLAYING）──
        if text == "TEAM_SCORE":
            self._team_score_a = room_data.get("score_a", 0)
            self._team_score_b = room_data.get("score_b", 0)
            return
        if text == "GAME_TIMER":
            self._game_timer_remaining = room_data.get("remaining_sec", 0)
            return
        if text == "BATTLE_END":
            self._battle_result = room_data
            self._in_room_game = False
            print(f"[GAME] 🏁 BATTLE_END received: winner={room_data.get('winner','?')}")
            return

        if self.state == GameState.PLAYING:
            return  # 其他房间事件不干扰游戏
        if not room_data:
            return
        if text == "ROOM_INFO":
            self._my_room = room_data
        elif text == "ROOM_LIST":
            self._room_list = room_data.get("rooms", [])
            self._room_list_dirty = False
        elif text == "ROOM_DISBAND":
            self._my_room = None
            self._room_list_dirty = True
        elif text == "ROOM_START":
            self._my_room = None
            self._in_room_game = True
            # 房间开始 → 自动开始游戏
            if self.state == GameState.MENU:
                self._start_game()

    def _start_game(self) -> None:
        """开始 / 重新开始游戏（MENU→PLAYING 或 GAME_OVER→PLAYING）。"""
        gl = GameLogger.get_instance()
        gl.info("_start_game() executing",
                previous_state=self.state.name)
        print(f"[GAME] 🎮 _start_game() 初始化 (from state={self.state.name})")
        self.all_sprites.empty()
        self.bullets.empty()
        self.enemies.empty()
        self.explosions.empty()
        self.powerups.empty()

        self.player = Player()
        self.all_sprites.add(self.player)
        # ⭐ 应用永久升级
        apply_upgrades_to_player(self.player, self.upgrade_data)

        self.spawner.reset()
        self.spawner.set_player(self.player)

        self.collision.reset()
        self.collision.current_level = 1  # ⭐ 初始关卡
        self.ui.reset()
        self.audio.reset()  # ⭐ 重置音频状态
        # ⭐ 背景主题重置为星空
        self.background = ScrollingBackground()
        self._bg_callback = BackgroundCallback(self.background)
        self._boss = None
        self._boss_dying = False
        self._boss_dying_positions.clear()
        self._entering_name = False
        self._name_buffer = ""
        self._screen_shake = 0.0
        self._level_transition_timer = 0.0
        self._level_transition_alpha = 0.0
        self._level_transition_text = ""
        self._last_sent_x = float(self.player.rect.centerx)
        self._last_sent_y = float(self.player.rect.centery)

        self.state = GameState.PLAYING
        self.frame_count = 0
        self.audio.start_bgm()
        self._event_bus.publish(Event(GameEvent.GAME_START, {"source": "local"}))

    def _go_to_menu(self) -> None:
        """返回主菜单（清除游戏现场）。"""
        self.all_sprites.empty()
        self.bullets.empty()
        self.enemies.empty()
        self.explosions.empty()
        self.powerups.empty()

        self.player = Player()
        self.all_sprites.add(self.player)
        self.spawner.set_player(self.player)

        self.ui.reset()
        self.audio.reset()  # ⭐ 重置音频状态
        self._boss = None
        self._screen_shake = 0.0
        self.audio.stop_bgm()
        self._in_room_game = False
        self.state = GameState.MENU
        self.frame_count = 0

    def _go_to_upgrade(self) -> None:
        """结束游戏后进入升级界面（如有点数可加）。"""
        # 保存本局经验
        xp = self.collision.xp_earned
        if xp > 0:
            old_level = self.upgrade_data.level
            gained = self.upgrade_data.add_xp(xp)
            self._xp_this_run = xp
            self._upgrade_show_levelup = gained > 0
            self._upgrade_levelup_count = gained
            save_upgrades(self.upgrade_data)
            print(f"[UPGRADE] 获得 {xp} 经验, Lv.{old_level}→{self.upgrade_data.level}, "
                  f"可用点数 {self.upgrade_data.points}")

        # 清理游戏现场
        self.all_sprites.empty()
        self.bullets.empty()
        self.enemies.empty()
        self.explosions.empty()
        self.powerups.empty()
        self.player = Player()
        self.all_sprites.add(self.player)
        self.spawner.set_player(self.player)
        self.ui.reset()
        self.audio.reset()  # ⭐ 重置音频状态
        self._boss = None
        self._screen_shake = 0.0
        self.audio.stop_bgm()
        self._in_room_game = False
        self.frame_count = 0

        # 有点数 → 升级界面；否则直接返回菜单
        if self.upgrade_data.points > 0:
            self._upgrade_selected = 0
            self.state = GameState.UPGRADE
        else:
            self.state = GameState.MENU

    # ================================================================
    # 主循环
    # ================================================================

    def _toggle_network(self) -> None:
        """F10: 连接/断开网络。"""
        if self.network.running:
            self.network.stop()
            GameLogger.get_instance().info("Network disconnected by user")
        else:
            self.network.start()
            GameLogger.get_instance().info("Network connecting...",
                                           host=self.network.host,
                                           port=self.network.port)

    def run(self) -> None:
        self.running = True
        if self._network_auto_connect:
            self.network.start()
        while self.running:
            # ⭐ 性能分析：开始帧
            self._profiler.begin_frame()

            self._profiler.begin_section("events")
            self.handle_events()
            self._profiler.end_section()

            self._profiler.begin_section("update")
            self.update()
            self._profiler.end_section()

            self._profiler.begin_section("render")
            self.render()
            self._profiler.end_section()

            delta_ms: float = self.clock.tick(FPS)
            self.dt = delta_ms / 1000.0

            # ⭐ 性能分析：结束帧
            self._profiler.end_frame()
        self.network.stop()

    def quit(self) -> None:
        self.network.stop()
        pygame.quit()
        sys.exit(0)


