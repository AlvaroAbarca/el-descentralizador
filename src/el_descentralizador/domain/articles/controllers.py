from __future__ import annotations

from datetime import date
from typing import Annotated
from uuid import UUID

from advanced_alchemy.service import OffsetPagination
from litestar import Controller, get
from litestar.params import FromPath, QueryParameter

from el_descentralizador.db.models.source import SourceKind
from el_descentralizador.domain.articles.schemas import ArticleDetail, ArticleListItem, FiltersResponse
from el_descentralizador.domain.articles.services import ArticleService
from el_descentralizador.lib.constants import PAGE_SIZE
from el_descentralizador.lib.di import Injected


class FilterController(Controller):
    path = "/filters"
    tags = ["Filters"]

    @get("/")
    async def get_filters(
        self,
        article_service: Injected[ArticleService],
    ) -> FiltersResponse:
        return await article_service.filters()


class ArticleController(Controller):
    path = "/articles"
    tags = ["Articles"]

    @get("/")
    async def list_articles(
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
    ) -> OffsetPagination[ArticleListItem]:
        return await article_service.list_grouped(
            region=region,
            kind=kind,
            source_id=source_id,
            q=q,
            published_from=published_from,
            published_to=published_to,
            limit=min(limit, 100),
            offset=max(offset, 0),
        )

    @get("/{article_id:uuid}")
    async def get_article(
        self,
        article_service: Injected[ArticleService],
        article_id: FromPath[UUID],
    ) -> ArticleDetail:
        return await article_service.get_detail(article_id)
