from collections import defaultdict

def aggregate_risk(records):
    region_scores = defaultdict(list)

    for r in records:
        region = r.get("combatant_command") or "UNKNOWN"
        region_scores[region].append(r["risk_score"])

    summary = []

    for region, scores in region_scores.items():
        avg = sum(scores) / len(scores)

        if avg >= 70:
            level = "HIGH"
        elif avg >= 40:
            level = "MEDIUM"
        else:
            level = "LOW"

        summary.append({
            "command": region,
            "average_risk": round(avg, 1),
            "risk_level": level,
            "signals": len(scores)
        })

    return summary
