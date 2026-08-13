from typing import Any

from el_descentralizador.lib.schema import CamelizedBaseStruct


class IngestionStatus(CamelizedBaseStruct):
    running: bool
    result: dict[str, Any] | None
    error: str | None
    progress: dict[str, Any] | None


class IngestionQueued(CamelizedBaseStruct):
    status: str
    job_id: str | None = None
