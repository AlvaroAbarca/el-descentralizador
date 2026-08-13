from __future__ import annotations

import asyncio
import difflib
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import feedparser
import httpx
from dateutil import parser as dateparser
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from el_descentralizador.db.models.article import Article
from el_descentralizador.db.models.source import Source
from el_descentralizador.domain.ingestion.html import EMPTY_SUMMARY_THRESHOLD, clean_html
from el_descentralizador.domain.ingestion.http import DEFAULT_TIMEOUT, USER_AGENT
from el_descentralizador.domain.ingestion.reader import extract_article
from el_descentralizador.domain.ingestion.scrapers import has_scraper, scrape

STOPWORDS = set(
    """a al ante como con contra de del desde donde el en entre es
fue ha hay la las lo los mas más para per pero por que se será sin sobre son
su sus tras un una uno y ya o u e este esta estos estas ese esa""".split()
)
DUP_WINDOW_DAYS = 3
JACCARD_THRESHOLD = 0.65
RATIO_THRESHOLD = 0.85
WORKERS = 12


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFD", title.lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    words = [word for word in text.split() if word not in STOPWORDS]
    return " ".join(words)


def are_similar(left: str, right: str) -> bool:
    set_a, set_b = set(left.split()), set(right.split())
    if not set_a or not set_b:
        return False
    jaccard = len(set_a & set_b) / len(set_a | set_b)
    if jaccard >= JACCARD_THRESHOLD:
        return True
    if jaccard < 0.3:
        return False
    return difflib.SequenceMatcher(None, left, right).ratio() >= RATIO_THRESHOLD


def extract_image(entry: Any, content_image: str | None) -> str | None:
    for media in entry.get("media_content", []) or []:
        url = media.get("url", "")
        if url.startswith("http") and media.get("medium", "image") in ("image", ""):
            return url
    for media in entry.get("media_thumbnail", []) or []:
        if media.get("url", "").startswith("http"):
            return media["url"]
    for enclosure in entry.get("enclosures", []) or []:
        if enclosure.get("type", "").startswith("image") and enclosure.get("href", "").startswith("http"):
            return enclosure["href"]
    return content_image


def extract_date(entry: Any) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            return datetime(*parsed[:6], tzinfo=UTC)
    for field in ("published", "updated"):
        if entry.get(field):
            try:
                value = dateparser.parse(entry[field])
                if value.tzinfo is None:
                    value = value.replace(tzinfo=UTC)
                return value.astimezone(UTC)
            except (ValueError, OverflowError):
                pass
    return None


def _rescue_summary(url: str, image: str | None) -> str:
    try:
        html = extract_article(url, image_cover=image)
        if not html:
            return ""
        from bs4 import BeautifulSoup

        text = re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text(" ", strip=True)).strip()
        if len(text) > 700:
            cut = text.rfind(" ", 0, 700)
            text = text[: cut if cut > 0 else 700] + "…"
        return text
    except Exception:
        return ""


async def _og_image(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        async with client.stream("GET", url, timeout=10.0) as response:
            response.raise_for_status()
            chunk = b""
            async for part in response.aiter_bytes():
                chunk += part
                if len(chunk) >= 120_000:
                    break
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(chunk, "html.parser")
        for selector in ({"property": "og:image"}, {"name": "twitter:image"}):
            meta = soup.find("meta", attrs=selector)
            if meta and str(meta.get("content", "")).startswith("http"):
                return str(meta["content"])
    except Exception:
        return None
    return None


async def _process_source(
    source: Source,
    client: httpx.AsyncClient,
) -> tuple[str, list[dict[str, Any]], str]:
    if not source.feed_url:
        entries = await scrape(source.url, client)
        if entries is None:
            return source.name, [], "error scraper: no scraper"
        now = datetime.now(UTC).isoformat()
        articles: list[dict[str, Any]] = []
        for entry in entries:
            url = (entry.get("link") or "").strip()
            title = re.sub(r"\s+", " ", entry.get("title") or "").strip()
            if not url or not title:
                continue
            summary, image_html = clean_html(entry.get("summary") or "")
            articles.append(
                {
                    "title": title,
                    "url": url,
                    "published_at": entry.get("published") or now,
                    "summary": summary,
                    "image_url": entry.get("image") or image_html,
                }
            )
        return source.name, articles, "ok"

    try:
        response = await client.get(source.feed_url, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as exc:
        return source.name, [], f"error: {type(exc).__name__}"

    articles = []
    for entry in feed.entries:
        url = (entry.get("link") or "").strip()
        title = re.sub(r"\s+", " ", entry.get("title") or "").strip()
        if not url or not title:
            continue
        html = ""
        if entry.get("content"):
            html = entry.content[0].get("value", "")
        if not html:
            html = entry.get("summary", "")
        summary, image_html = clean_html(html)
        image = extract_image(entry, image_html)
        if len(summary) < EMPTY_SUMMARY_THRESHOLD:
            rescued = await asyncio.to_thread(_rescue_summary, url, image)
            if rescued:
                summary = rescued
        published = extract_date(entry)
        articles.append(
            {
                "title": title,
                "url": url,
                "published_at": published,
                "summary": summary,
                "image_url": image,
            }
        )
    return source.name, articles, "ok"


async def _insert_articles(
    session: AsyncSession,
    source: Source,
    articles: list[dict[str, Any]],
) -> int:
    inserted = 0
    for article in articles:
        published = article["published_at"]
        if isinstance(published, str) and published:
            try:
                published = datetime.fromisoformat(published)
                if published.tzinfo is None:
                    published = published.replace(tzinfo=UTC)
            except ValueError:
                published = None
        stmt = (
            insert(Article)
            .values(
                source_id=source.id,
                title=article["title"],
                url=article["url"],
                published_at=published,
                summary=article["summary"],
                image_url=article["image_url"],
                title_norm=normalize_title(article["title"]),
                region=source.region,
            )
            .on_conflict_do_nothing(index_elements=[Article.url])
        )
        result = await session.execute(stmt)
        inserted += result.rowcount or 0
    await session.commit()
    return inserted


async def _rescue_images(session_maker: async_sessionmaker[AsyncSession], client: httpx.AsyncClient) -> int:
    async with session_maker() as session:
        pending = list(
            (await session.execute(select(Article.id, Article.url).where(Article.image_url.is_(None)))).all()
        )
    rescued = 0
    semaphore = asyncio.Semaphore(WORKERS)

    async def one(article_id: UUID, url: str) -> None:
        nonlocal rescued
        async with semaphore:
            image = await _og_image(client, url)
        if not image:
            return
        async with session_maker() as session:
            await session.execute(update(Article).where(Article.id == article_id).values(image_url=image))
            await session.commit()
            rescued += 1

    await asyncio.gather(*(one(row.id, row.url) for row in pending))
    return rescued


async def _dedupe(session: AsyncSession) -> int:
    new_rows = list(
        (
            await session.execute(
                select(Article).where(Article.group_id.is_(None)).order_by(Article.published_at.nulls_last())
            )
        )
        .scalars()
        .all()
    )
    duplicates = 0
    for article in new_rows:
        group_id = article.id
        if article.published_at and article.title_norm:
            window_start = article.published_at - timedelta(days=DUP_WINDOW_DAYS)
            window_end = article.published_at + timedelta(days=DUP_WINDOW_DAYS)
            candidates = list(
                (
                    await session.execute(
                        select(Article).where(
                            Article.group_id.is_not(None),
                            Article.source_id != article.source_id,
                            Article.published_at.between(window_start, window_end),
                        )
                    )
                )
                .scalars()
                .all()
            )
            for candidate in candidates:
                if candidate.title_norm and are_similar(article.title_norm, candidate.title_norm):
                    group_id = candidate.group_id or candidate.id
                    duplicates += 1
                    break
        article.group_id = group_id
    await session.commit()
    return duplicates


async def run_pipeline(
    session_maker: async_sessionmaker[AsyncSession],
    progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    async with session_maker() as session:
        sources = list(
            (
                await session.execute(
                    select(Source).where(
                        Source.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        ingestible = [
            src for src in sources if (src.has_rss and src.feed_url) or has_scraper(src.url)
        ]

    if progress is not None:
        progress.update(phase="feeds", done=0, total=len(ingestible))

    total_new = 0
    failed: list[str] = []
    semaphore = asyncio.Semaphore(WORKERS)
    source_by_name = {src.name: src for src in ingestible}

    async with httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    ) as client:

        async def process(source: Source) -> tuple[str, list[dict[str, Any]], str]:
            async with semaphore:
                return await _process_source(source, client)

        results = await asyncio.gather(*(process(src) for src in ingestible), return_exceptions=True)
        for index, result in enumerate(results, start=1):
            if isinstance(result, BaseException):
                failed.append(ingestible[index - 1].name)
                continue
            name, articles, status = result
            source = source_by_name[name]
            async with session_maker() as session:
                total_new += await _insert_articles(session, source, articles)
            if status != "ok":
                failed.append(name)
            if progress is not None:
                progress["done"] = index

        if progress is not None:
            progress.update(phase="images", done=0, total=0)
        await _rescue_images(session_maker, client)

    if progress is not None:
        progress.update(phase="dedup", done=0, total=0)
    from sqlalchemy import func

    async with session_maker() as session:
        duplicates = await _dedupe(session)
        total = int(await session.scalar(select(func.count()).select_from(Article)) or 0)
        groups = int(await session.scalar(select(func.count(func.distinct(Article.group_id)))) or 0)

    return {
        "created": total_new,
        "duplicates": duplicates,
        "total": total,
        "groups": groups,
        "failed": failed,
    }
