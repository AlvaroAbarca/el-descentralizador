from __future__ import annotations

import os
from datetime import UTC

import pytest
from sqlalchemy.ext.asyncio import create_async_engine


def postgres_available() -> bool:
    url = os.environ.get("DATABASE_URL", "")
    return url.startswith("postgresql")


@pytest.mark.anyio
@pytest.mark.skipif(not postgres_available(), reason="DATABASE_URL postgres is required for FTS tests")
async def test_tsvector_search() -> None:
    from datetime import datetime
    from uuid import uuid4

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from el_descentralizador.db.models.article import Article
    from el_descentralizador.db.models.source import Source, SourceKind
    from el_descentralizador.domain.articles.services import ArticleService

    engine = create_async_engine(os.environ["DATABASE_URL"])
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        source = Source(
            name=f"Test {uuid4()}",
            region="Los Ríos",
            url="https://example.test",
            kind=SourceKind.MEDIA,
            has_rss=True,
        )
        session.add(source)
        await session.flush()
        session.add(
            Article(
                source_id=source.id,
                title="Nevazones en Valdivia cierran rutas",
                url=f"https://example.test/{uuid4()}",
                published_at=datetime.now(UTC),
                summary="La nieve cubrió la cordillera de Los Ríos.",
                region="Los Ríos",
            )
        )
        await session.commit()
        async with ArticleService.new(session=session) as service:
            page = await service.list_grouped(q="Valdivia")
            assert page.total >= 1
    await engine.dispose()
