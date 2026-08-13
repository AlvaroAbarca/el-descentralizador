from __future__ import annotations

import pytest
from litestar import Litestar
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.di import Provide
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_202_ACCEPTED,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_409_CONFLICT,
)
from litestar.stores.memory import MemoryStore
from litestar.template.config import TemplateConfig
from litestar.testing import AsyncTestClient

from el_descentralizador.domain.accounts.auth import session_auth
from el_descentralizador.lib.exceptions import ApplicationError, application_exception_handler
from el_descentralizador.server.routers import api_router, web_router
from tests.conftest import (
    TEMPLATE_DIR,
    FakeJob,
    FakeTaskQueues,
    _provide_articles,
    _provide_db,
    _provide_ingestion,
    _provide_sources,
    _provide_user,
)


@pytest.mark.anyio
async def test_health(client: AsyncTestClient) -> None:
    response = await client.get("/health")
    assert response.status_code == HTTP_200_OK
    assert response.json()["status"] == "ok"


@pytest.mark.anyio
async def test_public_home(client: AsyncTestClient) -> None:
    response = await client.get("/")
    assert response.status_code == HTTP_200_OK
    assert "El Descentralizador" in response.text


@pytest.mark.anyio
async def test_filters_public(client: AsyncTestClient) -> None:
    response = await client.get("/api/v1/filters")
    assert response.status_code == HTTP_200_OK
    body = response.json()
    assert body["regions"] == ["Los Ríos"]
    assert "dateRange" in body


@pytest.mark.anyio
async def test_articles_list_public(client: AsyncTestClient) -> None:
    response = await client.get("/api/v1/articles")
    assert response.status_code == HTTP_200_OK
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["sourceName"] == "Diario Test"
    assert body["items"][0]["title"] == "Nevazón en Valdivia"


@pytest.mark.anyio
async def test_article_detail_public(client: AsyncTestClient) -> None:
    listing = await client.get("/api/v1/articles")
    article_id = listing.json()["items"][0]["id"]
    response = await client.get(f"/api/v1/articles/{article_id}")
    assert response.status_code == HTTP_200_OK
    assert response.json()["bodyHtml"] == "<p>Cuerpo</p>"


@pytest.mark.anyio
async def test_articles_partial_html(client: AsyncTestClient) -> None:
    response = await client.get("/partials/articles")
    assert response.status_code == HTTP_200_OK
    assert "Nevazón en Valdivia" in response.text
    assert 'class="pieza"' in response.text


@pytest.mark.anyio
async def test_ingestion_requires_auth(client: AsyncTestClient) -> None:
    response = await client.post("/api/v1/ingestion-jobs")
    assert response.status_code in {HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN}


@pytest.mark.anyio
async def test_sources_require_auth(client: AsyncTestClient) -> None:
    response = await client.get("/api/v1/sources")
    assert response.status_code in {HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN}


@pytest.mark.anyio
async def test_curator_requires_auth(client: AsyncTestClient) -> None:
    response = await client.get("/curator/media", headers={"accept": "application/json"})
    assert response.status_code in {HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN}


@pytest.mark.anyio
async def test_login_page(client: AsyncTestClient) -> None:
    response = await client.get("/login")
    assert response.status_code == HTTP_200_OK
    assert "Entrar" in response.text


@pytest.mark.anyio
async def test_login_sets_session_cookie(client: AsyncTestClient) -> None:
    response = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
    assert response.status_code == HTTP_200_OK
    assert response.json()["username"] == "admin"
    assert response.cookies


@pytest.mark.anyio
async def test_login_rejects_bad_password(client: AsyncTestClient) -> None:
    response = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "nope"})
    assert response.status_code in {HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN}


@pytest.mark.anyio
async def test_enqueue_ingest_when_authenticated() -> None:
    async def queues() -> FakeTaskQueues:
        return FakeTaskQueues(FakeJob())

    app = Litestar(
        route_handlers=[api_router, web_router],
        on_app_init=[session_auth.on_app_init],
        template_config=TemplateConfig(directory=TEMPLATE_DIR, engine=JinjaTemplateEngine),
        stores={"sessions": MemoryStore()},
        exception_handlers={ApplicationError: application_exception_handler},
        dependencies={
            "article_service": Provide(_provide_articles),
            "source_service": Provide(_provide_sources),
            "ingestion_service": Provide(_provide_ingestion),
            "task_queues": Provide(queues),
            "user_service": Provide(_provide_user),
            "db_session": Provide(_provide_db),
        },
        debug=True,
    )
    async with AsyncTestClient(app=app) as client:
        await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
        response = await client.post("/api/v1/ingestion-jobs")
        assert response.status_code == HTTP_202_ACCEPTED
        assert response.json()["status"] == "queued"


@pytest.mark.anyio
async def test_enqueue_ingest_duplicate() -> None:
    async def queues() -> FakeTaskQueues:
        return FakeTaskQueues(None)

    app = Litestar(
        route_handlers=[api_router, web_router],
        on_app_init=[session_auth.on_app_init],
        template_config=TemplateConfig(directory=TEMPLATE_DIR, engine=JinjaTemplateEngine),
        stores={"sessions": MemoryStore()},
        exception_handlers={ApplicationError: application_exception_handler},
        dependencies={
            "article_service": Provide(_provide_articles),
            "source_service": Provide(_provide_sources),
            "ingestion_service": Provide(_provide_ingestion),
            "task_queues": Provide(queues),
            "user_service": Provide(_provide_user),
            "db_session": Provide(_provide_db),
        },
        debug=True,
    )
    async with AsyncTestClient(app=app) as client:
        await client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin"})
        response = await client.post("/api/v1/ingestion-jobs")
        assert response.status_code == HTTP_409_CONFLICT
