from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, time
from uuid import UUID

from advanced_alchemy.repository import SQLAlchemyAsyncRepository
from advanced_alchemy.service import OffsetPagination, SQLAlchemyAsyncRepositoryService
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from el_descentralizador.db.models.article import Article
from el_descentralizador.db.models.source import Source, SourceKind
from el_descentralizador.domain.articles.schemas import (
    AlsoIn,
    ArticleDetail,
    ArticleListItem,
    DateRange,
    FiltersResponse,
    SourceCount,
)
from el_descentralizador.domain.ingestion.reader import extract_article
from el_descentralizador.lib.constants import PAGE_SIZE, REGION_ORDER
from el_descentralizador.lib.exceptions import NotFoundError


class ArticleService(SQLAlchemyAsyncRepositoryService[Article]):
    class Repo(SQLAlchemyAsyncRepository[Article]):
        model_type = Article

    repository_type = Repo

    async def filters(self) -> FiltersResponse:
        session = self.repository.session
        region_rows = (
            await session.execute(select(Article.region).distinct().where(Article.region.is_not(None)))
        ).all()
        regions = [row[0] for row in region_rows]
        regions.sort(key=lambda name: REGION_ORDER.index(name) if name in REGION_ORDER else 99)

        source_stmt = (
            select(
                Source.id,
                Source.name,
                Source.region,
                Source.kind,
                func.count(Article.id).label("n"),
            )
            .join(Article, Article.source_id == Source.id)
            .group_by(Source.id, Source.name, Source.region, Source.kind)
            .order_by(Source.region, Source.name)
        )
        source_rows = (await session.execute(source_stmt)).all()
        rango = (
            await session.execute(
                select(func.min(Article.published_at), func.max(Article.published_at)).where(
                    Article.published_at.is_not(None)
                )
            )
        ).one()
        return FiltersResponse(
            regions=regions,
            sources=[
                SourceCount(
                    source_id=row.id,
                    name=row.name,
                    region=row.region,
                    kind=row.kind.value,
                    n=row.n,
                )
                for row in source_rows
            ],
            date_range=DateRange(start=rango[0], end=rango[1]),
        )

    def _filtered_query(
        self,
        *,
        region: str | None,
        kind: SourceKind | None,
        source_id: UUID | None,
        q: str | None,
        published_from: date | None,
        published_to: date | None,
    ) -> Select[tuple[Article]]:
        stmt = select(Article).join(Source, Article.source_id == Source.id)
        if region:
            stmt = stmt.where(Article.region == region)
        if kind is not None:
            stmt = stmt.where(Source.kind == kind)
        if source_id is not None:
            stmt = stmt.where(Article.source_id == source_id)
        if published_from is not None:
            start = datetime.combine(published_from, time.min, tzinfo=UTC)
            stmt = stmt.where(Article.published_at >= start)
        if published_to is not None:
            end = datetime.combine(published_to, time.max, tzinfo=UTC)
            stmt = stmt.where(Article.published_at <= end)
        if q:
            tokens = [token for token in q.replace("'", " ").split() if token]
            if tokens:
                tsquery = " & ".join(f"{token}:*" for token in tokens)
                stmt = stmt.where(Article.search_vector.op("@@")(func.to_tsquery("spanish", tsquery)))
        return stmt

    async def list_grouped(
        self,
        *,
        region: str | None = None,
        kind: SourceKind | None = None,
        source_id: UUID | None = None,
        q: str | None = None,
        published_from: date | None = None,
        published_to: date | None = None,
        limit: int = PAGE_SIZE,
        offset: int = 0,
    ) -> OffsetPagination[ArticleListItem]:
        session = self.repository.session
        ranked = (
            self._filtered_query(
                region=region,
                kind=kind,
                source_id=source_id,
                q=q,
                published_from=published_from,
                published_to=published_to,
            )
            .add_columns(
                func.row_number()
                .over(
                    partition_by=func.coalesce(Article.group_id, Article.id),
                    order_by=(Article.published_at.desc().nullslast(), Article.id),
                )
                .label("rn")
            )
            .subquery()
        )
        count_stmt = select(func.count()).select_from(ranked).where(ranked.c.rn == 1)
        total = int(await session.scalar(count_stmt) or 0)
        id_rows = (
            await session.execute(
                select(ranked.c.id)
                .where(ranked.c.rn == 1)
                .order_by(ranked.c.published_at.desc().nulls_last(), ranked.c.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        ordered_ids = [row[0] for row in id_rows]
        if not ordered_ids:
            return OffsetPagination(items=[], limit=limit, offset=offset, total=total)
        loaded = {
            article.id: article
            for article in (
                await session.execute(select(Article).where(Article.id.in_(ordered_ids)))
            )
            .scalars()
            .unique()
            .all()
        }
        articles = [loaded[article_id] for article_id in ordered_ids if article_id in loaded]
        items = [await self._to_list_item(article) for article in articles]
        return OffsetPagination(items=items, limit=limit, offset=offset, total=total)

    async def get_detail(self, article_id: UUID) -> ArticleDetail:
        article = await self.get_one_or_none(id=article_id)
        if article is None:
            raise NotFoundError("Article not found")
        if article.body_html is None:
            try:
                article.body_html = await asyncio.to_thread(
                    extract_article, article.url, article.image_url
                )
            except Exception:
                article.body_html = ""
            await self.repository.session.flush()
        item = await self._to_list_item(article)
        return ArticleDetail(
            id=item.id,
            source_id=item.source_id,
            source_name=item.source_name,
            kind=item.kind,
            region=item.region,
            title=item.title,
            url=item.url,
            published_at=item.published_at,
            summary=item.summary,
            image_url=item.image_url,
            also_in=item.also_in,
            body_html=article.body_html,
        )

    async def _to_list_item(self, article: Article) -> ArticleListItem:
        session = self.repository.session
        others: list[AlsoIn] = []
        if article.group_id is not None:
            other_rows = (
                await session.execute(
                    select(Article, Source.name)
                    .join(Source, Article.source_id == Source.id)
                    .where(Article.group_id == article.group_id, Article.id != article.id)
                )
            ).all()
            others = [AlsoIn(source_name=name, url=other.url) for other, name in other_rows]
        source = article.source
        return ArticleListItem(
            id=article.id,
            source_id=article.source_id,
            source_name=source.name,
            kind=source.kind.value,
            region=article.region,
            title=article.title,
            url=article.url,
            published_at=article.published_at,
            summary=article.summary,
            image_url=article.image_url,
            also_in=others,
        )


async def provide_article_service(db_session: AsyncSession) -> AsyncGenerator[ArticleService]:
    async with ArticleService.new(session=db_session) as service:
        yield service
