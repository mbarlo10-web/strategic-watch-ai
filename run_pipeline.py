import json
import csv
from pathlib import Path

from src.tagger import tag_article
from src.scorer import score_article

# Temporary sample articles for local testing
SAMPLE_ARTICLES = [
    {
        "title": "NATO expands missile defense and drone countermeasures in Poland",
        "summary": "Alliance partners announced modernization and joint exercise plans to strengthen air defense posture.",
        "source": "Defense News",
        "published_date": "2026-03-16",
        "url": "https://example.com/nato-poland-air-defense"
    },
    {
        "title": "China increases naval patrols near Taiwan Strait",
        "summary": "Regional tensions rise as maritime and air activity intensifies near Taiwan.",
        "source": "Reuters",
        "published_date": "2026-03-16",
        "url": "https://example.com/taiwan-strait-patrols"
    },
    {
        "title": "Cyber attacks target critical infrastructure in the Middle East",
        "summary": "Security officials report increased malware campaigns affecting regional energy networks.",
        "source": "AP",
        "published_date": "2026-03-16",
        "url": "https://example.com/middle-east-cyber"
    }
]


def build_risk_signal(article):
    tags = tag_article(article)
    score = score_article(article)

    return {
        "title": article.get("title"),
        "summary": article.get("summary"),
        "source": article.get("source"),
        "published_date": article.get("published_date"),
        "url": article.get("url"),
        "region": tags.get("region"),
        "combatant_command": tags.get("combatant_command"),
        "domain": tags.get("domain"),
        "conflict_area": tags.get("conflict_area"),
        "risk_type": tags.get("risk_type"),
        "risk_score": score.get("risk_score"),
        "confidence": score.get("confidence"),
    }


def export_json(records, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)


def export_csv(records, filepath):
    if not records:
        return

    fieldnames = list(records[0].keys())
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def main():
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    risk_signals = [build_risk_signal(article) for article in SAMPLE_ARTICLES]

    export_json(risk_signals, output_dir / "strategic_risk_signals.json")
    export_csv(risk_signals, output_dir / "strategic_risk_signals.csv")

    print("Pipeline complete.")
    print(f"Exported {len(risk_signals)} records to outputs/")


if __name__ == "__main__":
    main()
