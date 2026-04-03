"""
Security relevance filter: keep only articles that contain defense/conflict signals.
Discards items like "Letters: Care of hedgerows" that slip through broad NewsAPI queries.

Also provides balance_sources() so one RSS brand (e.g. Defense News across many feeds)
does not consume the entire analysis budget before other outlets are considered.
"""

from collections import defaultdict, deque
from typing import Any, Dict, List

# Articles must contain at least one of these (case-insensitive) in title + description + content.
SECURITY_KEYWORDS = [
    "military", "strike", "missile", "troops", "sanctions", "navy", "air force",
    "war", "defense", "cyber attack", "nuclear", "combat", "invasion", "drone",
    "attack", "terrorism", "nato", "armed", "weapon", "escalation", "conflict",
    "pentagon", "platoon", "battalion", "artillery", "blockade", "regime",
    "coup", "sovereignty", "intelligence", "surveillance", "exercises", "deployment",
]


def filter_by_security_relevance(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Return only articles whose title, description, or content contains at least one
    security/defense keyword. Reduces noise (e.g. lifestyle or unrelated news).
    """
    if not articles:
        return []
    keywords_lower = [k.lower() for k in SECURITY_KEYWORDS]
    kept: List[Dict[str, Any]] = []
    for a in articles:
        text = " ".join(
            str(x) for x in [
                a.get("title") or "",
                a.get("description") or "",
                (a.get("content") or "")[:3000],
            ]
            if x
        ).lower()
        if any(kw in text for kw in keywords_lower):
            kept.append(a)
    return kept


# Backwards-compatible alias for dashboard_app.py
def filter_relevant(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return filter_by_security_relevance(articles)


def _normalize_source_label(name: str) -> str:
    """Group Defense News category feeds under one label for fair round-robin."""
    n = (name or "").strip() or "Unknown"
    low = n.lower()
    if low.startswith("defense news"):
        return "Defense News"
    return n


def balance_sources(articles: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    """
    Pick up to ``limit`` articles by round-robin across distinct sources so the batch
    mixes outlets instead of taking the first N in list order (which favored RSS-first).
    Preserves order within each source bucket (e.g. NewsAPI recency / feed order).
    """
    if not articles or limit <= 0:
        return []
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for a in articles:
        key = _normalize_source_label(str(a.get("source") or ""))
        buckets[key].append(a)
    keys = sorted(buckets.keys())
    q: deque[str] = deque(keys)
    out: List[Dict[str, Any]] = []
    while len(out) < limit and q:
        k = q.popleft()
        if not buckets.get(k):
            continue
        out.append(buckets[k].pop(0))
        if buckets[k]:
            q.append(k)
    return out
