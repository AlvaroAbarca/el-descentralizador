"""initial schema

Revision ID: 20260812_0001
Revises:
Create Date: 2026-08-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260812_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    source_kind = postgresql.ENUM("media", "municipality", name="source_kind")
    curation_status = postgresql.ENUM("approved", "fix", "discarded", name="curation_status")
    source_kind.create(op.get_bind(), checkfirst=True)
    curation_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "user_account",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sa_orm_sentinel", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_user_account"),
        sa.UniqueConstraint("username", name="uq_user_account_username"),
    )
    op.create_index("ix_user_account_username", "user_account", ["username"], unique=True)

    op.create_table(
        "source",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("feed_url", sa.String(length=512), nullable=True),
        sa.Column("kind", postgresql.ENUM("media", "municipality", name="source_kind", create_type=False), nullable=False),
        sa.Column("has_rss", sa.Boolean(), nullable=False),
        sa.Column("site_live", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "curation_status",
            postgresql.ENUM("approved", "fix", "discarded", name="curation_status", create_type=False),
            nullable=True,
        ),
        sa.Column("curation_comment", sa.Text(), nullable=True),
        sa.Column("curated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sa_orm_sentinel", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_source"),
        sa.UniqueConstraint("name", name="uq_source_name"),
    )
    op.create_index("ix_source_name", "source", ["name"], unique=True)
    op.create_index("ix_source_region", "source", ["region"])
    op.create_index("ix_source_kind", "source", ["kind"])

    op.create_table(
        "article",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=1024), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("title_norm", sa.String(length=512), nullable=True),
        sa.Column("region", sa.String(length=64), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=True),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('spanish', coalesce(title, '')), 'A') || "
                "setweight(to_tsvector('spanish', coalesce(summary, '')), 'B')",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("sa_orm_sentinel", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["source.id"], name="fk_article_source_id_source", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["article.id"], name="fk_article_group_id_article", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_article"),
        sa.UniqueConstraint("url", name="uq_article_url"),
    )
    op.create_index("ix_article_source_id", "article", ["source_id"])
    op.create_index("ix_article_title_norm", "article", ["title_norm"])
    op.create_index("ix_article_published_at", "article", ["published_at"])
    op.create_index("ix_article_region", "article", ["region"])
    op.create_index("ix_article_group_id", "article", ["group_id"])
    op.create_index("ix_article_search", "article", ["search_vector"], postgresql_using="gin")


def downgrade() -> None:
    op.drop_index("ix_article_search", table_name="article")
    op.drop_index("ix_article_group_id", table_name="article")
    op.drop_index("ix_article_region", table_name="article")
    op.drop_index("ix_article_published_at", table_name="article")
    op.drop_index("ix_article_title_norm", table_name="article")
    op.drop_index("ix_article_source_id", table_name="article")
    op.drop_table("article")
    op.drop_index("ix_source_kind", table_name="source")
    op.drop_index("ix_source_region", table_name="source")
    op.drop_index("ix_source_name", table_name="source")
    op.drop_table("source")
    op.drop_index("ix_user_account_username", table_name="user_account")
    op.drop_table("user_account")
    op.execute("DROP TYPE IF EXISTS curation_status")
    op.execute("DROP TYPE IF EXISTS source_kind")
