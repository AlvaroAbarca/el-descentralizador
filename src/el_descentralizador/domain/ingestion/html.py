from __future__ import annotations

import re

from bs4 import BeautifulSoup

MAX_SUMMARY = 700
EMPTY_SUMMARY_THRESHOLD = 80

JUNK_PATTERN = re.compile(
    r"(^|[-_ ])(ad|ads|advert|publicidad|banner|sponsor|promo|sharedaddy|"
    r"jp-relatedposts|related|widget|social|share|comment)([-_ ]|$)",
    re.I,
)


def clean_html(html: str | None) -> tuple[str, str | None]:
    """Return (plain text, first image URL) from feed HTML."""
    if not html:
        return "", None
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(
        ["script", "style", "iframe", "form", "ins", "noscript", "object", "embed", "button", "aside", "footer"]
    ):
        tag.decompose()
    for tag in soup.find_all(attrs={"class": JUNK_PATTERN}):
        tag.decompose()
    for tag in soup.find_all(attrs={"id": JUNK_PATTERN}):
        tag.decompose()

    image: str | None = None
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src.startswith("http"):
            continue
        width = img.get("width")
        if width and str(width).isdigit() and int(width) < 80:
            continue
        if any(part in src.lower() for part in ["emoji", "gravatar", "avatar", "pixel", "1x1", "blank.", "spacer"]):
            continue
        image = src
        break

    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(
        r"(La entrada|The post|El artículo)\s.{0,120}?(se publicó primero|aparece primero|appeared first)\s.+$",
        "",
        text,
        flags=re.I,
    ).strip()
    if len(text) > MAX_SUMMARY:
        cut = text.rfind(" ", 0, MAX_SUMMARY)
        text = text[: cut if cut > 0 else MAX_SUMMARY] + "…"
    return text, image
