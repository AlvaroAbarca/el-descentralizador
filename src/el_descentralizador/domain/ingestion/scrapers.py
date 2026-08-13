"""HTML scrapers for outlets without a public RSS feed."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

TIMEOUT = 20.0
MAX_ENTRIES = 25
MERCURIO_DOMAINS = {
    "diariodeosorno.cl",
    "diariodepuertomontt.cl",
    "diariodevaldivia.cl",
    "diarioregionalaysen.cl",
    "elheraldoaustral.cl",
}
MONTHS_ES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def parse_spanish_date(text: str | None) -> datetime | None:
    if not text:
        return None
    match = re.search(
        r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})(?:\s*[|@\-,]\s*(\d{1,2}):(\d{2}))?",
        text.lower().strip(),
    )
    if not match:
        return None
    day, month_name, year, hour, minute = match.groups()
    month = MONTHS_ES.get(month_name)
    if not month:
        return None
    try:
        return datetime(
            int(year),
            month,
            int(day),
            int(hour) if hour else 12,
            int(minute) if minute else 0,
            tzinfo=UTC,
        )
    except ValueError:
        return None


def _date_from_url(url: str) -> datetime | None:
    match = re.search(r"/noticia/[^/]+/(\d{4})/(\d{1,2})/", url)
    if not match:
        return None
    try:
        return datetime(int(match.group(1)), int(match.group(2)), 15, 12, 0, tzinfo=UTC)
    except ValueError:
        return None


def _domain(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.lower().removeprefix("www.")


def has_scraper(site_url: str) -> bool:
    return _domain(site_url) in MERCURIO_DOMAINS


def scrape_mercurio(html: str, page_url: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    best: dict[str, object] = {}
    for anchor in soup.find_all("a", href=re.compile(r"/noticia/")):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        full = urljoin(page_url, href)
        text = anchor.get_text(" ", strip=True)
        previous = best.get(full)
        if previous is None or (text and not previous.get_text(strip=True)):
            best[full] = anchor

    entries: list[dict[str, str]] = []
    for full, anchor in best.items():
        container = (
            anchor.find_parent("article")
            or anchor.find_parent(["div", "li"], class_=re.compile(r"item|post|news|noticia|featured|destacad", re.I))
            or anchor.parent
            or anchor
        )
        title_el = (
            container.select_one(".news-title, .post-title, .item-title")
            or container.find(["h1", "h2", "h3"])
            or anchor
        )
        title = title_el.get_text(" ", strip=True)
        if not title or len(title) < 8:
            continue
        date_el = container.select_one(".nota-fecha, .post-date, .date, time")
        published = parse_spanish_date(date_el.get_text(" ", strip=True) if date_el else None)
        if published is None:
            published = _date_from_url(full)
        image = ""
        img_el = container.find("img") if hasattr(container, "find") else None
        if img_el:
            image = img_el.get("data-src") or img_el.get("src") or ""
            if image and not image.startswith("http"):
                image = urljoin(page_url, image)
            if "loadingCont" in image or "blank" in image.lower():
                image = ""
        entries.append(
            {
                "link": full,
                "title": title,
                "published": published.isoformat() if published else "",
                "summary": "",
                "image": image,
            }
        )
        if len(entries) >= MAX_ENTRIES:
            break
    return entries


async def scrape(site_url: str, client: httpx.AsyncClient) -> list[dict[str, str]] | None:
    if not has_scraper(site_url):
        return None
    try:
        response = await client.get(site_url, timeout=TIMEOUT)
        response.raise_for_status()
    except httpx.HTTPError:
        return []
    return scrape_mercurio(response.text, str(response.url))
