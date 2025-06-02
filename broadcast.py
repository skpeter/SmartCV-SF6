import asyncio
import socket
import time

BROADCAST_PORT = 6500
BROADCAST_INTERVAL = 1  # seconds

def broadcast_device_info():
    hostname = socket.gethostname()
    ip = socket.gethostbyname(hostname)
    message = f"smartcv-ggst:{hostname}:{ip}".encode("utf-8")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(('', 0))


    try:
        while True:
            sock.sendto(message, ("192.168.1.255", BROADCAST_PORT))
            time.sleep(BROADCAST_INTERVAL)
    except asyncio.CancelledError:
        print("Broadcast cancelled.")
    finally:
        sock.close()

def broadcaster_thread():
    try:
        asyncio.run(broadcast_device_info())
    except Exception as e:
        print(f"Broadcast thread error: {e}")

if __name__ == "__main__":
    asyncio.run(broadcast_device_info())