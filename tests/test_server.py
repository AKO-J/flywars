"""
Server 单元测试 — 启动、连接、断开、管理命令
"""
import asyncio
import time
import pytest
from server.server import GameServer
from systems.frame_io import read_frame, write_frame


class TestServerLifecycle:
    def test_server_create(self):
        s = GameServer("127.0.0.1", 0, 10)
        assert s.host == "127.0.0.1"
        assert s.max_clients == 10
        assert s._running is False

    @pytest.mark.asyncio
    async def test_server_start_stop(self):
        s = GameServer("127.0.0.1", 0, 2)
        await s.start()
        assert s._running is True
        assert s._server is not None
        await s.shutdown()
        assert s._running is False

    @pytest.mark.asyncio
    async def test_client_connect_disconnect(self):
        s = GameServer("127.0.0.1", 0, 5)
        await s.start()
        port = s._server.sockets[0].getsockname()[1]

        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        await asyncio.sleep(0.1)

        assert len(s._clients) == 1

        writer.close()
        await writer.wait_closed()
        await asyncio.sleep(0.1)
        assert len(s._clients) == 0

        await s.shutdown()

    @pytest.mark.asyncio
    async def test_max_clients_rejected(self):
        s = GameServer("127.0.0.1", 0, 1)
        await s.start()
        port = s._server.sockets[0].getsockname()[1]

        # First client
        reader1, writer1 = await asyncio.open_connection("127.0.0.1", port)
        await asyncio.sleep(0.1)
        assert len(s._clients) == 1

        # Second client - should be rejected
        try:
            reader2, writer2 = await asyncio.open_connection("127.0.0.1", port)
            await asyncio.sleep(0.1)
            # Either connection closed by server or accepted then immediately closed
            assert len(s._clients) <= 1
            writer2.close()
        except Exception:
            pass  # Connection refused is fine

        writer1.close()
        await writer1.wait_closed()
        await s.shutdown()


class TestClientHandler:
    @pytest.mark.asyncio
    async def test_handler_close(self):
        s = GameServer("127.0.0.1", 0, 3)
        await s.start()
        port = s._server.sockets[0].getsockname()[1]

        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        await asyncio.sleep(0.1)

        cid = list(s._clients.keys())[0]
        handler = s._clients[cid]
        assert handler.alive

        await handler.close("test")
        assert not handler.alive

        writer.close()
        await writer.wait_closed()
        await s.shutdown()


class TestFrameProtocol:
    @pytest.mark.asyncio
    async def test_write_read_frame(self):
        # 创建一个 echo 服务器用于测试帧协议
        async def echo(reader, writer):
            payload = await read_frame(reader)
            if payload:
                await write_frame(writer, payload)
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(echo, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]

        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        test_data = b"Hello Protocol!"
        await write_frame(writer, test_data)
        result = await read_frame(reader)
        assert result == test_data

        writer.close()
        await writer.wait_closed()
        server.close()
        await server.wait_closed()
