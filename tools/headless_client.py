import sys
import os
import time
import signal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from systems.network_client import NetworkClient
from systems.event_bus import EventBus, Event, GameEvent

running = True

def _sigint(signum, frame):
    global running
    running = False

signal.signal(signal.SIGINT, _sigint)


def on_event(e: Event) -> None:
    print(f"Event received: {e.type.name} -> {e.data}")


if __name__ == '__main__':
    bus = EventBus.get_instance()
    bus.subscribe(GameEvent.GAME_START, on_event)
    bus.subscribe(GameEvent.GOTO_MENU, on_event)
    bus.subscribe(GameEvent.GAME_PAUSE, on_event)
    bus.subscribe(GameEvent.GAME_RESUME, on_event)
    bus.subscribe(GameEvent.CONFIG_RELOADED, on_event)

    client = NetworkClient(host='127.0.0.1', port=8888, player_name='Headless', auto_reconnect=True)
    client.start()
    print('Headless client started, connecting...')

    try:
        while running:
            # 处理网络线程通过 publish_async 发来的事件（游戏主线程每帧 flush）
            bus.flush_async()
            time.sleep(0.1)
    finally:
        client.stop()
        print('Headless client stopped')
