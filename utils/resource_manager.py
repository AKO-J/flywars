"""
==============================================================================
飞机大战 — 资源管理器（题3：统一加载、缓存、占位、统计）
==============================================================================
ResourceManager 单例类：
  1. 统一加载图片/音效/字体
  2. 自动缓存，同一资源不重复 IO
  3. 自动解析项目相对路径
  4. 资源缺失时返回占位资源（洋红色问号图 / 系统默认字体 / None）
  5. 提供缓存命中率、内存占用统计
==============================================================================
"""

import os
import pygame


# ==========================================================================
# 占位资源生成
# ==========================================================================

def _make_placeholder_image(width: int, height: int) -> pygame.Surface:
    """生成洋红色矩形 + 对角线叉号，表示资源缺失。"""
    surf = pygame.Surface((max(width, 4), max(height, 4)), pygame.SRCALPHA)
    surf.fill((255, 0, 255, 255))
    w, h = surf.get_width(), surf.get_height()
    pygame.draw.line(surf, (0, 0, 0), (0, 0), (w, h), width=2)
    pygame.draw.line(surf, (0, 0, 0), (w, 0), (0, h), width=2)
    pygame.draw.rect(surf, (0, 0, 0), (0, 0, w, h), width=1)
    return surf


# ==========================================================================
# 路径工具
# ==========================================================================

def _get_asset_path(relative_path: str) -> str:
    """将项目相对路径转为绝对路径（基于 project/ 根目录）。"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(project_root, relative_path)


# ==========================================================================
# ResourceManager 单例
# ==========================================================================

class ResourceManager:
    """统一资源加载器（单例），带缓存、占位回退、统计。"""

    _instance: "ResourceManager | None" = None

    def __init__(self) -> None:
        self._image_cache: dict[str, pygame.Surface] = {}
        self._sound_cache: dict[str, pygame.mixer.Sound] = {}
        self._font_cache: dict[tuple[str, int], pygame.font.Font] = {}
        # 统计
        self._loads: dict[str, int] = {"image": 0, "sound": 0, "font": 0}
        self._hits: dict[str, int] = {"image": 0, "sound": 0, "font": 0}
        self._misses: dict[str, int] = {"image": 0, "sound": 0, "font": 0}

    @classmethod
    def get_instance(cls) -> "ResourceManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ==================================================================
    # 图片
    # ==================================================================

    def get_image(
        self, relative_path: str,
        width: int | None = None, height: int | None = None,
    ) -> pygame.Surface:
        """加载图片（缓存命中则直接返回）。"""
        key = f"img:{relative_path}:{width}:{height}"
        if key in self._image_cache:
            self._hits["image"] += 1
            return self._image_cache[key]

        full = _get_asset_path(relative_path)
        try:
            img = pygame.image.load(full).convert_alpha()
            if width is not None and height is not None:
                img = pygame.transform.scale(img, (width, height))
            self._loads["image"] += 1
        except (pygame.error, FileNotFoundError, OSError):
            w = width or 32
            h = height or 32
            img = _make_placeholder_image(w, h)
            self._misses["image"] += 1

        self._image_cache[key] = img
        return img

    # ==================================================================
    # 音效
    # ==================================================================

    def get_sound(self, relative_path: str) -> pygame.mixer.Sound | None:
        """加载音效（缓存命中则直接返回，缺失返回 None）。"""
        if relative_path in self._sound_cache:
            self._hits["sound"] += 1
            return self._sound_cache[relative_path]

        full = _get_asset_path(relative_path)
        try:
            if not os.path.exists(full):
                raise FileNotFoundError(full)
            snd = pygame.mixer.Sound(full)
            self._loads["sound"] += 1
        except (pygame.error, FileNotFoundError, OSError):
            snd = None
            self._misses["sound"] += 1

        self._sound_cache[relative_path] = snd
        return snd

    # ==================================================================
    # 字体
    # ==================================================================

    def get_font(self, path: str, size: int) -> pygame.font.Font:
        """加载字体（缺失时回退到系统默认字体）。"""
        key = (path, size)
        if key in self._font_cache:
            self._hits["font"] += 1
            return self._font_cache[key]

        try:
            if not os.path.exists(path):
                raise FileNotFoundError(path)
            font = pygame.font.Font(path, size)
            self._loads["font"] += 1
        except (FileNotFoundError, pygame.error, OSError):
            font = pygame.font.Font(None, size)
            self._misses["font"] += 1

        self._font_cache[key] = font
        return font

    # ==================================================================
    # 缓存管理
    # ==================================================================

    def clear_cache(self) -> None:
        self._image_cache.clear()
        self._sound_cache.clear()
        self._font_cache.clear()

    def get_stats(self) -> dict:
        """返回资源统计信息。"""
        total_loaded = sum(self._loads.values())
        total_hits = sum(self._hits.values())
        total_misses = sum(self._misses.values())
        total_access = total_loaded + total_hits

        # 估算显存占用
        img_bytes = sum(s.get_width() * s.get_height() * 4
                       for s in self._image_cache.values())
        img_mb = img_bytes / (1024 * 1024)

        return {
            "cache": {
                "images": len(self._image_cache),
                "sounds": len(self._sound_cache),
                "fonts": len(self._font_cache),
            },
            "access": {
                "loads": dict(self._loads),
                "hits": dict(self._hits),
                "misses": dict(self._misses),
                "hit_rate": f"{total_hits / max(total_access, 1) * 100:.0f}%",
            },
            "memory": {
                "image_estimate_mb": round(img_mb, 2),
                "total_cache_entries": len(self._image_cache) + len(self._sound_cache) + len(self._font_cache),
            },
        }


# ==========================================================================
# 模块级便捷函数（向后兼容，内部委托 ResourceManager）
# ==========================================================================

def load_image(
    relative_path: str,
    width: int | None = None,
    height: int | None = None,
    rotation: float = 0.0,
) -> pygame.Surface:
    """加载图像（委托 ResourceManager）。rotation 非零时额外旋转。"""
    rm = ResourceManager.get_instance()
    img = rm.get_image(relative_path, width, height)
    if rotation != 0.0:
        img = pygame.transform.rotate(img, rotation)
    return img


def load_sound(relative_path: str) -> pygame.mixer.Sound | None:
    """加载音效（委托 ResourceManager）。"""
    return ResourceManager.get_instance().get_sound(relative_path)


def load_font(path: str, size: int) -> pygame.font.Font:
    """加载字体（委托 ResourceManager）。"""
    return ResourceManager.get_instance().get_font(path, size)


def load_and_scale(relative_path: str, width: int, height: int) -> pygame.Surface:
    return load_image(relative_path, width=width, height=height)


def load_and_rotate(relative_path: str, rotation: float) -> pygame.Surface:
    return load_image(relative_path, rotation=rotation)


def scale_image(image: pygame.Surface, width: int, height: int) -> pygame.Surface:
    return pygame.transform.scale(image, (width, height))


def rotate_image(image: pygame.Surface, rotation: float) -> pygame.Surface:
    return pygame.transform.rotate(image, rotation)
