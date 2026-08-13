from datetime import datetime
from uuid import UUID

import msgspec

from el_descentralizador.db.models.source import CurationStatus, SourceKind
from el_descentralizador.lib.schema import CamelizedBaseStruct


class SourceRead(CamelizedBaseStruct):
    id: UUID
    name: str
    region: str
    url: str
    feed_url: str | None
    kind: SourceKind
    has_rss: bool
    site_live: bool
    is_active: bool
    curation_status: CurationStatus | None
    curation_comment: str | None
    curated_at: datetime | None


class CurationPatch(CamelizedBaseStruct):
    status: CurationStatus
    comment: str | None = None


class CurationForm(msgspec.Struct, kw_only=True):
    status: CurationStatus
    comment: str | None = None


class FeedEntry(CamelizedBaseStruct):
    title: str
    url: str
    published_at: datetime | None
    summary: str
    image_url: str | None


class FeedSample(CamelizedBaseStruct):
    title: str
    entries: list[FeedEntry]
