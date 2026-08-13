from __future__ import annotations

from litestar import Controller, get, post
from litestar.status_codes import HTTP_202_ACCEPTED
from litestar_saq import TaskQueues

from el_descentralizador.domain.accounts.guards import requires_admin
from el_descentralizador.domain.ingestion.deps import IngestionService
from el_descentralizador.domain.ingestion.schemas import IngestionQueued, IngestionStatus
from el_descentralizador.lib.di import Injected
from el_descentralizador.lib.exceptions import ConflictError


class IngestionController(Controller):
    path = "/ingestion-jobs"
    tags = ["Ingestion"]
    guards = [requires_admin]

    @post("/", status_code=HTTP_202_ACCEPTED)
    async def enqueue(
        self,
        task_queues: Injected[TaskQueues],
    ) -> IngestionQueued:
        queue = task_queues.get("ingestion")
        job = await queue.enqueue(
            "run_ingest",
            timeout=600,
            retries=0,
            key="ingest-run",
            heartbeat=90,
        )
        if job is None:
            raise ConflictError("Ingestion already running")
        return IngestionQueued(status="queued", job_id=getattr(job, "id", None))

    @get("/current")
    async def current(
        self,
        ingestion_service: Injected[IngestionService],
    ) -> IngestionStatus:
        return await ingestion_service.current()
