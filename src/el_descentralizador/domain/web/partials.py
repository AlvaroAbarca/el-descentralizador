from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from litestar import Controller, get, patch
from litestar.enums import RequestEncodingType
from litestar.params import Body, FromPath, QueryParameter
from litestar.response import Template
from litestar_htmx import HTMXTemplate

from el_descentralizador.db.models.source import CurationStatus, SourceKind
from el_descentralizador.domain.accounts.guards import requires_admin
from el_descentralizador.domain.articles.services import ArticleService
from el_descentralizador.domain.sources.schemas import CurationForm, SourceRead
from el_descentralizador.domain.sources.services import SourceService
from el_descentralizador.lib.constants import PAGE_SIZE
from el_descentralizador.lib.dates import format_short
from el_descentralizador.lib.di import Injected
from el_descentralizador.lib.exceptions import DependencyError, NotFoundError, ValidationError

STATUS_UI = {
    None: "pendiente",
    CurationStatus.APPROVED: "aprobado",
    CurationStatus.FIX: "arreglar",
    CurationStatus.DISCARDED: "descartado",
}


def _kind_from_path(kind: str) -> SourceKind:
    if kind in {"media", "municipality"}:
        return SourceKind(kind)
    if kind == "municipalities":
        return SourceKind.MUNICIPALITY
    raise NotFoundError("Unknown curator kind")


class PartialController(Controller):
    path = "/partials"
    tags = ["HTMX"]

    @get("/articles")
    async def articles(
        self,
        article_service: Injected[ArticleService],
        q: str | None = None,
        region: str | None = None,
        kind: SourceKind | None = None,
        source_id: Annotated[UUID | None, QueryParameter(name="sourceId")] = None,
        published_from: Annotated[date | None, QueryParameter(name="from")] = None,
        published_to: Annotated[date | None, QueryParameter(name="to")] = None,
        limit: int = PAGE_SIZE,
        offset: int = 0,
    ) -> Template:
        page = await article_service.list_grouped(
            region=region,
            kind=kind,
            source_id=source_id,
            q=q,
            published_from=published_from,
            published_to=published_to,
            limit=min(limit, 100),
            offset=max(offset, 0),
        )
        shown = offset + len(page.items)
        return HTMXTemplate(
            template_name="partials/articles.html",
            context={
                "items": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "region": item.region,
                        "source_name": item.source_name,
                        "kind": item.kind,
                        "url": item.url,
                        "image_url": item.image_url,
                        "published_at": item.published_at,
                        "published_label": format_short(item.published_at),
                        "summary": item.summary,
                        "also_in": item.also_in,
                    }
                    for item in page.items
                ],
                "total": page.total,
                "shown": shown,
                "has_more": shown < page.total,
            },
            push_url=False,
        )

    @get("/curator/{kind:str}", guards=[requires_admin])
    async def curator_card(
        self,
        source_service: Injected[SourceService],
        kind: FromPath[str],
    ) -> Template:
        source_kind = _kind_from_path(kind)
        source = await source_service.next_pending(source_kind)
        return self._curator_template(source, source_kind, await source_service.list_for_curator(kind=source_kind))

    @patch("/sources/{source_id:uuid}/curation", guards=[requires_admin])
    async def classify(
        self,
        source_service: Injected[SourceService],
        source_id: FromPath[UUID],
        data: Annotated[CurationForm, Body(media_type=RequestEncodingType.URL_ENCODED)],
        kind: str | None = None,
    ) -> Template:
        updated = await source_service.patch_curation(source_id, data.status, data.comment)
        source_kind = _kind_from_path(kind) if kind else updated.kind
        nxt = await source_service.next_pending(source_kind, skip_id=source_id)
        sources = await source_service.list_for_curator(kind=source_kind)
        return self._curator_template(nxt, source_kind, sources)

    @get("/sources/{source_id:uuid}/sample", guards=[requires_admin])
    async def sample(
        self,
        source_service: Injected[SourceService],
        source_id: FromPath[UUID],
    ) -> Template:
        try:
            sample = await source_service.sample_feed(source_id)
        except (DependencyError, ValidationError, NotFoundError) as exc:
            return HTMXTemplate(
                template_name="partials/feed_sample.html",
                context={"error": exc.detail, "entries": []},
                push_url=False,
            )
        return HTMXTemplate(
            template_name="partials/feed_sample.html",
            context={
                "error": None,
                "entries": [
                    {
                        "title": entry.title,
                        "url": entry.url,
                        "summary": entry.summary,
                        "image_url": entry.image_url,
                        "published_label": format_short(entry.published_at),
                    }
                    for entry in sample.entries
                ],
            },
            push_url=False,
        )

    def _curator_template(
        self,
        source: SourceRead | None,
        kind: SourceKind,
        sources: list[SourceRead],
    ) -> Template:
        position = 1
        if source is not None:
            for index, item in enumerate(sources, start=1):
                if item.id == source.id:
                    position = index
                    break
        path_kind = "municipalities" if kind is SourceKind.MUNICIPALITY else "media"
        return HTMXTemplate(
            template_name="partials/curator_card.html",
            context={
                "source": source,
                "kind": path_kind,
                "position": position,
                "total": len(sources),
                "status_ui": STATUS_UI.get(source.curation_status if source else None, "pendiente"),
            },
            push_url=False,
        )
