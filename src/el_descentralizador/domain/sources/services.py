from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import feedparser
import httpx
from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import SQLAlchemyAsyncRepositoryService
from sqlalchemy.ext.asyncio import AsyncSession

from el_descentralizador.db.models.source import CurationStatus, Source, SourceKind
from el_descentralizador.domain.ingestion.html import clean_html
from el_descentralizador.domain.ingestion.http import USER_AGENT
from el_descentralizador.domain.ingestion.pipeline import extract_date, extract_image
from el_descentralizador.domain.sources.schemas import FeedEntry, FeedSample, SourceRead
from el_descentralizador.lib.exceptions import DependencyError, NotFoundError, ValidationError


class SourceService(SQLAlchemyAsyncRepositoryService[Source]):
    class Repo(SQLAlchemyAsyncRepository[Source]):
        model_type = Source

    repository_type = Repo

    async def list_for_curator(self, kind: SourceKind | None = None) -> list[SourceRead]:
        filters: dict[str, object] = {}
        if kind is not None:
            filters["kind"] = kind
        sources = await self.list(**filters)
        order = {None: 0, CurationStatus.FIX: 1, CurationStatus.APPROVED: 2, CurationStatus.DISCARDED: 3}
        sources.sort(
            key=lambda src: (
                order.get(src.curation_status, 9),
                0 if src.has_rss else 1,
                src.name,
            )
        )
        return [self._to_read(src) for src in sources]

    async def next_pending(
        self,
        kind: SourceKind | None,
        *,
        skip_id: object | None = None,
    ) -> SourceRead | None:
        sources = await self.list_for_curator(kind=kind)
        pending = [src for src in sources if src.curation_status is None and src.id != skip_id]
        if pending:
            return pending[0]
        remaining = [src for src in sources if src.id != skip_id]
        return remaining[0] if remaining else None

    async def source_position(self, kind: SourceKind | None, source_id: object) -> tuple[int, int]:
        sources = await self.list_for_curator(kind=kind)
        for index, src in enumerate(sources, start=1):
            if src.id == source_id:
                return index, len(sources)
        return 1, len(sources)

    async def patch_curation(
        self,
        source_id: object,
        status: CurationStatus,
        comment: str | None,
    ) -> SourceRead:
        source = await self.get_one_or_none(id=source_id)
        if source is None:
            raise NotFoundError("Source not found")
        source.curation_status = status
        source.curation_comment = comment
        source.curated_at = datetime.now(UTC)
        await self.repository.session.flush()
        return self._to_read(source)

    async def reset_curation(self, source_id: object) -> SourceRead:
        source = await self.get_one_or_none(id=source_id)
        if source is None:
            raise NotFoundError("Source not found")
        source.curation_status = None
        source.curation_comment = None
        source.curated_at = None
        await self.repository.session.flush()
        return self._to_read(source)

    async def sample_feed(self, source_id: object) -> FeedSample:
        source = await self.get_one_or_none(id=source_id)
        if source is None:
            raise NotFoundError("Source not found")
        if not source.feed_url:
            raise ValidationError("Source has no feed URL")
        try:
            async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=15) as client:
                response = await client.get(source.feed_url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise DependencyError(f"{type(exc).__name__}: {exc}") from exc
        feed = feedparser.parse(response.content)
        entries: list[FeedEntry] = []
        for entry in feed.entries[:10]:
            html = ""
            if entry.get("content"):
                html = entry.content[0].get("value", "")
            if not html:
                html = entry.get("summary", "")
            summary, image_from_html = clean_html(html)
            image = extract_image(entry, image_from_html)
            published = extract_date(entry)
            entries.append(
                FeedEntry(
                    title=(entry.get("title") or "").strip(),
                    url=(entry.get("link") or "").strip(),
                    published_at=published,
                    summary=summary[:400],
                    image_url=image,
                )
            )
        title = ""
        if feed.feed:
            title = feed.feed.get("title") or ""
        return FeedSample(title=title, entries=entries)

    def _to_read(self, source: Source) -> SourceRead:
        return SourceRead(
            id=source.id,
            name=source.name,
            region=source.region,
            url=source.url,
            feed_url=source.feed_url,
            kind=source.kind,
            has_rss=source.has_rss,
            site_live=source.site_live,
            is_active=source.is_active,
            curation_status=source.curation_status,
            curation_comment=source.curation_comment,
            curated_at=source.curated_at,
        )


async def provide_source_service(db_session: AsyncSession) -> AsyncGenerator[SourceService]:
    async with SourceService.new(session=db_session) as service:
        yield service
