"""
==============================================================================
飞机大战 — 空间哈希碰撞加速
==============================================================================
将屏幕划分为网格，只检测同一或相邻网格中的精灵对，
将 O(n²) 降低为 O(n) ~ O(n log n)。

适用于大量精灵（>100）时的碰撞检测优化。
默认开启，精灵数少时自动回退到直接检测。
"""

import math
import pygame


class SpatialHash:
    """
    空间哈希表 — 将 2D 空间划分为网格，加速碰撞检测。

    用法：
      sh = SpatialHash(cell_size=64)
      sh.clear()
      sh.add(sprite1)
      sh.add(sprite2)
      pairs = sh.get_pairs()  # 返回可能碰撞的 (sprite, sprite) 对
    """

    def __init__(self, cell_size: int = 64) -> None:
        self.cell_size: int = cell_size
        self._cells: dict[tuple[int, int], list[pygame.sprite.Sprite]] = {}
        self._rect_cache: dict[int, pygame.Rect] = {}  # id → rect

    def clear(self) -> None:
        """清空所有格子。"""
        self._cells.clear()
        self._rect_cache.clear()

    def _cell_coords(self, x: float, y: float) -> tuple[int, int]:
        """返回坐标所在的网格坐标。"""
        return (int(math.floor(x / self.cell_size)),
                int(math.floor(y / self.cell_size)))

    def _cell_range(self, rect: pygame.Rect) -> list[tuple[int, int]]:
        """返回与 rect 相交的所有网格坐标。"""
        min_cx, min_cy = self._cell_coords(rect.left, rect.top)
        max_cx, max_cy = self._cell_coords(rect.right, rect.bottom)
        cells = []
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                cells.append((cx, cy))
        return cells

    def add(self, sprite: pygame.sprite.Sprite) -> None:
        """将一个精灵加入空间哈希表。"""
        rect = sprite.rect
        if rect.width <= 0 or rect.height <= 0:
            return
        self._rect_cache[id(sprite)] = rect
        for cell in self._cell_range(rect):
            if cell not in self._cells:
                self._cells[cell] = []
            self._cells[cell].append(sprite)

    def add_group(self, group: pygame.sprite.Group) -> None:
        """将一个精灵组中的所有精灵加入。"""
        for sprite in group:
            if sprite.alive():
                self.add(sprite)

    def get_pairs_for_group(
        self,
        group_a: pygame.sprite.Group,
        group_b: pygame.sprite.Group,
        keep_a: bool = False,
    ) -> dict[pygame.sprite.Sprite, list[pygame.sprite.Sprite]]:
        """
        返回 group_a 中精灵与 group_b 中精灵的潜在碰撞对。

        返回格式与 pygame.sprite.groupcollide() 兼容：
          {sprite_from_a: [sprite_from_b, ...], ...}
        """
        # 将两个组加入哈希表
        self.clear()
        self.add_group(group_a)
        self.add_group(group_b)

        # 用集合去重
        result: dict[int, set[int]] = {}

        for cell_sprites in self._cells.values():
            n = len(cell_sprites)
            if n < 2:
                continue
            # 同一格子内的所有精灵两两配对
            for i in range(n):
                sa = cell_sprites[i]
                if not sa.alive():
                    continue
                id_a = id(sa)
                if id_a not in result:
                    result[id_a] = set()
                for j in range(i + 1, n):
                    sb = cell_sprites[j]
                    if not sb.alive():
                        continue
                    id_b = id(sb)
                    result[id_a].add(id_b)

        # 转换为 dict[sprite, list[sprite]] 格式
        output: dict[pygame.sprite.Sprite, list[pygame.sprite.Sprite]] = {}
        sprite_map = {}
        for cell_sprites in self._cells.values():
            for s in cell_sprites:
                sprite_map[id(s)] = s

        # 只保留 group_a 中的精灵作为 key
        a_ids = {id(s) for s in group_a if s.alive()}
        for id_a in result:
            if id_a in a_ids and id_a in sprite_map:
                sa = sprite_map[id_a]
                matches = [sprite_map[id_b] for id_b in result[id_a]
                          if id_b in sprite_map]
                if matches:
                    output[sa] = matches

        return output

    def get_candidates(
        self,
        sprite: pygame.sprite.Sprite,
        group: pygame.sprite.Group,
    ) -> list[pygame.sprite.Sprite]:
        """
        返回指定 sprite 与 group 中精灵的潜在碰撞候选。
        替代 pygame.sprite.spritecollide() 的加速版本。
        """
        rect = sprite.rect
        candidates: set[int] = set()
        for cell in self._cell_range(rect):
            if cell not in self._cells:
                continue
            for other in self._cells[cell]:
                if other is sprite:
                    continue
                if not other.alive():
                    continue
                candidates.add(id(other))

        sprite_map = {id(s): s for s in group if s.alive()}
        return [sprite_map[cid] for cid in candidates if cid in sprite_map]

    @property
    def stats(self) -> dict:
        """返回哈希表统计信息。"""
        cell_counts = [len(v) for v in self._cells.values()]
        return {
            "cells": len(self._cells),
            "sprites": len(self._rect_cache),
            "avg_per_cell": sum(cell_counts) / max(len(cell_counts), 1),
            "max_per_cell": max(cell_counts) if cell_counts else 0,
        }
