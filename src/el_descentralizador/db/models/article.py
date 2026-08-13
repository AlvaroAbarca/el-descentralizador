from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from advanced_alchemy.base import UUIDv7AuditBase
from advanced_alchemy.types import DateTimeUTC
from sqlalchemy import Computed, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from el_descentralizador.db.models.source import Source


class Article(UUIDv7AuditBase):
    """Indexed news item."""

    __tablename__ = "article"
    __table_args__ = (
        Index("ix_article_search", "search_vector", postgresql_using="gin"),
        Index("ix_article_published_at", "published_at"),
        Index("ix_article_region", "region"),
        Index("ix_article_group_id", "group_id"),
    )

    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("source.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(1024), unique=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTimeUTC, default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    image_url: Mapped[str | None] = mapped_column(String(1024), default=None)
    body_html: Mapped[str | None] = mapped_column(Text, default=None)
    title_norm: Mapped[str | None] = mapped_column(String(512), default=None, index=True)
    region: Mapped[str] = mapped_column(String(64))
    group_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("article.id", ondelete="SET NULL"),
        default=None,
    )
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('spanish', coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('spanish', coalesce(summary, '')), 'B')",
            persisted=True,
        ),
        deferred=True,
    )

    source: Mapped[Source] = relationship(back_populates="articles", lazy="selectin")
    group: Mapped[Article | None] = relationship(
        remote_side="Article.id",
        foreign_keys=[group_id],
        lazy="noload",
    )
