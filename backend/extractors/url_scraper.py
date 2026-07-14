"""
Scrapes article content from URLs.

Primary strategy: newspaper3k (handles article boilerplate removal, title,
authors, publish date well for most news/blog sites).

Fallback strategy: raw requests + BeautifulSoup, stripping script/style/nav
tags and pulling visible text. Used when newspaper3k fails to parse or
returns very little text (common on JS-heavy or unusual sites).
"""
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

try:
    from newspaper import Article
except Exception:  # pragma: no cover - optional dep may fail to import in some envs
    Article = None

from config import settings
from models.schemas import ExtractedContent

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 AINewsletterBot/1.0"
)

MIN_ACCEPTABLE_CHARS = 200


def _scrape_with_newspaper(url: str) -> Optional[ExtractedContent]:
    if Article is None:
        return None
    try:
        article = Article(url)
        article.download()
        article.parse()
        text = (article.text or "").strip()
        if len(text) < MIN_ACCEPTABLE_CHARS:
            return None
        return ExtractedContent(
            source=url,
            title=article.title or None,
            text=text,
        )
    except Exception as e:  # noqa: BLE001
        logger.info("newspaper3k failed for %s: %s", url, e)
        return None


def _scrape_with_bs4(url: str) -> ExtractedContent:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=settings.URL_FETCH_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return ExtractedContent(source=url, text="", error=f"Failed to fetch URL: {e}")

    try:
        soup = BeautifulSoup(resp.text, "lxml")

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "form", "aside"]):
            tag.decompose()

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else None

        # Prefer <article> content if present, else fall back to <body>
        container = soup.find("article") or soup.body or soup
        paragraphs = [p.get_text(" ", strip=True) for p in container.find_all(["p", "h1", "h2", "h3", "li"])]
        text = "\n".join(p for p in paragraphs if p)

        if len(text) < MIN_ACCEPTABLE_CHARS:
            return ExtractedContent(
                source=url,
                title=title,
                text=text,
                error="Extracted content is very short; page may require JavaScript "
                "or block scraping.",
            )

        return ExtractedContent(source=url, title=title, text=text)
    except Exception as e:  # noqa: BLE001
        return ExtractedContent(source=url, text="", error=f"Failed to parse page: {e}")


def scrape_url(url: str) -> ExtractedContent:
    """Scrape a single URL, trying newspaper3k first then falling back to BS4."""
    result = _scrape_with_newspaper(url)
    if result is not None:
        return result
    return _scrape_with_bs4(url)


def scrape_urls(urls: list[str]) -> list[ExtractedContent]:
    return [scrape_url(u) for u in urls]
