from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from litestar import Litestar
from litestar.config.cors import CORSConfig
from litestar.contrib.jinja import JinjaTemplateEngine
from litestar.di import Provide
from litestar.openapi.config import OpenAPIConfig
from litestar.openapi.plugins import SwaggerRenderPlugin
from litestar.template.config import TemplateConfig
from redis.asyncio import Redis

from el_descentralizador.db import models as _models  # noqa: F401
from el_descentralizador.domain.accounts.auth import session_auth
from el_descentralizador.domain.accounts.services import provide_user_service
from el_descentralizador.domain.articles.deps import provide_article_service
from el_descentralizador.domain.ingestion.deps import provide_ingestion_service
from el_descentralizador.domain.sources.deps import provide_source_service
from el_descentralizador.lib.exceptions import ApplicationError, application_exception_handler
from el_descentralizador.lib.settings import get_settings
from el_descentralizador.server.plugins import (
    create_redis,
    create_stores,
    granian_plugin,
    htmx_plugin,
    saq_plugin,
    sqlalchemy_plugin,
)
from el_descentralizador.server.routers import api_router, web_router
from el_descentralizador.server.seed import seed_if_needed

TEMPLATE_DIR = Path(__file__).parent / "templates"


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncGenerator[None]:
    redis: Redis = app.state.redis
    try:
        await seed_if_needed(app)
        yield
    finally:
        await redis.aclose()


def create_app() -> Litestar:
    settings = get_settings()
    redis = create_redis()
    stores = create_stores(redis)

    app = Litestar(
        route_handlers=[api_router, web_router],
        plugins=[sqlalchemy_plugin, saq_plugin, granian_plugin, htmx_plugin],
        on_app_init=[session_auth.on_app_init],
        template_config=TemplateConfig(
            directory=TEMPLATE_DIR,
            engine=JinjaTemplateEngine,
        ),
        openapi_config=OpenAPIConfig(
            title=settings.name,
            version="0.1.0",
            path="/schema",
            render_plugins=[SwaggerRenderPlugin()],
        ),
        cors_config=CORSConfig(allow_origins=["*"]),
        exception_handlers={ApplicationError: application_exception_handler},
        dependencies={
            "article_service": Provide(provide_article_service),
            "source_service": Provide(provide_source_service),
            "ingestion_service": Provide(provide_ingestion_service),
            "user_service": Provide(provide_user_service),
        },
        stores=stores,
        lifespan=[lifespan],
        debug=settings.debug,
    )
    app.state.redis = redis
    app.state.settings = settings
    return app
