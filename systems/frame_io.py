"""
==============================================================================
飞机大战 — 共享帧协议工具
==============================================================================
提取自 server.py 和 network_client.py 的公共帧读写逻辑，
避免代码重复并确保客户端/服务器协议一致。

帧格式: 4B 大端长度前缀 + 载荷（最大 65535 字节）
==============================================================================
"""

from __future__ import annotations

import asyncio

# 帧最大载荷
MAX_FRAME_PAYLOAD = 65535


async def read_frame(reader: asyncio.StreamReader) -> bytes | None:
    """
    读取一帧：4B 大端长度 + 载荷。

    返回载荷 bytes，或在连接断开/数据异常时返回 None。
    """
    try:
        len_bytes = await reader.readexactly(4)
        length = int.from_bytes(len_bytes, "big")
        if length > MAX_FRAME_PAYLOAD:
            return None
        payload = await reader.readexactly(length)
        return payload
    except (asyncio.IncompleteReadError, OSError):
        return None


async def write_frame(writer: asyncio.StreamWriter, data: bytes) -> None:
    """
    写入一帧：4B 大端长度 + 载荷。
    """
    length = len(data).to_bytes(4, "big")
    writer.write(length + data)
    await writer.drain()
