"""
Protocol 单元测试 — 二进制编解码、心跳、流量统计
"""
import time
from systems.protocol import (
    Message, MessageType, TrafficStats, HeartbeatManager,
    MAGIC, PROTOCOL_VERSION, HEADER_SIZE, MAX_PAYLOAD,
    make_conn, make_auth, make_move, make_shoot, make_hit,
    make_sync, make_chat, make_heartbeat, make_disconn,
)


class TestMessageEncodeDecode:
    def test_conn_roundtrip(self):
        m = make_conn("Player1", seq=42)
        data = m.encode()
        decoded = Message.decode(data)
        assert decoded.type == MessageType.CONN
        assert decoded.payload["player_name"] == "Player1"
        assert decoded.seq == 42
        assert decoded.version == PROTOCOL_VERSION

    def test_auth_roundtrip(self):
        m = make_auth("token_abc123", seq=1)
        decoded = Message.decode(m.encode())
        assert decoded.type == MessageType.AUTH
        assert decoded.payload["token"] == "token_abc123"

    def test_move_roundtrip(self):
        m = make_move(240.0, 600.0, 5.0, -2.5, seq=10)
        decoded = Message.decode(m.encode())
        assert decoded.type == MessageType.MOVE
        assert decoded.payload["x"] == 240.0
        assert decoded.payload["y"] == 600.0
        assert decoded.payload["dx"] == 5.0
        assert decoded.payload["dy"] == -2.5

    def test_shoot_roundtrip(self):
        m = make_shoot(240.0, 500.0, 0.85)
        decoded = Message.decode(m.encode())
        assert decoded.type == MessageType.SHOOT
        assert abs(decoded.payload["charge"] - 0.85) < 0.001

    def test_hit_roundtrip(self):
        m = make_hit(target_id=12345, damage=3, x=240.0, y=300.0)
        decoded = Message.decode(m.encode())
        assert decoded.type == MessageType.HIT
        assert decoded.payload["target_id"] == 12345
        assert decoded.payload["damage"] == 3

    def test_sync_roundtrip(self):
        m = make_sync(player_count=2, data=b"\x01\x02\x03")
        decoded = Message.decode(m.encode())
        assert decoded.type == MessageType.SYNC
        assert decoded.payload["player_count"] == 2

    def test_chat_roundtrip(self):
        m = make_chat("Hello World!")
        decoded = Message.decode(m.encode())
        assert decoded.payload["message"] == "Hello World!"

    def test_heartbeat_roundtrip(self):
        m = make_heartbeat(is_pong=True)
        decoded = Message.decode(m.encode())
        assert decoded.type == MessageType.HEARTBEAT
        assert decoded.payload["is_pong"] is True

    def test_disconn_roundtrip(self):
        m = make_disconn(reason=1)
        decoded = Message.decode(m.encode())
        assert decoded.type == MessageType.DISCONN
        assert decoded.payload["reason"] == 1


class TestMessageHeader:
    def test_header_size_is_12(self):
        assert HEADER_SIZE == 12

    def test_magic_in_header(self):
        data = make_conn("test").encode()
        import struct
        magic = struct.unpack("!I", data[:4])[0]
        assert magic == MAGIC

    def test_version_in_header(self):
        data = make_conn("test").encode()
        assert data[4] == PROTOCOL_VERSION

    def test_type_in_header(self):
        data = make_move(0, 0, 0, 0).encode()
        assert data[5] == MessageType.MOVE

    def test_payload_length_in_header(self):
        m = make_conn("hello")  # 5 bytes UTF-8
        data = m.encode()
        import struct
        length = struct.unpack("!H", data[6:8])[0]
        assert length == 5


class TestMessageErrors:
    def test_decode_too_short(self):
        try:
            Message.decode(b"\x00\x00")
            assert False, "should raise"
        except ValueError as e:
            assert "太短" in str(e)

    def test_decode_bad_magic(self):
        import struct
        # Craft a message with wrong magic
        header = struct.pack("!IBBH I", 0xDEADBEEF, 1, 1, 0, 0)
        try:
            Message.decode(header)
            assert False, "should raise"
        except ValueError as e:
            assert "Magic" in str(e)

    def test_decode_bad_type(self):
        import struct
        header = struct.pack("!IBBH I", MAGIC, 1, 255, 0, 0)
        try:
            Message.decode(header)
            assert False, "should raise"
        except ValueError as e:
            assert "类型" in str(e)

    def test_decode_length_mismatch(self):
        import struct
        header = struct.pack("!IBBH I", MAGIC, 1, MessageType.CONN, 999, 0)
        try:
            Message.decode(header)
            assert False, "should raise"
        except ValueError as e:
            assert "长度" in str(e)


class TestTrafficStats:
    def test_record_send(self):
        ts = TrafficStats()
        m = make_conn("test")
        data = m.encode()
        ts.record_send(m, len(data))
        assert ts.bytes_sent == len(data)
        assert ts.msgs_sent[MessageType.CONN] == 1

    def test_record_recv(self):
        ts = TrafficStats()
        m = make_move(0, 0, 0, 0)
        data = m.encode()
        ts.record_recv(m, len(data))
        assert ts.bytes_recv == len(data)

    def test_summary(self):
        ts = TrafficStats()
        ts.record_send(make_conn("t"), 20)
        ts.record_recv(make_move(0, 0, 0, 0), 28)
        s = ts.summary()
        assert "TX:" in s
        assert "RX:" in s


class TestHeartbeat:
    def test_should_send_after_interval(self):
        hm = HeartbeatManager(interval=5.0)
        assert hm.should_send(6.0) is True
        assert hm.should_send(0.0) is False

    def test_send_updates_timer(self):
        hm = HeartbeatManager(interval=5.0)
        hm.send(10.0)
        assert hm.should_send(12.0) is False
        assert hm.should_send(16.0) is True

    def test_timeout_detected(self):
        hm = HeartbeatManager(timeout=15.0)
        hm.on_recv(10.0)
        assert hm.is_timeout(26.0) is True   # 26 - 10 > 15
        assert hm.is_timeout(20.0) is False  # 20 - 10 < 15

    def test_no_timeout_before_first_recv(self):
        hm = HeartbeatManager(timeout=15.0)
        assert hm.is_timeout(100.0) is False


class TestMaxPayload:
    def test_max_payload(self):
        assert MAX_PAYLOAD == 65535
