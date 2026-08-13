"""Full-article HTML extraction for the in-app reader."""

from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from el_descentralizador.domain.ingestion.html import JUNK_PATTERN
from el_descentralizador.domain.ingestion.http import USER_AGENT

TIMEOUT = 20.0
MIN_TEXT = 250
MAX_HTML = 300_000

NAV_PATTERN = re.compile(
    r"(^|[-_ ])(menu|nav|navbar|sidebar|breadcrumbs?|cookie|newsletter|"
    r"suscripcion|subscribe|author|autor|tags|pagination|paginacion|"
    r"copyright|entry-footer|post-meta|caja-poll|encuesta)([-_ ]|$)",
    re.I,
)
ALLOWED_TAGS = {
    "p",
    "h2",
    "h3",
    "h4",
    "blockquote",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "b",
    "i",
    "a",
    "img",
    "figure",
    "figcaption",
}
JUNK_IMG = ("emoji", "gravatar", "avatar", "pixel", "1x1", "blank.", "spacer", "logo", "icon")


def _score(el: Tag) -> int:
    return sum(len(p.get_text(strip=True)) for p in el.find_all("p"))


def _best_container(soup: BeautifulSoup) -> Tag | None:
    candidates = soup.find_all(["article", "main", "section", "div"])
    if not candidates:
        return soup.body or soup
    best = max(candidates, key=_score)
    if _score(best) < MIN_TEXT:
        return None
    while True:
        total = _score(best)
        child = next(
            (
                node
                for node in best.find_all(["article", "main", "section", "div"], recursive=False)
                if _score(node) >= 0.9 * total
            ),
            None,
        )
        if child is None:
            return best
        best = child


def _sanitize(node: Tag, base_url: str, skip_images: set[str]) -> None:
    seen = set(skip_images)
    for tag in list(node.find_all(True)):
        if tag.decomposed or tag.parent is None:
            continue
        if tag.name == "img":
            src = tag.get("src") or tag.get("data-src") or tag.get("data-lazy-src") or ""
            src = urljoin(base_url, src.strip())
            if not src.startswith("http") or src in seen or any(part in src.lower() for part in JUNK_IMG):
                tag.decompose()
                continue
            seen.add(src)
            alt = tag.get("alt", "")
            tag.attrs = {"src": src, "loading": "lazy"}
            if alt:
                tag.attrs["alt"] = alt
        elif tag.name == "a":
            href = urljoin(base_url, (tag.get("href") or "").strip())
            if href.startswith("http"):
                tag.attrs = {"href": href, "target": "_blank", "rel": "noopener"}
            else:
                tag.unwrap()
        elif tag.name in ALLOWED_TAGS:
            tag.attrs = {}
        else:
            tag.unwrap()
    for paragraph in node.find_all(["p", "figure", "li"]):
        if not paragraph.get_text(strip=True) and not paragraph.find("img"):
            paragraph.decompose()


def extract_article(url: str, image_cover: str | None = None) -> str:
    """Return sanitized article HTML, or empty string if extraction failed."""
    response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")
    for tag in soup(
        [
            "script",
            "style",
            "iframe",
            "form",
            "nav",
            "aside",
            "footer",
            "header",
            "noscript",
            "ins",
            "button",
            "svg",
            "object",
            "embed",
            "select",
            "input",
            "h1",
        ]
    ):
        tag.decompose()
    total = _score(soup)
    for pattern in (JUNK_PATTERN, NAV_PATTERN):
        for attr in ("class", "id"):
            for tag in soup.find_all(attrs={attr: pattern}):
                if tag.name in ("html", "body", "main", "article"):
                    continue
                if total and _score(tag) >= 0.5 * total:
                    continue
                tag.decompose()
    body = _best_container(soup)
    if body is None:
        return ""
    skip = {image_cover} if image_cover else set()
    _sanitize(body, str(response.url), skip)
    if len(body.get_text(strip=True)) < MIN_TEXT:
        return ""
    html = "".join(str(child) for child in body.children).strip()
    return html[:MAX_HTML]
