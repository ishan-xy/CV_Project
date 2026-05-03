import json
import asyncio
from pathlib import Path

INDEX_PATH = Path("booking_index.json")
_lock = asyncio.Lock()


def _read() -> dict:
    if not INDEX_PATH.exists():
        return {}
    try:
        return json.loads(INDEX_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write(index: dict) -> None:
    INDEX_PATH.write_text(json.dumps(index, indent=2))


async def index_add(booking_id: str, name: str) -> None:
    async with _lock:
        index = _read()
        index[booking_id] = name
        _write(index)


async def index_remove(booking_id: str) -> None:
    async with _lock:
        index = _read()
        index.pop(booking_id, None)
        _write(index)


def lookup(booking_id: str) -> str | None:
    return _read().get(booking_id)