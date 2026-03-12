"""
Tier 1 RSS ingestion for curated defense signal.
Returns articles in the same shape as news_ingestion for pipeline merge.
"""

import random
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Tuple

import feedparser

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

# Add more feeds by appending ( "Display Name", "https://...rss..." ) tuples.
# Standard RSS/Atom feeds work; entries need <title>, <link>, and optionally <description>/<summary>, <pubDate>.
RSS_FEEDS: List[Tuple[str, str]] = [
    # Defense News (multiple categories)
    (
        "Defense News",
        "https://www.defensenews.com/arc/outboundfeeds/rss/?outputType=xml",
    ),
    (
        "Defense News (Pentagon)",
        "https://www.defensenews.com/arc/outboundfeeds/rss/category/pentagon/?outputType=xml",
    ),
    (
        "Defense News (Air)",
        "https://www.defensenews.com/arc/outboundfeeds/rss/category/air/?outputType=xml",
    ),
    (
        "Defense News (Land)",
        "https://www.defensenews.com/arc/outboundfeeds/rss/category/land/?outputType=xml",
    ),
    (
        "Defense News (Naval)",
        "https://www.defensenews.com/arc/outboundfeeds/rss/category/naval/?outputType=xml",
    ),
    (
        "Defense News (Space)",
        "https://www.defensenews.com/arc/outboundfeeds/rss/category/space/?outputType=xml",
    ),
    (
        "Department of War",
        "https://www.war.gov/DesktopModules/ArticleCS/RSS.ashx?max=10&ContentType=1&Site=945",
    ),
    # Broader geopolitical / world news (improves theater coverage when NewsAPI is limited)
    (
        "BBC World",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
    ),
    (
        "Foreign Policy",
        "https://foreignpolicy.com/feed/",
    ),
    (
        "Al Jazeera English",
        "https://www.aljazeera.com/xml/rss/all.xml",
    ),
]

TIER_1 = 1


# User-Agent so servers (e.g. war.gov) that block default clients allow the request
FEEDPARSER_HEADERS = {"User-Agent": "StrategicWatch/1.0 (RSS reader; https://github.com/strategic-watch)"}


def _fetch_feed_bytes(url: str) -> bytes:
    """Fetch feed XML; use requests if available (better SSL), else urllib."""
    if _HAS_REQUESTS:
        r = _requests.get(url, headers=FEEDPARSER_HEADERS, timeout=15)
        r.raise_for_status()
        return r.content
    from urllib.request import Request, urlopen
    req = Request(url, headers=FEEDPARSER_HEADERS)
    with urlopen(req, timeout=15) as resp:
        return resp.read()


def _parse_feed_fallback(url: str) -> List[Dict[str, Any]]:
    """When feedparser returns no entries, parse RSS/Atom with stdlib (SSL via requests if available)."""
    try:
        raw = _fetch_feed_bytes(url)
    except Exception:
        return []
    root = ET.fromstring(raw)
    out: List[Dict[str, Any]] = []
    # Atom: feed/entry, link@href, title, summary, updated
    ns_atom = "http://www.w3.org/2005/Atom"
    entries = root.findall(f".//{{{ns_atom}}}entry") or root.findall(".//entry")
    if entries:
        for item in entries:
            link_el = item.find(f"{{{ns_atom}}}link") or item.find("link")
            if link_el is not None and link_el.get("href"):
                link = link_el.get("href", "").strip()
            else:
                link = (item.find(f"{{{ns_atom}}}link") or item.find("link"))
                link = (link.text or "").strip() if link is not None else ""
            if not link:
                continue
            title_el = item.find(f"{{{ns_atom}}}title") or item.find("title")
            title = (title_el.text or "").strip() if title_el is not None else "Untitled"
            sum_el = item.find(f"{{{ns_atom}}}summary") or item.find("summary") or item.find("description")
            desc = (sum_el.text or "").strip() if sum_el is not None else ""
            pub_el = item.find(f"{{{ns_atom}}}updated") or item.find("pubDate") or item.find("updated")
            pub = (pub_el.text or "").strip() if pub_el is not None else ""
            out.append({"link": link, "title": title, "summary": desc, "published": pub})
        return out
    # RSS 2.0: channel/item
    channel = root.find("channel") or root.find("{http://purl.org/rss/1.0/}channel") or root.find(".//channel")
    if channel is None:
        return []
    items = channel.findall("item") or channel.findall("{http://purl.org/rss/1.0/}item") or []
    for item in items:
        def text(tag: str) -> str:
            el = item.find(tag) or item.find(f"{{*}}{tag}")
            return (el.text or "").strip() if el is not None else ""
        link = text("link")
        if not link:
            continue
        out.append({"link": link, "title": text("title") or "Untitled", "summary": text("description"), "published": text("pubDate")})
    return out


def fetch_defense_news() -> List[Dict[str, Any]]:
    """
    Fetch Defense News RSS feeds. Returns articles with same keys as news_ingestion
    (topic, source, source_tier, title, description, content, url, published_at) for pipeline merge.
    """
    articles: List[Dict[str, Any]] = []
    seen_urls: set = set()

    for source_name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url, request_headers=FEEDPARSER_HEADERS)
            count_before = len(articles)
            entries_to_use: List[Any] = list(feed.entries)
            # If feedparser returns no entries (e.g. war.gov namespace), use stdlib XML fallback
            if not entries_to_use:
                entries_to_use = _parse_feed_fallback(url)
            for entry in entries_to_use:
                if isinstance(entry, dict):
                    link = (entry.get("link") or "").strip()
                    raw_summary = entry.get("summary", "")
                    title = (entry.get("title") or "Untitled").strip()
                    pub = entry.get("published", "")
                else:
                    link = (getattr(entry, "link", None) or "").strip()
                    raw_summary = getattr(entry, "summary", None) or ""
                    title = (getattr(entry, "title", None) or "Untitled").strip()
                    pub = getattr(entry, "published", None) or ""
                if not link or link in seen_urls:
                    continue
                seen_urls.add(link)
                summary = str(raw_summary) if raw_summary else ""
                if summary:
                    summary = summary.replace("<p>", " ").replace("</p>", " ").replace("<br>", " ")
                articles.append({
                    "topic": "Defense",
                    "source": source_name,
                    "source_tier": TIER_1,
                    "author": None,
                    "title": title,
                    "description": summary[:500] if summary else "",
                    "content": summary[:2000] if summary else "",
                    "url": link,
                    "published_at": pub,
                })
            count_from_feed = len(articles) - count_before
            print(f"[RSS] {source_name}: {count_from_feed} articles")
        except Exception as exc:
            print(f"[WARN] Defense RSS feed failed {source_name} ({url}): {exc}")

    # Shuffle so the pipeline's first N articles aren't all from Defense News
    random.shuffle(articles)
    return articles


def fetch_defense_rss() -> List[Dict[str, Any]]:
    """
    Backwards-compatible alias for older code that expects fetch_defense_rss.
    Used by the HTML dashboard pipeline. Returns [] on any failure so pipeline can continue.
    """
    try:
        return fetch_defense_news()
    except Exception as exc:
        print(f"[WARN] Defense RSS fetch failed: {exc}")
        return []
