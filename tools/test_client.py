import socket
import struct
import time
import argparse
import os
import sys

# 确保能够导入项目内模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from systems.protocol import make_conn, make_chat, Message


def send_frame(sock: socket.socket, data: bytes) -> None:
    length = len(data).to_bytes(4, "big")
    sock.sendall(length + data)


def read_frame(sock: socket.socket, timeout: float = 2.0) -> bytes | None:
    sock.settimeout(timeout)
    try:
        len_bytes = sock.recv(4)
        if not len_bytes or len(len_bytes) < 4:
            return None
        length = int.from_bytes(len_bytes, "big")
        payload = b""
        while len(payload) < length:
            chunk = sock.recv(length - len(payload))
            if not chunk:
                return None
            payload += chunk
        return payload
    except socket.timeout:
        return None
    except Exception:
        return None


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8888)
    p.add_argument('--name', default='Tester')
    p.add_argument('--chat', default='')
    args = p.parse_args()

    addr = (args.host, args.port)
    print(f"Connecting to {addr}...")
    s = socket.create_connection(addr, timeout=5)
    print("Connected")

    # send CONN
    conn = make_conn(args.name)
    send_frame(s, conn.encode())
    print("Sent CONN")

    time.sleep(0.2)

    if args.chat:
        chat = make_chat(args.chat)
        send_frame(s, chat.encode())
        print("Sent CHAT:", args.chat)

    # try reading server broadcast/response for a short time
    for _ in range(5):
        payload = read_frame(s, timeout=1.0)
        if payload is None:
            break
        try:
            msg = Message.decode(payload)
            print("Recv:", msg.type.name, msg.payload)
        except Exception as e:
            print("Decode error:", e)

    print("Closing")
    s.close()
