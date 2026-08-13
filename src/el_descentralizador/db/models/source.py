import enum
from datetime import datetime
from typing import TYPE_CHECKING

from advanced_alchemy.base import UUIDv7AuditBase
from advanced_alchemy.types import DateTimeUTC
from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from el_descentralizador.db.models.article import Article


class SourceKind(enum.StrEnum):
    MEDIA = "media"
    MUNICIPALITY = "municipality"


class CurationStatus(enum.StrEnum):
    APPROVED = "approved"
    FIX = "fix"
    DISCARDED = "discarded"


class Source(UUIDv7AuditBase):
    """Regional outlet or municipality feed."""

    __tablename__ = "source"

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    region: Mapped[str] = mapped_column(String(64), index=True)
    url: Mapped[str] = mapped_column(String(512))
    feed_url: Mapped[str | None] = mapped_column(String(512), default=None)
    kind: Mapped[SourceKind] = mapped_column(
        Enum(SourceKind, name="source_kind", native_enum=True, values_callable=lambda x: [e.value for e in x]),
        index=True,
    )
    has_rss: Mapped[bool] = mapped_column(default=False)
    site_live: Mapped[bool] = mapped_column(default=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    curation_status: Mapped[CurationStatus | None] = mapped_column(
        Enum(
            CurationStatus,
            name="curation_status",
            native_enum=True,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=None,
    )
    curation_comment: Mapped[str | None] = mapped_column(Text, default=None)
    curated_at: Mapped[datetime | None] = mapped_column(DateTimeUTC, default=None)

    articles: Mapped[list[Article]] = relationship(back_populates="source", lazy="noload")
