from __future__ import annotations

from uuid import UUID

from litestar import Controller, delete, get, patch
from litestar.params import FromPath

from el_descentralizador.db.models.source import SourceKind
from el_descentralizador.domain.accounts.guards import requires_admin
from el_descentralizador.domain.sources.schemas import CurationPatch, FeedSample, SourceRead
from el_descentralizador.domain.sources.services import SourceService
from el_descentralizador.lib.di import Injected


class SourceController(Controller):
    path = "/sources"
    tags = ["Sources"]
    guards = [requires_admin]

    @get("/")
    async def list_sources(
        self,
        source_service: Injected[SourceService],
        kind: SourceKind | None = None,
    ) -> list[SourceRead]:
        return await source_service.list_for_curator(kind=kind)

    @get("/{source_id:uuid}/sample")
    async def sample(
        self,
        source_service: Injected[SourceService],
        source_id: FromPath[UUID],
    ) -> FeedSample:
        return await source_service.sample_feed(source_id)

    @patch("/{source_id:uuid}/curation")
    async def patch_curation(
        self,
        source_service: Injected[SourceService],
        source_id: FromPath[UUID],
        data: CurationPatch,
    ) -> SourceRead:
        return await source_service.patch_curation(source_id, data.status, data.comment)

    @delete("/{source_id:uuid}/curation", status_code=200)
    async def reset_curation(
        self,
        source_service: Injected[SourceService],
        source_id: FromPath[UUID],
    ) -> SourceRead:
        return await source_service.reset_curation(source_id)
