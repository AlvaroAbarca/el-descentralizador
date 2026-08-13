from datetime import datetime
from uuid import UUID

from el_descentralizador.lib.schema import CamelizedBaseStruct


class AlsoIn(CamelizedBaseStruct):
    source_name: str
    url: str


class ArticleListItem(CamelizedBaseStruct):
    id: UUID
    source_id: UUID
    source_name: str
    kind: str
    region: str
    title: str
    url: str
    published_at: datetime | None
    summary: str | None
    image_url: str | None
    also_in: list[AlsoIn]


class ArticleDetail(ArticleListItem):
    body_html: str | None


class SourceCount(CamelizedBaseStruct):
    source_id: UUID
    name: str
    region: str
    kind: str
    n: int


class DateRange(CamelizedBaseStruct):
    start: datetime | None
    end: datetime | None


class FiltersResponse(CamelizedBaseStruct):
    regions: list[str]
    sources: list[SourceCount]
    date_range: DateRange
