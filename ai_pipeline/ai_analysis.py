import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
from openai import OpenAI


# Load environment variables from .env (project root)
load_dotenv()

def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise EnvironmentError("OPENAI_API_KEY not found. Please set it in your .env file.")
    return OpenAI(api_key=api_key)


def build_article_prompt(article: Dict[str, Any]) -> str:
    """Create a structured prompt for geopolitical article analysis."""
    return (
        f"""
You are a geopolitical intelligence analyst focused on hard security and conflict.

Analyze the following article and return a JSON object only. Prioritize and label:
combat actions, strikes, terrorism, cyber attacks, electronic warfare (EW), regime change,
coups, government changes, military operations, and direct security threats. If the article
is mainly about markets, de-escalation rhetoric, or general commentary with no concrete
combat/security event, set event_type and summary to reflect that (e.g. "Market reaction"
or "Commentary") and keep risk_level appropriate.

Risk level criteria — apply the same rules to every conflict zone (Russia-Ukraine, Iran-Israel, China-Taiwan, North Korea, Venezuela, Cuba):
- High: Active combat, strikes, or kinetic attack; terrorism or major attack; imminent escalation or regime collapse; significant cyber/EW attack on critical systems; coup or violent government overthrow; direct threat to sovereignty or mass casualties.
- Medium: Significant military buildup or tension; sanctions or coercion with escalation risk; serious instability or protests with security impact; indirect threat or proxy activity; cyber/EW incident with limited impact.
- Low: Monitoring or routine activity; de-escalation or diplomatic outreach; commentary or analysis with no new event; economic/market impact only; no direct security or combat implication.

Required JSON schema:
{{
  "headline": "string",
  "topic": "string",
  "country_or_region": ["list", "of", "entities"],
  "key_actors": ["list", "of", "actors"],
  "event_type": "one short label (e.g. Strike, Terrorism, Cyber Attack, EW, Regime Change, Coup, Combat)",
  "risk_level": "Low | Medium | High",
  "summary": "2-4 sentence summary emphasizing any combat/security/terrorism/EW/regime action",
  "why_it_matters": "2-3 sentence executive explanation",
  "escalation_signal": true,
  "confidence": "Low | Medium | High"
}}

Article topic: {article.get("topic")}
Headline: {article.get("title")}
Source: {article.get("source")}
Published: {article.get("published_at")}
Description: {article.get("description")}
Content: {article.get("content")}
""".strip()
    )


def analyze_article(article: Dict[str, Any], model: str = "gpt-4.1-mini") -> Dict[str, Any]:
    """Send one article to OpenAI and return structured analysis."""
    client = get_openai_client()
    prompt = build_article_prompt(article)

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "You produce structured geopolitical intelligence analysis in valid JSON only. "
                    "Emphasize combat actions, strikes, terrorism, cyber/EW, regime change, and coups; "
                    "label event_type accordingly (e.g. Strike, Terrorism, Cyber Attack, EW, Coup)."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    )

    raw_content = response.choices[0].message.content
    parsed = json.loads(raw_content)

    # Add source metadata and normalized keys for dashboard display
    parsed["source"] = article.get("source")
    parsed["source_tier"] = article.get("source_tier", 3)
    parsed["url"] = article.get("url")
    parsed["published_at"] = article.get("published_at")
    parsed["title"] = parsed.get("headline") or article.get("title", "")
    parsed["theater"] = parsed.get("topic") or article.get("topic", "Defense")
    return parsed


def analyze_articles(
    articles: List[Dict[str, Any]],
    model: str = "gpt-4.1-mini",
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Analyze multiple articles with OpenAI."""
    results: List[Dict[str, Any]] = []

    for article in articles[:limit]:
        try:
            analysis = analyze_article(article, model=model)
            results.append(analysis)
        except Exception as exc:
            print(f"[WARN] Failed to analyze article '{article.get('title')}': {exc}")

    return results


if __name__ == "__main__":
    sample_article = {
        "topic": "Russia-Ukraine",
        "title": "Russia launches drone strikes on key Ukrainian infrastructure",
        "source": "Example News",
        "published_at": "2026-03-10T12:00:00Z",
        "description": "A wave of overnight drone attacks targeted multiple infrastructure nodes.",
        "content": "Officials reported multiple strikes and increased regional military activity...",
        "url": "https://example.com/article",
    }

    result = analyze_article(sample_article)
    print(json.dumps(result, indent=2))

