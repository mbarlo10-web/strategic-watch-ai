"""
Geopolitical risk scoring model for ranking developments.
Score = weighted combination of escalation, military/risk level, and recency.
Used to select Top 5 global risks (decision-support, not just summarization).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Weights (sum to 1.0): escalation signals, military/risk level, geopolitical impact, recency
W_ESCALATION = 0.35
W_RISK_LEVEL = 0.25
W_GEOPOLITICAL = 0.20  # approximated from risk_level + event_type
W_RECENCY = 0.20

RISK_LEVEL_SCORE = {"High": 1.0, "Medium": 0.5, "Low": 0.2}
RECENCY_DAYS_CAP = 7  # articles older than this get 0 recency score


def _parse_published(published_at: Any) -> Optional[datetime]:
    """Return naive UTC datetime if parseable, else None."""
    if not published_at:
        return None
    s = str(published_at).strip()
    if not s:
        return None
    try:
        from dateutil import parser as date_parser  # type: ignore
        dt = date_parser.parse(s)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return None


def score_article(analysis: Dict[str, Any]) -> float:
    """
    Compute a single risk score in [0, 1] for ranking.
    Higher = more important for Top 5 strategic risks.
    """
    esc = 1.0 if analysis.get("escalation_signal") else 0.0
    risk_level = (analysis.get("risk_level") or "").strip()
    risk_num = RISK_LEVEL_SCORE.get(risk_level, 0.0)
    # Geopolitical impact: use same risk level as proxy (could add event_type later)
    geo = risk_num
    # Recency: newer = higher score
    rec = 0.0
    pub = _parse_published(analysis.get("published_at"))
    if pub:
        age_days = (datetime.utcnow() - pub).total_seconds() / 86400
        if age_days <= 0:
            rec = 1.0
        elif age_days < RECENCY_DAYS_CAP:
            rec = 1.0 - (age_days / RECENCY_DAYS_CAP)
    return (
        W_ESCALATION * esc
        + W_RISK_LEVEL * risk_num
        + W_GEOPOLITICAL * geo
        + W_RECENCY * rec
    )


def rank_and_select_top(
    analyses: List[Dict[str, Any]],
    top_n: int = 5,
) -> List[Dict[str, Any]]:
    """Sort by risk score descending and return top_n. Adds 'risk_score' to each item."""
    scored = []
    for a in analyses:
        s = score_article(a)
        scored.append({**a, "risk_score": round(s, 4)})
    scored.sort(key=lambda x: x["risk_score"], reverse=True)
    return scored[:top_n]


def score_and_rank(
    analyses: List[Dict[str, Any]],
) -> tuple[list[Dict[str, Any]], str, list[Dict[str, Any]]]:
    """
    Adapter used by the HTML dashboard pipeline.
    Returns (top5, trend_label, escalation_items).
    """
    if not analyses:
        return [], "Stable", []

    top5 = rank_and_select_top(analyses, top_n=5)

    high_count = sum(1 for a in analyses if (a.get("risk_level") or "").strip() == "High")
    esc_items = [a for a in analyses if a.get("escalation_signal")]

    if len(esc_items) >= 2 or high_count >= 2:
        trend = "Escalating"
    elif high_count == 0 and not esc_items:
        trend = "De-escalating"
    else:
        trend = "Stable"

    # Ensure escalation items carry a short escalation_note field for the dashboard.
    out_esc: list[Dict[str, Any]] = []
    for a in esc_items:
        note = a.get("why_it_matters") or a.get("summary") or a.get("headline")
        out_esc.append({**a, "escalation_note": note})

    return top5, trend, out_esc
