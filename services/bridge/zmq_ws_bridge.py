import asyncio
import json
import threading
import zmq
import websockets

ZMQ_ADDRESS = "tcp://127.0.0.1:5558"
ZMQ_TOPIC   = b"current_identity"
WS_HOST     = "0.0.0.0"
WS_PORT     = 5556

connected_clients: set = set()
latest_message: dict | None = None


async def ws_handler(websocket):
    connected_clients.add(websocket)
    print(f"[WS] client connected ({len(connected_clients)} total)")

    if latest_message:
        try:
            await websocket.send(json.dumps(latest_message))
        except Exception:
            pass

    try:
        await websocket.wait_closed()
    finally:
        connected_clients.discard(websocket)
        print(f"[WS] client disconnected ({len(connected_clients)} total)")


async def broadcast(message: str):
    if not connected_clients:
        return
    try:
        websockets.broadcast(connected_clients, message)
    except AttributeError:
        await asyncio.gather(
            *[ws.send(message) for ws in list(connected_clients)],
            return_exceptions=True
        )


def zmq_reader(loop: asyncio.AbstractEventLoop):
    global latest_message
    ctx = zmq.Context()
    sock = ctx.socket(zmq.SUB)
    sock.connect(ZMQ_ADDRESS)
    sock.setsockopt(zmq.SUBSCRIBE, ZMQ_TOPIC)
    print(f"[ZMQ] subscribed to {ZMQ_ADDRESS}")

    while True:
        try:
            frames = sock.recv_multipart()
            if len(frames) < 2:
                continue
            data = json.loads(frames[1].decode("utf-8", errors="replace").strip())
            print(f"[ZMQ] received: {data}")
            latest_message = data
            asyncio.run_coroutine_threadsafe(broadcast(json.dumps(data)), loop)
        except json.JSONDecodeError as e:
            print(f"[ZMQ] JSON parse error: {e} — raw: {frames!r}")
        except Exception as e:
            print(f"[ZMQ] error: {e}")


async def main():
    loop = asyncio.get_running_loop()
    t = threading.Thread(target=zmq_reader, args=(loop,), daemon=True)
    t.start()

    async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
        print(f"[WS] server listening on ws://{WS_HOST}:{WS_PORT}")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())