from __future__ import annotations

from litestar import Request
from redis.asyncio import Redis

from el_descentralizador.domain.ingestion.progress import read_progress
from el_descentralizador.domain.ingestion.schemas import IngestionStatus


class IngestionService:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    async def current(self) -> IngestionStatus:
        payload = await read_progress(self.redis)
        return IngestionStatus(
            running=bool(payload.get("running")),
            result=payload.get("result"),
            error=payload.get("error"),
            progress=payload.get("progress"),
        )


async def provide_ingestion_service(request: Request) -> IngestionService:
    return IngestionService(redis=request.app.state.redis)
