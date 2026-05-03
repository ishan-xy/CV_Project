import json
import asyncio
import zmq
from datetime import datetime

_context: zmq.Context = None
_socket: zmq.Socket = None


def init_publisher():
    global _context, _socket
    _context = zmq.Context()
    _socket = _context.socket(zmq.PUB)
    _socket.bind("tcp://127.0.0.1:5560")


def close_publisher():
    global _socket, _context
    if _socket:
        _socket.close()
    if _context:
        _context.term()


def _publish(event: str, booking_id: str):
    payload = json.dumps({"event": event, "booking_id": booking_id, "ts": datetime.utcnow().isoformat()})
    _socket.send_string(payload)


async def publish_photo_stored(booking_id: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _publish, "photo.stored", booking_id)


async def publish_photo_deleted(booking_id: str):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _publish, "photo.deleted", booking_id)