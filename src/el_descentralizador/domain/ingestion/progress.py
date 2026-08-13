from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis

PROGRESS_KEY = "ingest:current"


async def write_progress(redis: Redis, payload: dict[str, Any]) -> None:
    await redis.set(PROGRESS_KEY, json.dumps(payload), ex=60 * 60)


async def read_progress(redis: Redis) -> dict[str, Any]:
    raw = await redis.get(PROGRESS_KEY)
    if not raw:
        return {"running": False, "result": None, "error": None, "progress": None}
    if isinstance(raw, bytes):
        raw = raw.decode()
    return json.loads(raw)
