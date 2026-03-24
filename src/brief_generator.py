import json
from datetime import datetime
from src.risk_engine import aggregate_risk


def risk_label(score):
    if score >= 80:
        return "CRITICAL"
    elif score >= 60:
        return "HIGH"
    elif score >= 40:
        return "MODERATE"
    else:
        return "LOW"


def strategic_implication(record):
    domain = (record.get("domain") or "").lower()
    command = record.get("combatant_command", "UNKNOWN")
    region = record.get("region", "the region")
    risk_type = record.get("risk_type", "security developments")

    if domain == "counter-uas":
        return (
            f"{command} activity suggests continued demand for layered air defense "
            f"and counter-UAS modernization across {region}."
        )
    elif domain == "cyber":
        return (
            f"{command} cyber activity may indicate growing pressure on critical "
            f"infrastructure and increased demand for defensive cyber capabilities "
            f"in {region}."
        )
    elif domain == "maritime":
        return (
            f"{command} maritime signaling suggests sustained naval competition "
            f"and elevated regional monitoring requirements in {region}."
        )
    elif domain == "air defense":
        return (
            f"{command} reporting indicates continued emphasis on integrated air "
            f"and missile defense posture in {region}."
        )
    elif domain == "isr":
        return (
            f"{command} developments suggest growing demand for ISR, sensing, "
            f"and decision-support capabilities in {region}."
        )
    else:
        return (
            f"{command} reporting reflects broader {risk_type.lower()} trends "
            f"that may shape regional defense priorities in {region}."
        )


def build_brief(records):
    command_summary = aggregate_risk(records)
    sorted_records = sorted(
        records,
        key=lambda x: x.get("risk_score", 0),
        reverse=True
    )
    top_records = sorted_records[:5]

    brief = []

    brief.append("STRATEGICWATCH AI")
    brief.append("Global Risk Brief")
    brief.append(f"Date: {datetime.utcnow().strftime('%B %d, %Y')}")
    brief.append("")

    brief.append("COMMAND RISK SUMMARY")
    brief.append("--------------------")

    for item in command_summary:
        brief.append(
            f"{item['command']}: {item['risk_level']} "
            f"(avg risk {item['average_risk']}, signals {item['signals']})"
        )

    brief.append("")
    brief.append("TOP STRATEGIC SIGNALS")
    brief.append("---------------------")

    for i, r in enumerate(top_records, start=1):
        title = r.get("title", "Unknown Event")
        command = r.get("combatant_command", "UNKNOWN")
        domain = r.get("domain", "Unknown")
        risk_type = r.get("risk_type", "Unknown")
        score = r.get("risk_score", 0)

        brief.append(f"{i}. {title}")
        brief.append(f"   Command: {command}")
        brief.append(f"   Domain: {domain}")
        brief.append(f"   Risk Type: {risk_type}")
        brief.append(f"   Risk Score: {score} ({risk_label(score)})")
        brief.append("")

    brief.append("STRATEGIC IMPLICATIONS")
    brief.append("----------------------")

    for i, r in enumerate(top_records, start=1):
        brief.append(f"{i}. {strategic_implication(r)}")

    brief.append("")
    brief.append("ASSESSMENT")
    brief.append("----------")
    brief.append(
        "This brief summarizes the highest-priority geopolitical and defense-related "
        "signals identified from current reporting. These outputs help monitor "
        "regional escalation, modernization trends, and emerging strategic demand signals."
    )

    return "\n".join(brief) + "\n"


def main():
    with open("outputs/strategic_risk_signals.json", "r", encoding="utf-8") as f:
        records = json.load(f)

    brief = build_brief(records)

    with open("outputs/strategic_risk_brief.txt", "w", encoding="utf-8") as f:
        f.write(brief)

    print("Strategic brief generated successfully.")
    print("Output: outputs/strategic_risk_brief.txt")


if __name__ == "__main__":
    main()
