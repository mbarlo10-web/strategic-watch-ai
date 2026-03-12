"""
Security relevance filter: keep only articles that contain defense/conflict signals.
Discards items like "Letters: Care of hedgerows" that slip through broad NewsAPI queries.
"""

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
