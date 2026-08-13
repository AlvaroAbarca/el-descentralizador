from time import time

from litestar_saq import monitored_job

from el_descentralizador.domain.ingestion.pipeline import run_pipeline
from el_descentralizador.domain.ingestion.progress import write_progress
from el_descentralizador.lib.settings import get_settings


@monitored_job()
async def run_ingest(ctx: dict) -> dict:
    """Download feeds, persist articles, rescue images, and dedupe."""
    from redis.asyncio import Redis
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    settings = get_settings()
    engine = create_async_engine(settings.database.url)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    redis = Redis.from_url(settings.redis.url)
    progress = {"phase": "starting", "done": 0, "total": 0, "started_at": time()}
    await write_progress(
        redis,
        {"running": True, "result": None, "error": None, "progress": progress},
    )
    try:
        result = await run_pipeline(session_maker, progress=progress)
        await write_progress(
            redis,
            {"running": False, "result": result, "error": None, "progress": progress},
        )
        return result
    except Exception as exc:
        await write_progress(
            redis,
            {"running": False, "result": None, "error": str(exc), "progress": progress},
        )
        raise
    finally:
        await engine.dispose()
        await redis.aclose()
