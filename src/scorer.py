# src/scorer.py

ESCALATION_KEYWORDS = [
    "attack", "strike", "missile", "drone", "offensive", "escalation",
    "incursion", "deployment", "mobilization", "conflict"
]

MODERNIZATION_KEYWORDS = [
    "modernization", "upgrade", "procurement", "acquisition",
    "contract", "capability", "defense spending", "rearmament"
]

ALLIANCE_KEYWORDS = [
    "nato", "joint exercise", "coalition", "alliance", "partner",
    "security cooperation"
]

TECH_KEYWORDS = [
    "ai", "hypersonic", "cyber", "autonomy", "counter-uas",
    "satellite", "electronic warfare"
]


def count_matches(text, keywords):
    text = text.lower()
    return sum(1 for keyword in keywords if keyword in text)


def score_article(article):
    """
    Assign a simple rules-based risk score and confidence value.
    """

    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()

    escalation_hits = count_matches(text, ESCALATION_KEYWORDS)
    modernization_hits = count_matches(text, MODERNIZATION_KEYWORDS)
    alliance_hits = count_matches(text, ALLIANCE_KEYWORDS)
    tech_hits = count_matches(text, TECH_KEYWORDS)

    raw_score = (
        escalation_hits * 20 +
        modernization_hits * 12 +
        alliance_hits * 10 +
        tech_hits * 8
    )

    risk_score = min(raw_score, 100)

    # Confidence rises with the number of matched signals, capped at 0.95
    total_hits = escalation_hits + modernization_hits + alliance_hits + tech_hits
    confidence = min(0.35 + (total_hits * 0.1), 0.95)

    return {
        "risk_score": risk_score,
        "confidence": round(confidence, 2),
        "signal_breakdown": {
            "escalation_hits": escalation_hits,
            "modernization_hits": modernization_hits,
            "alliance_hits": alliance_hits,
            "tech_hits": tech_hits
        }
    }
