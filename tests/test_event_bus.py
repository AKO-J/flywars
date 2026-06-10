"""
EventBus 单元测试 — 订阅、发布、优先级、异步、日志
"""
from systems.event_bus import EventBus, GameEvent, Event


class TestEventBusSubscribe:
    def test_subscribe_and_publish(self):
        bus = EventBus.get_instance()
        received = []

        def handler(e: Event):
            received.append(e)

        bus.subscribe(GameEvent.GAME_START, handler)
        bus.publish(Event(GameEvent.GAME_START, {}))
        assert len(received) == 1
        assert received[0].type == GameEvent.GAME_START
        bus.unsubscribe(GameEvent.GAME_START, handler)

    def test_unsubscribe_stops_receiving(self):
        bus = EventBus.get_instance()
        received = []

        def handler(e: Event):
            received.append(e)

        bus.subscribe(GameEvent.GAME_START, handler)
        bus.unsubscribe(GameEvent.GAME_START, handler)
        bus.publish(Event(GameEvent.GAME_START, {}))
        assert len(received) == 0

    def test_duplicate_subscribe_only_adds_once(self):
        bus = EventBus.get_instance()
        count = [0]

        def handler(e: Event):
            count[0] += 1

        bus.subscribe(GameEvent.GAME_OVER, handler)
        bus.subscribe(GameEvent.GAME_OVER, handler)  # duplicate
        bus.publish(Event(GameEvent.GAME_OVER, {}))
        assert count[0] == 1
        bus.unsubscribe(GameEvent.GAME_OVER, handler)


class TestEventBusPriority:
    def test_higher_priority_runs_first(self):
        bus = EventBus.get_instance()
        order = []

        def handler_a(e: Event):
            order.append("a")

        def handler_b(e: Event):
            order.append("b")

        bus.subscribe(GameEvent.GAME_START, handler_a, priority=10)
        bus.subscribe(GameEvent.GAME_START, handler_b, priority=20)
        bus.publish(Event(GameEvent.GAME_START, {}))
        assert order == ["b", "a"]
        bus.unsubscribe(GameEvent.GAME_START, handler_a)
        bus.unsubscribe(GameEvent.GAME_START, handler_b)


class TestEventBusAsync:
    def test_async_not_executed_until_flush(self):
        bus = EventBus.get_instance()
        received = []

        def handler(e: Event):
            received.append(e)

        bus.subscribe(GameEvent.GAME_PAUSE, handler)
        bus.publish_async(Event(GameEvent.GAME_PAUSE, {}))
        assert len(received) == 0  # not yet
        bus.flush_async()
        assert len(received) == 1
        bus.unsubscribe(GameEvent.GAME_PAUSE, handler)

    def test_async_multiple_flushed_in_order(self):
        bus = EventBus.get_instance()
        order = []

        def handler(e: Event):
            order.append(e.data["n"])

        bus.subscribe(GameEvent.GAME_START, handler)
        bus.publish_async(Event(GameEvent.GAME_START, {"n": 1}))
        bus.publish_async(Event(GameEvent.GAME_START, {"n": 2}))
        bus.publish_async(Event(GameEvent.GAME_START, {"n": 3}))
        bus.flush_async()
        assert order == [1, 2, 3]
        bus.unsubscribe(GameEvent.GAME_START, handler)


class TestEventBusLog:
    def test_log_records_events(self):
        bus = EventBus.get_instance()
        log_before = len(bus.get_log())
        bus.publish(Event(GameEvent.GAME_START, {"test": True}))
        log_after = bus.get_log()
        assert len(log_after) > log_before

    def test_log_filter_by_type(self):
        bus = EventBus.get_instance()
        bus.publish(Event(GameEvent.LEVEL_UP, {"level": 2}))
        filtered = bus.get_log(event_type=GameEvent.LEVEL_UP)
        assert all(e.type == GameEvent.LEVEL_UP for e in filtered)

    def test_log_limit(self):
        bus = EventBus.get_instance()
        bus.publish(Event(GameEvent.GAME_START, {}))
        limited = bus.get_log(limit=1)
        assert len(limited) <= 1


class TestEventBusStats:
    def test_stats_counts_events(self):
        bus = EventBus.get_instance()
        initial = bus.get_stats()["total_events"]
        bus.publish(Event(GameEvent.GAME_START, {}))
        bus.publish(Event(GameEvent.PLAYER_SHOOT, {}))
        assert bus.get_stats()["total_events"] == initial + 2

    def test_handler_count(self):
        bus = EventBus.get_instance()

        def tmp_handler(e: Event):
            pass

        bus.subscribe(GameEvent.GAME_START, tmp_handler)
        assert bus.get_stats()["handler_count"] >= 1
        bus.unsubscribe(GameEvent.GAME_START, tmp_handler)


class TestEventData:
    def test_event_data_passed_to_handler(self):
        bus = EventBus.get_instance()
        result = {}

        def handler(e: Event):
            result.update(e.data)

        bus.subscribe(GameEvent.PLAYER_HIT, handler)
        bus.publish(Event(GameEvent.PLAYER_HIT, {"damage": 3, "source": "boss"}))
        assert result["damage"] == 3
        assert result["source"] == "boss"
        bus.unsubscribe(GameEvent.PLAYER_HIT, handler)

    def test_event_timestamp(self):
        e = Event(GameEvent.GAME_START, {})
        assert e.timestamp > 0
