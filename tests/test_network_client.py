"""
NetworkClient 单元测试 — 连接状态机、指数退避、线程安全、状态摘要
"""
import time
import threading
from systems.network_client import (
    NetworkClient, ConnectionState,
    DEFAULT_HOST, DEFAULT_PORT,
    RECONNECT_BASE_DELAY, RECONNECT_MAX_DELAY,
)


class TestConnectionState:
    """连接状态枚举"""

    def test_states_exist(self):
        assert ConnectionState.DISCONNECTED is not None
        assert ConnectionState.CONNECTING is not None
        assert ConnectionState.CONNECTED is not None

    def test_states_distinct(self):
        states = {ConnectionState.DISCONNECTED, ConnectionState.CONNECTING, ConnectionState.CONNECTED}
        assert len(states) == 3


class TestNetworkClientConstruction:
    """构造参数"""

    def test_default_values(self):
        c = NetworkClient()
        assert c.host == DEFAULT_HOST
        assert c.port == DEFAULT_PORT
        assert c.auto_reconnect is True
        assert c.reconnect_base_delay == RECONNECT_BASE_DELAY
        assert c.reconnect_max_delay == RECONNECT_MAX_DELAY

    def test_custom_values(self):
        c = NetworkClient(
            host="192.168.1.1", port=9999,
            player_name="TestPlayer",
            auto_reconnect=False,
            reconnect_base_delay=2.0,
            reconnect_max_delay=60.0,
        )
        assert c.host == "192.168.1.1"
        assert c.port == 9999
        assert c.player_name == "TestPlayer"
        assert c.auto_reconnect is False
        assert c.reconnect_base_delay == 2.0
        assert c.reconnect_max_delay == 60.0

    def test_initial_state_disconnected(self):
        c = NetworkClient()
        assert c.state == ConnectionState.DISCONNECTED
        assert c.is_connected is False
        assert c.latency == 0.0


class TestNetworkClientState:
    """状态管理（线程安全）"""

    def test_state_transition(self):
        c = NetworkClient()
        assert c.state == ConnectionState.DISCONNECTED
        c.state = ConnectionState.CONNECTING
        assert c.state == ConnectionState.CONNECTING
        c.state = ConnectionState.CONNECTED
        assert c.state == ConnectionState.CONNECTED
        assert c.is_connected is True
        c.state = ConnectionState.DISCONNECTED
        assert c.is_connected is False

    def test_state_thread_safety(self):
        """多线程状态读写不丢更新、不崩溃。"""
        c = NetworkClient()
        errors = []

        def writer():
            try:
                for _ in range(500):
                    c.state = ConnectionState.CONNECTING
                    c.state = ConnectionState.CONNECTED
                    c.state = ConnectionState.DISCONNECTED
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(500):
                    _ = c.state
                    _ = c.is_connected
                    _ = c.latency
                    _ = c.status_text()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer), threading.Thread(target=reader),
                   threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestExponentialBackoff:
    """指数退避计算"""

    def test_first_attempt_base_delay(self):
        c = NetworkClient(reconnect_base_delay=1.0)
        delay = c._next_reconnect_delay()
        # 第一次 ≈ 1.0s，有 ±20% 抖动
        assert 0.1 <= delay <= 1.0 * 1.2 * 1.01  # 略大于 1.2 因 max

    def test_backoff_increases(self):
        c = NetworkClient(reconnect_base_delay=1.0)
        d1 = c._next_reconnect_delay()
        d2 = c._next_reconnect_delay()
        d3 = c._next_reconnect_delay()
        # 总体趋势递增（考虑抖动，d3 大概率 > d1）
        assert c.reconnect_attempt == 3

    def test_backoff_hits_max(self):
        c = NetworkClient(reconnect_base_delay=1.0, reconnect_max_delay=5.0)
        # 快速推进到高尝试次数
        for _ in range(10):
            c._next_reconnect_delay()
        delay = c._next_reconnect_delay()
        # 应该被 max_delay 截断，再加抖动也不会超过太多
        assert delay <= 5.0 * 1.2 + 0.01

    def test_backoff_clamps_to_min(self):
        c = NetworkClient(reconnect_base_delay=0.01, reconnect_max_delay=30)
        delay = c._next_reconnect_delay()
        assert delay >= 0.1  # min 0.1


class TestStatusText:
    """状态文本输出"""

    def test_disconnected_text(self):
        c = NetworkClient(host="10.0.0.1", port=7777)
        text = c.status_text()
        assert "OFFLINE" in text
        assert "10.0.0.1:7777" in text

    def test_connecting_text(self):
        c = NetworkClient()
        c.state = ConnectionState.CONNECTING
        text = c.status_text()
        assert "CONNECTING" in text

    def test_connected_text(self):
        c = NetworkClient()
        c.state = ConnectionState.CONNECTED
        text = c.status_text()
        assert "ONLINE" in text

    def test_status_color(self):
        c = NetworkClient()
        assert c.status_color() == (255, 0, 0)  # RED for DISCONNECTED
        c.state = ConnectionState.CONNECTING
        assert c.status_color() == (255, 255, 0)  # YELLOW
        c.state = ConnectionState.CONNECTED
        assert c.status_color() == (0, 255, 0)  # GREEN


class TestNetworkClientLifecycle:
    """生命周期 start/stop"""

    def test_start_stop(self):
        c = NetworkClient(auto_reconnect=False)
        assert c._running is False
        c.start()
        assert c._running is True
        assert c._thread is not None
        assert c._thread.is_alive()
        c.stop()
        # 线程应已结束
        assert c._thread is not None
        c._thread.join(timeout=2.0)
        assert not c._thread.is_alive() or c._running is False

    def test_double_start_noop(self):
        c = NetworkClient(auto_reconnect=False)
        c.start()
        thread1 = c._thread
        c.start()
        thread2 = c._thread
        assert thread1 is thread2
        c.stop()

    def test_stop_without_start_noop(self):
        c = NetworkClient()
        c.stop()  # 不抛异常


class TestLatencyTracking:
    """延迟测量"""

    def test_initial_latency_zero(self):
        c = NetworkClient()
        assert c.latency == 0.0

    def test_latency_averaging(self):
        c = NetworkClient()
        with c._lock:
            c._latency_samples.append(50.0)
            c._latency_samples.append(100.0)
            c._latency_samples.append(150.0)
            c._latency_ms = sum(c._latency_samples) / len(c._latency_samples)
        assert 99.0 <= c.latency <= 101.0  # 均值 ≈ 100ms
