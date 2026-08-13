from __future__ import annotations

from litestar import Router

from el_descentralizador.domain.accounts.controllers import AuthController
from el_descentralizador.domain.articles.controllers import ArticleController, FilterController
from el_descentralizador.domain.ingestion.controllers import IngestionController
from el_descentralizador.domain.sources.controllers import SourceController
from el_descentralizador.domain.web.controllers import HealthController, WebController
from el_descentralizador.domain.web.partials import PartialController

api_router = Router(
    path="/api/v1",
    route_handlers=[
        FilterController,
        ArticleController,
        SourceController,
        IngestionController,
        AuthController,
    ],
)

web_router = Router(
    path="/",
    route_handlers=[HealthController, WebController, PartialController],
)
