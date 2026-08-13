from __future__ import annotations

import csv
from pathlib import Path

from litestar import Litestar
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from el_descentralizador.db.models.source import Source, SourceKind
from el_descentralizador.db.models.user import User
from el_descentralizador.lib.constants import MUNICIPALITY_PREFIX
from el_descentralizador.lib.settings import get_settings


def _kind_from_name(name: str) -> SourceKind:
    if name.startswith(MUNICIPALITY_PREFIX):
        return SourceKind.MUNICIPALITY
    return SourceKind.MEDIA


def load_catalog_rows(csv_path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with csv_path.open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("nombre") or "").strip()
            if not name:
                continue
            has_rss = row.get("tiene_rss", "") == "True"
            feed_url = (row.get("feed_url") or "").strip() if has_rss else None
            rows.append(
                {
                    "name": name,
                    "region": (row.get("region") or "").strip(),
                    "url": (row.get("url") or "").strip(),
                    "feed_url": feed_url or None,
                    "kind": _kind_from_name(name),
                    "has_rss": has_rss,
                    "site_live": row.get("sitio_vivo", "") == "True",
                    "is_active": True,
                }
            )
    return rows


async def seed_if_needed(app: Litestar) -> None:
    settings = get_settings()
    from el_descentralizador.server.plugins import alchemy_config

    config = alchemy_config()
    key = config.session_maker_app_state_key
    session_maker = getattr(app.state, key, None)
    if session_maker is None:
        session_maker = config.create_session_maker()
    async with session_maker() as session:
        await _seed_admin(session)
        await _seed_sources(session, settings.catalog_csv)
        await session.commit()


async def _seed_admin(session: AsyncSession) -> None:
    settings = get_settings()
    existing = await session.scalar(select(User).where(User.username == settings.admin.username))
    if existing is not None:
        return
    session.add(
        User(
            username=settings.admin.username,
            password=settings.admin.password,
            is_active=True,
        )
    )


async def _seed_sources(session: AsyncSession, csv_path: Path) -> None:
    count = await session.scalar(select(func.count()).select_from(Source))
    if count:
        return
    if not csv_path.exists():
        fallback = Path("medios_rss_actualizado.csv")
        if not fallback.exists():
            return
        csv_path = fallback
    for row in load_catalog_rows(csv_path):
        session.add(Source(**row))
