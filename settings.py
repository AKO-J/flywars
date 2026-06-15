"""
==============================================================================
飞机大战 — 全局配置文件
==============================================================================
包含所有游戏中使用的常量：窗口尺寸、帧率、颜色定义等。
后续所有模块统一从此文件导入配置，保证参数一致性。
"""

# ---------------------- 窗口设置 ---------------------- #
# 游戏窗口宽度（像素），固定分辨率不可调整
SCREEN_WIDTH: int = 600
# 游戏窗口高度（像素）
SCREEN_HEIGHT: int = 820
# 窗口标题
GAME_TITLE: str = "飞机大战"

# ---------------------- 游戏状态枚举 ---------------------- #
from enum import Enum, auto

class GameState(Enum):
    """游戏全局状态机"""
    MENU = auto()       # 主菜单
    PLAYING = auto()    # 游戏中
    PAUSED = auto()     # 暂停
    GAME_OVER = auto()  # 游戏结束
    VICTORY = auto()    # 通关胜利（题19）
    UPGRADE = auto()    # ⭐ 升级加点界面

class PowerUpType(Enum):
    """道具类型枚举"""
    HEALTH = auto()          # 生命恢复 +1（即时生效）
    BOMB = auto()            # 清屏炸弹（即时生效）
    DOUBLE_DAMAGE = auto()   # 双倍伤害（持续8秒）
    TRIPLE_SPREAD = auto()   # 三向散射（持续8秒）
    PIERCE = auto()          # 穿透弹（持续8秒）
    RAPID_FIRE = auto()      # 快速蓄力（持续8秒）

class FormationType(Enum):
    """敌机编队阵型枚举"""
    NONE = auto()      # 无阵型，随机位置（原有行为）
    LINE = auto()      # 一字横排
    VSHAPE = auto()    # V字楔形
    TRIANGLE = auto()  # 正三角/倒三角
    ARC = auto()       # 弧线排列
    CROSS = auto()     # X形交叉
    SURROUND = auto()  # 两侧包围

# ---------------------- 帧率设置 ---------------------- #
# 目标帧率：每秒刷新60次，保证动画流畅
FPS: int = 60

# ---------------------- 字体设置 ---------------------- #
import os
UI_FONT_PATH: str = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "msyh.ttc")

# ---------------------- 资源路径（真实图像素材） ---------------------- #
PLAYER_IMAGE_PATH: str = "assets/images/player.png"
BOSS_IMAGE_PATH: str = "assets/images/boss.png"
ENEMY_NORMAL_IMAGE_PATH: str = "assets/images/小怪2.png"
ENEMY_FAST_IMAGE_PATH: str = "assets/images/小怪3.png"
ENEMY_ELITE_IMAGE_PATH: str = "assets/images/小怪.png"
ENEMY_TRACKING_IMAGE_PATH: str = "assets/images/小怪4.png"

# ---------------------- 颜色常量（RGB 元组） ---------------------- #
BLACK: tuple = (0, 0, 0)
WHITE: tuple = (255, 255, 255)
RED: tuple = (255, 0, 0)
GREEN: tuple = (0, 255, 0)
BLUE: tuple = (0, 0, 255)
YELLOW: tuple = (255, 255, 0)
GRAY: tuple = (128, 128, 128)
DARK_GRAY: tuple = (50, 50, 50)
CYAN: tuple = (0, 255, 255)
ORANGE: tuple = (255, 165, 0)

# ---------------------- 玩家设置 ---------------------- #
# 玩家飞机移动速度（像素/帧）
PLAYER_SPEED: int = 5
# ⭐ 升级每级移速增量（原+1）
PLAYER_SPEED_PER_UPGRADE: int = 2
# ⭐ 升级每级蓄力倍率（原0.92，越小越快）
PLAYER_CHARGE_MULT_PER_UPGRADE: float = 0.85
# Shift加速倍率（按住 Shift 时速度 = PLAYER_SPEED × 此值）
PLAYER_BOOST_MULTIPLIER: float = 1.8
# 玩家飞机初始生命值
PLAYER_MAX_HP: int = 5
# 玩家受伤后无敌时间（秒），防止连续扣血
PLAYER_INVINCIBLE_TIME: float = 1.5
# 敌机碰撞伤害
ENEMY_COLLISION_DAMAGE: int = 1
# 玩家飞机显示尺寸（原始美术资源 405×418，等比缩放至以下尺寸）
PLAYER_WIDTH: int = 55
PLAYER_HEIGHT: int = 57
# 玩家飞机倾斜角度（左右移动时机身倾斜，单位：度）
PLAYER_TILT_ANGLE: int = 20

# ---------------------- 背景设置 ---------------------- #
# 背景滚动基准速度（像素/秒），实际每层速度 = 基准 × 层系数
BACKGROUND_BASE_SPEED: float = 80.0
# 视差层配置：[ (星星数量, 最小尺寸, 最大尺寸, 速度系数, 最小亮度, 最大亮度), ... ]
# 速度系数：1.0 = 基准速度，越小越慢（远层），越大越快（近层）
BACKGROUND_LAYERS: list[tuple[int, int, int, float, int, int]] = [
    (60, 1, 1, 0.3, 60, 120),    # 原(40) → 远层：更多小星
    (35, 1, 2, 0.6, 100, 170),   # 原(25) → 中层
    (20, 2, 4, 1.0, 150, 255),   # 原(15) → 近层：大星含彩色
]

# ---------------------- 子弹设置 ---------------------- #
# 玩家子弹速度（像素/秒，Delta-Time驱动）
PLAYER_BULLET_SPEED: float = 550.0       # 原500 → 更快
# 玩家子弹伤害
PLAYER_BULLET_DAMAGE: int = 1
# 玩家子弹尺寸（⭐ 单发子弹更大更帅）
PLAYER_BULLET_WIDTH: int = 8             # 原4 → 加宽
PLAYER_BULLET_HEIGHT: int = 20           # 原14 → 加长
# 玩家自动连射间隔（秒）⭐ 新增
PLAYER_AUTO_FIRE_INTERVAL: float = 0.18  # ≈ 5.5发/秒
# 蓄力系统 — 进度条随时间填充，SPACE释放时按蓄力等级发射
# 充满所需时间（秒），值越大蓄力越慢，多发射击代价越大
PLAYER_CHARGE_TIME: float = 0.85
# 双发阈值：蓄力≥40% 触发
CHARGE_THRESHOLD_DOUBLE: float = 0.40
# 三发阈值：蓄力≥80% 触发
CHARGE_THRESHOLD_TRIPLE: float = 0.80
# 双发子弹水平间距（像素）
DOUBLE_SHOT_SPACING: int = 10

# 敌人子弹速度（像素/秒）
ENEMY_BULLET_SPEED: float = 380.0
# 敌人子弹伤害
ENEMY_BULLET_DAMAGE: int = 1
# 敌人子弹尺寸
ENEMY_BULLET_WIDTH: int = 8
ENEMY_BULLET_HEIGHT: int = 8

# ---------------------- 敌机设置 ---------------------- #
# 普通敌机
ENEMY_NORMAL_SPEED: float = 150.0       # 移动速度（像素/秒）
ENEMY_NORMAL_HP: int = 2                # 生命值
ENEMY_NORMAL_SCORE: int = 100           # 击毁得分
ENEMY_NORMAL_WIDTH: int = 40            # 图像宽度
ENEMY_NORMAL_HEIGHT: int = 40           # 图像高度
ENEMY_NORMAL_SPAWN_INTERVAL: float = 1.5  # 生成间隔（秒）
ENEMY_NORMAL_FIRE_INTERVAL: float = 2.8   # 射击间隔（秒）⭐ 新增

# 快速敌机
ENEMY_FAST_SPEED: float = 280.0         # 移动速度（像素/秒）
ENEMY_FAST_HP: int = 1                  # 生命值
ENEMY_FAST_SCORE: int = 150             # 击毁得分
ENEMY_FAST_WIDTH: int = 28              # 图像宽度
ENEMY_FAST_HEIGHT: int = 28             # 图像高度
ENEMY_FAST_SPAWN_INTERVAL: float = 3.5  # 生成间隔（秒）
ENEMY_FAST_DIAGONAL_SPEED: float = 120.0  # 斜向水平速度（px/s）
ENEMY_FAST_FIRE_INTERVAL: float = 2.2    # 射击间隔（秒）⭐ 新增

# 精英敌机（正弦波移动）
ENEMY_ELITE_SPEED: float = 100.0          # 垂直速度（px/s）
ENEMY_ELITE_HP: int = 4                   # 生命值
ENEMY_ELITE_SCORE: int = 300              # 击毁得分
ENEMY_ELITE_WIDTH: int = 44               # 图像宽度
ENEMY_ELITE_HEIGHT: int = 44              # 图像高度
ENEMY_ELITE_SPAWN_INTERVAL: float = 6.0   # 生成间隔（秒）
ENEMY_ELITE_WAVE_AMPLITUDE: float = 80.0  # 正弦波振幅（像素）
ENEMY_ELITE_WAVE_FREQUENCY: float = 2.5   # 正弦波频率（Hz）
ENEMY_ELITE_FIRE_INTERVAL: float = 1.5    # 射击间隔（秒）⭐ 新增
ENEMY_ELITE_BURST_COUNT: int = 3          # 连射发数 ⭐ 新增
ENEMY_ELITE_BURST_INTERVAL: float = 0.12  # 连射间隔（秒）⭐ 新增

# 追踪敌机（跟踪玩家）
ENEMY_TRACKING_SPEED: float = 180.0       # 移动速度（px/s）
ENEMY_TRACKING_HP: int = 3                # 生命值
ENEMY_TRACKING_SCORE: int = 250           # 击毁得分
ENEMY_TRACKING_WIDTH: int = 34            # 图像宽度
ENEMY_TRACKING_HEIGHT: int = 34           # 图像高度
ENEMY_TRACKING_SPAWN_INTERVAL: float = 8.0  # 生成间隔（秒）
ENEMY_TRACKING_FIRE_INTERVAL: float = 1.8   # 射击间隔（秒）⭐ 新增

# ---------------------- 爆炸特效设置 ---------------------- #
# 爆炸动画帧总数
EXPLOSION_FRAME_COUNT: int = 16
# 每帧持续时间（游戏帧数，60fps下约50ms/帧）
EXPLOSION_FRAME_TICKS: int = 3
# 爆炸动画最大尺寸（像素，正方形）
EXPLOSION_SIZE: int = 64

# ---------------------- Boss 设置（题15） ---------------------- #
# Boss 首次出现的关卡
BOSS_SPAWN_LEVEL: int = 3
# Boss 生命值（基础值，随关卡进一步缩放）
BOSS_HP: int = 60                    # 原50 → 更高
# Boss 移动速度（像素/秒）
BOSS_SPEED: float = 65.0             # 原60 → 稍快
# Boss 击毁得分
BOSS_SCORE: int = 1000
# Boss 显示尺寸（题19：真实素材宽高比 ~2.5:1）
BOSS_WIDTH: int = 150
BOSS_HEIGHT: int = 62
# Boss 弹幕发射间隔（秒）⭐ 全部缩短 → 弹幕更密
BOSS_FIRE_INTERVAL_CIRCLE: float = 1.6    # 原2.0 → 圆形弹幕更密集
BOSS_FIRE_INTERVAL_AIMED: float = 1.2     # 原1.5 → 瞄准弹幕更频繁
BOSS_FIRE_INTERVAL_SPIRAL: float = 0.06   # 原0.08 → 螺旋弹幕更密
# Boss 进入阶段：从顶部移动到目标Y位置的时间（秒）
BOSS_ENTER_DURATION: float = 2.0
# Boss 巡逻左右边界（像素，距边缘）
BOSS_PATROL_MARGIN: int = 60
# Boss 子弹伤害
BOSS_BULLET_DAMAGE: int = 1
# Boss 子弹速度（像素/秒）
BOSS_BULLET_SPEED: float = 220.0          # 原200 → 更快
# Boss 扇形弹幕（题19）
BOSS_FAN_COUNT: int = 16                  # 原12 → 更多弹头
BOSS_FAN_ANGLE: float = 120.0             # 原110° → 更宽角度
BOSS_FAN_INTERVAL: float = 1.8            # 原2.2 → 更频繁
# Boss 死亡特效（题19）
BOSS_EXPLOSION_COUNT: int = 10      # Boss 死亡时生成爆炸数量
BOSS_EXPLOSION_DELAY: float = 0.10  # 连续爆炸间隔（秒）
# 通关设置（题19）
FINAL_BOSS_LEVEL: int = 9           # 击败该关卡 Boss 后显示通关界面

# ---------------------- 难度递增设置（题15 ⭐ 增强版） ---------------------- #
# 每提升一级，生成间隔乘以该系数（<1 则敌机越来越密）
DIFFICULTY_SPAWN_INTERVAL_SCALE: float = 0.82  # 原0.85 → 更密
# 每提升一级，敌机速度乘以该系数（>1 则越来越快）
DIFFICULTY_SPEED_SCALE: float = 1.12            # 原1.10 → 更快
# 每提升一级，敌机 HP 乘以该系数（>1 则越来越肉）
DIFFICULTY_HP_SCALE: float = 1.18               # 原1.15 → 更耐打
# 每提升一级，敌机射速乘以该系数（>1 则子弹更密）⭐ 新增
DIFFICULTY_FIRE_RATE_SCALE: float = 0.88        # <1 射击间隔缩短
# ⭐ 非线性难度指数：>1 时后期难度陡增，<1 时前期更难
# 公式：effective_level = level ** DIFFICULTY_NONLINEAR_EXP
# level=1~3: 平缓  level=4~6: 加速  level=7~9: 陡升
DIFFICULTY_NONLINEAR_EXP: float = 1.3

# 生成间隔的下限（秒），防止间隔过短
SPAWN_INTERVAL_MIN: float = 0.15                # 原0.20 → 更密集

# ---------------------- 关卡波次系统（⭐ 全新设计） ---------------------- #
# 每关由若干波次组成，清完波次出 Boss，Boss 击败进入下一关
# 波次定义：(敌机类型, 数量) 的列表

# 敌机类型别名
from typing import Literal
EnemyWaveType = Literal["normal", "fast", "elite", "tracking"]

# ⭐ 编队阵型默认参数
FORMATION_DEFAULTS: dict[str, dict] = {
    "line": {
        "spacing": 60,
        "width": 450,
        "entry_y": -80,
        "angle": 0,
    },
    "vshape": {
        "spacing": 55,
        "width": 400,
        "entry_y": -80,
        "angle": 30,
    },
    "triangle": {
        "spacing": 60,
        "width": 400,
        "entry_y": -100,
        "angle": 0,
    },
    "arc": {
        "spacing": 45,
        "width": 380,
        "entry_y": -80,
        "angle": 150,
    },
    "cross": {
        "spacing": 55,
        "width": 400,
        "entry_y": -80,
        "angle": 35,
    },
    "surround": {
        "spacing": 60,
        "width": 500,
        "entry_y": -60,
        "angle": 25,
    },
}

# 波次结构：每个波次可以是 [(type, count), ...]（旧格式，随机位置）
# 或 {"units": [(type, count), ...], "formation": "...", "params": {...}}
LEVEL_WAVES: dict[int, dict] = {
    1: {  # 入门关 — 横排入门
        "waves": [
            {"units": [("normal", 3)], "formation": "line"},
            {"units": [("normal", 4)], "formation": "line"},
            {"units": [("normal", 3), ("fast", 1)], "formation": "vshape"},
        ],
        "spawn_interval": 0.9,
        "has_boss": False,
    },
    2: {  # 引入快速敌机 — 三角+V形
        "waves": [
            {"units": [("normal", 4)], "formation": "line"},
            {"units": [("normal", 3), ("fast", 2)], "formation": "triangle"},
            {"units": [("normal", 4), ("fast", 2)], "formation": "vshape"},
        ],
        "spawn_interval": 0.8,
        "has_boss": False,
    },
    3: {  # 引入精英敌机
        "waves": [
            {"units": [("normal", 4), ("fast", 1)], "formation": "line"},
            {"units": [("normal", 3), ("elite", 1)], "formation": "triangle"},
            {"units": [("normal", 4), ("fast", 3)], "formation": "vshape"},
            {"units": [("normal", 5), ("fast", 2), ("elite", 1)], "formation": "cross"},
        ],
        "spawn_interval": 0.7,
        "has_boss": False,
    },
    4: {  # 引入追踪敌机
        "waves": [
            {"units": [("normal", 4), ("fast", 2)], "formation": "line"},
            {"units": [("normal", 3), ("fast", 2), ("tracking", 1)], "formation": "vshape"},
            {"units": [("normal", 4), ("fast", 3), ("elite", 1)], "formation": "arc"},
            {"units": [("normal", 5), ("fast", 3), ("tracking", 1)], "formation": "cross"},
        ],
        "spawn_interval": 0.65,
        "has_boss": False,
    },
    5: {  # ⭐ 首个 Boss 战
        "waves": [
            {"units": [("normal", 5), ("fast", 2)], "formation": "line"},
            {"units": [("normal", 3), ("fast", 3), ("elite", 1)], "formation": "vshape"},
            {"units": [("normal", 4), ("fast", 3), ("elite", 2)], "formation": "triangle"},
            {"units": [("normal", 6), ("fast", 3), ("tracking", 1)], "formation": "surround"},
        ],
        "spawn_interval": 0.6,
        "has_boss": True,
    },
    6: {  # 战间期 — 混合编队
        "waves": [
            {"units": [("normal", 4), ("fast", 3), ("tracking", 1)], "formation": "vshape"},
            {"units": [("normal", 3), ("fast", 2), ("elite", 2)], "formation": "cross"},
            {"units": [("normal", 4), ("fast", 3), ("elite", 2)], "formation": "triangle"},
            {"units": [("normal", 5), ("fast", 3), ("tracking", 2)], "formation": "arc"},
            {"units": [("normal", 6), ("fast", 4), ("elite", 1), ("tracking", 1)], "formation": "surround"},
        ],
        "spawn_interval": 0.55,
        "has_boss": False,
    },
    7: {  # 高密度 — 全阵型展示
        "waves": [
            {"units": [("normal", 6), ("fast", 3), ("tracking", 1)], "formation": "line"},
            {"units": [("normal", 5), ("fast", 4), ("elite", 2)], "formation": "vshape"},
            {"units": [("normal", 6), ("fast", 3), ("tracking", 2)], "formation": "triangle"},
            {"units": [("normal", 5), ("fast", 4), ("elite", 2), ("tracking", 2)], "formation": "cross"},
            {"units": [("normal", 8), ("fast", 5), ("elite", 2)], "formation": "surround"},
        ],
        "spawn_interval": 0.5,
        "has_boss": False,
    },
    8: {  # 最终关前哨
        "waves": [
            {"units": [("normal", 6), ("fast", 4), ("tracking", 2)], "formation": "vshape"},
            {"units": [("normal", 5), ("fast", 4), ("elite", 3)], "formation": "cross"},
            {"units": [("normal", 6), ("fast", 5), ("tracking", 3)], "formation": "triangle"},
            {"units": [("normal", 8), ("fast", 4), ("elite", 3), ("tracking", 2)], "formation": "arc"},
            {"units": [("normal", 10), ("fast", 5), ("elite", 3), ("tracking", 2)], "formation": "surround"},
        ],
        "spawn_interval": 0.45,
        "has_boss": False,
    },
    9: {  # ⭐ 最终 Boss 战
        "waves": [
            {"units": [("normal", 8), ("fast", 5), ("tracking", 2)], "formation": "vshape"},
            {"units": [("normal", 6), ("fast", 5), ("elite", 3), ("tracking", 2)], "formation": "cross"},
            {"units": [("normal", 10), ("fast", 4), ("elite", 3)], "formation": "triangle"},
            {"units": [("normal", 8), ("fast", 5), ("tracking", 3), ("elite", 2)], "formation": "arc"},
            {"units": [("normal", 10), ("fast", 6), ("elite", 4), ("tracking", 3)], "formation": "surround"},
            {"units": [("normal", 8), ("fast", 6), ("elite", 4), ("tracking", 3)], "formation": "cross"},
        ],
        "spawn_interval": 0.4,
        "has_boss": True,
        "final": True,  # 击败最终 Boss 通关
    },
}

# 波次间休息时间（秒）
WAVE_REST_DURATION: float = 1.2  # 原2.0 → 节奏更快
# 波次推进提示显示时间
WAVE_ANNOUNCE_DURATION: float = 1.0
# ⭐ 阵型波次敌机生成间隔（秒）— 快速序列，让编队可见
FORMATION_SPAWN_INTERVAL: float = 0.12
# 飘字得分：上浮速度（像素/秒）
FLOATING_TEXT_SPEED: float = 80.0
# 飘字得分：存在时间（秒）
FLOATING_TEXT_LIFETIME: float = 1.0
# 关卡：每 N 分升一级
LEVEL_SCORE_BASE: int = 800        # 原500 → 每关间距拉大，升级节奏更舒服
# 关卡提升提示显示时长（秒）
LEVEL_UP_DISPLAY_TIME: float = 2.0

# ---------------------- 精灵层排序（DirtySprite/LayeredDirty） ---------------------- #
# 数值越小越先绘制（底层），越大越后绘制（顶层）
LAYER_ENEMY: int = 0
LAYER_BULLET: int = 1
LAYER_PLAYER: int = 2
LAYER_BOSS: int = 3
LAYER_EXPLOSION: int = 4
LAYER_POWERUP: int = 2  # 道具层（在敌机/子弹之上，与玩家同层，避免被遮挡）

# ---------------------- 道具系统设置（题18） ---------------------- #
# 道具掉落概率
POWERUP_DROP_CHANCE: float = 0.20          # 普通敌机
POWERUP_ELITE_DROP_CHANCE: float = 0.45    # 精英/追踪敌机
POWERUP_BOSS_DROP_COUNT: int = 3           # Boss 死亡掉落数量
# 道具尺寸与速度
POWERUP_SIZE: int = 28                     # 道具图标尺寸
POWERUP_FALL_SPEED: float = 80.0           # 下落速度（px/s）
POWERUP_LIFETIME: float = 8.0              # 存活时间（秒）
POWERUP_PULSE_SPEED: float = 4.0           # 脉冲动画频率（Hz）
# 火力道具持续时间（秒）
POWERUP_DURATION: float = 8.0
# 炸弹上限（⭐ 新增：不再无限使用）
PLAYER_MAX_BOMBS: int = 3

# ---------------------- 玩家成长系统（⭐ 新增） ---------------------- #
# 击杀经验值
XP_NORMAL: int = 15            # 普通敌机（原10）
XP_FAST: int = 25              # 快速敌机（原15）
XP_ELITE: int = 50             # 精英敌机（原30）
XP_TRACKING: int = 40          # 追踪敌机（原25）
XP_BOSS: int = 200             # Boss（原100）

# 升级所需经验公式: BASE + (level-1) × SCALE
XP_LEVEL_BASE: int = 100       # 1级→2级所需经验（原80）
XP_LEVEL_SCALE: int = 50       # 每级递增（原40）
XP_LEVEL_MAX: int = 99         # 最高等级

# 强化类型
UPGRADE_MAX_LEVEL: int = 8                # 每项强化最高等级（原5）
UPGRADE_POINTS_PER_LEVEL: int = 1         # 每升1级获得点数

# ⭐ 阈值质变 — 各属性在特定等级解锁特效
# ❤️ 生命强化
PLAYER_HP_REGEN_INTERVAL: float = 10.0    # Lv.3: 自动回血间隔（秒）
PLAYER_ARMOR_DAMAGE_REDUCTION: int = 1    # Lv.5: 每次受伤抵消伤害
PLAYER_IMMORTAL_ONCE: bool = True         # Lv.8: 每局一次免死
# ⚡ 火力提升
PLAYER_CRIT_CHANCE: float = 0.10          # Lv.5: 暴击率
PLAYER_CRIT_DAMAGE_MULT: float = 2.0      # Lv.5: 暴击伤害倍率
PLAYER_BULLET_SIZE_BONUS: int = 2         # Lv.3: 子弹尺寸增大（px）
PLAYER_PIERCE_SHOT: bool = True           # Lv.8: 穿透弹
# 🔥 蓄力加速
PLAYER_OVERCHARGE_THRESHOLD: float = 1.50 # Lv.3: 二阶蓄力上限（150%）
PLAYER_CHARGE_RETAIN: float = 0.40        # Lv.5: 发射后保留蓄力比例
PLAYER_TURBO_CHARGE_MULT: float = 0.70    # Lv.8: 涡轮充能倍率
# 💨 机动增强
PLAYER_DIAGONAL_PENALTY_UPGRADE: float = 0.80  # Lv.3: 斜向惩罚（原0.707）
PLAYER_HURT_SPEED_BOOST: float = 1.40     # Lv.5: 受伤加速倍率
PLAYER_HURT_SPEED_DURATION: float = 2.0   # Lv.5: 受伤加速持续（秒）
PLAYER_MOVE_FIRE_BONUS: float = 0.80      # Lv.8: 移动时连射间隔系数（越小越快）
# 🌊 弹幕扩散
PLAYER_SPREAD_SPACING_UPGRADE: int = 10   # Lv.2: 扩散子弹间距（px）
PLAYER_SPREAD_ANGLE: float = 30.0         # Lv.3: 扇形散射覆盖角（度）
# 🛡️ 护盾精通
PLAYER_SHIELD_BONUS_TIME: float = 0.5     # Lv.3: 无敌时间额外增加
PLAYER_COUNTER_SHOT: bool = True          # Lv.5: 无敌期间受伤反击
PLAYER_REVIVE_EXTRA_TIME: float = 3.0     # Lv.8: 复活后无敌时间
# 道具主题色（程序化渲染用）
POWERUP_COLORS: dict = {
    PowerUpType.HEALTH: (0, 230, 60),
    PowerUpType.BOMB: (255, 190, 0),
    PowerUpType.DOUBLE_DAMAGE: (255, 60, 60),
    PowerUpType.TRIPLE_SPREAD: (0, 200, 255),
    PowerUpType.PIERCE: (120, 120, 255),
    PowerUpType.RAPID_FIRE: (255, 140, 0),
}

# ---------------------- 网络客户端设置（题9） ---------------------- #
# 服务器地址
NETWORK_SERVER_HOST: str = "127.0.0.1"
NETWORK_SERVER_PORT: int = 8888
# 是否启动时自动连接
NETWORK_AUTO_CONNECT: bool = False
# 重连指数退避：初始延迟（秒）
NETWORK_RECONNECT_BASE_DELAY: float = 1.0
# 重连指数退避：最大延迟（秒）
NETWORK_RECONNECT_MAX_DELAY: float = 30.0
# 心跳间隔（秒）
NETWORK_HEARTBEAT_INTERVAL: float = 5.0
# 心跳超时（秒）
NETWORK_HEARTBEAT_TIMEOUT: float = 15.0

# ---------------------- 性能测试设置 ---------------------- #
# 按 F2 一键生成 N 架敌机用于压测
PERF_TEST_ENEMY_COUNT: int = 100
# FPS 采样窗口（帧数）
FPS_SAMPLE_WINDOW: int = 60
