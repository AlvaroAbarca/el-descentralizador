from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from advanced_alchemy.service import OffsetPagination
from litestar import Litestar
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.di import Provide
from litestar.stores.memory import MemoryStore
from litestar.template.config import TemplateConfig
from litestar.testing import AsyncTestClient

from el_descentralizador.db.models.source import SourceKind
from el_descentralizador.domain.accounts.auth import session_auth
from el_descentralizador.domain.articles.schemas import ArticleDetail, ArticleListItem, DateRange, FiltersResponse
from el_descentralizador.domain.ingestion.schemas import IngestionStatus
from el_descentralizador.lib.exceptions import ApplicationError, application_exception_handler
from el_descentralizador.server.routers import api_router, web_router

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "src/el_descentralizador/server/templates"
ARTICLE_ID = uuid4()
SOURCE_ID = uuid4()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeUser:
    id = uuid4()
    username = "admin"


class FakeUserService:
    async def authenticate(self, username: str, password: str) -> FakeUser | None:
        if username == "admin" and password == "admin":
            return FakeUser()
        return None


class FakeArticleService:
    async def filters(self) -> FiltersResponse:
        return FiltersResponse(regions=["Los Ríos"], sources=[], date_range=DateRange(start=None, end=None))

    async def list_grouped(self, **_kwargs: object) -> OffsetPagination[ArticleListItem]:
        item = ArticleListItem(
            id=ARTICLE_ID,
            source_id=SOURCE_ID,
            source_name="Diario Test",
            kind=SourceKind.MEDIA.value,
            region="Los Ríos",
            title="Nevazón en Valdivia",
            url="https://example.test/nieve",
            published_at=datetime(2026, 8, 12, tzinfo=UTC),
            summary="Cayeron 20 cm de nieve.",
            image_url=None,
            also_in=[],
        )
        return OffsetPagination(items=[item], limit=24, offset=0, total=1)

    async def get_detail(self, article_id: object) -> ArticleDetail:
        page = await self.list_grouped()
        item = page.items[0]
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
            body_html="<p>Cuerpo</p>",
        )


class FakeQueue:
    def __init__(self, job: object | None) -> None:
        self._job = job

    async def enqueue(self, *_args: object, **_kwargs: object) -> object | None:
        return self._job


class FakeJob:
    id = "job-1"


class FakeTaskQueues:
    def __init__(self, job: object | None = FakeJob()) -> None:
        self._queue = FakeQueue(job)

    def get(self, _name: str) -> FakeQueue:
        return self._queue


class FakeIngestionService:
    async def current(self) -> IngestionStatus:
        return IngestionStatus(running=False, result=None, error=None, progress=None)


class FakeSourceService:
    async def list_for_curator(self, kind: object = None) -> list:
        return []

    async def next_pending(self, kind: object = None, *, skip_id: object = None) -> None:
        return None

    async def patch_curation(self, source_id: object, status: object, comment: str | None) -> None:
        return None

    async def sample_feed(self, source_id: object) -> None:
        return None


async def _provide_articles() -> FakeArticleService:
    return FakeArticleService()


async def _provide_sources() -> FakeSourceService:
    return FakeSourceService()


async def _provide_ingestion() -> FakeIngestionService:
    return FakeIngestionService()


async def _provide_queues() -> FakeTaskQueues:
    return FakeTaskQueues()


async def _provide_user() -> FakeUserService:
    return FakeUserService()


async def _provide_db() -> object:
    return object()


@pytest.fixture
def app() -> Litestar:
    return Litestar(
        route_handlers=[api_router, web_router],
        on_app_init=[session_auth.on_app_init],
        template_config=TemplateConfig(directory=TEMPLATE_DIR, engine=JinjaTemplateEngine),
        stores={"sessions": MemoryStore()},
        exception_handlers={ApplicationError: application_exception_handler},
        dependencies={
            "article_service": Provide(_provide_articles),
            "source_service": Provide(_provide_sources),
            "ingestion_service": Provide(_provide_ingestion),
            "task_queues": Provide(_provide_queues),
            "user_service": Provide(_provide_user),
            "db_session": Provide(_provide_db),
        },
    )


@pytest.fixture
async def client(app: Litestar) -> AsyncGenerator[AsyncTestClient]:
    async with AsyncTestClient(app=app) as test_client:
        yield test_client
