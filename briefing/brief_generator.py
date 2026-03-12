import json
import os
from datetime import datetime
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


def _safe_json_loads(text: str) -> Dict[str, Any]:
    """Safely parse model output as JSON."""
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model did not return valid JSON. Raw output: {text}") from exc


def _format_analysis_items(analyses: List[Dict[str, Any]], max_items: int = 12) -> str:
    """Convert article analyses into a compact text block for the LLM."""
    selected = analyses[:max_items]
    lines: List[str] = []

    for idx, item in enumerate(selected, start=1):
        lines.append(
            f"""
Item {idx}
Topic: {item.get("topic", "Unknown")}
Headline: {item.get("headline", "Untitled")}
Source: {item.get("source", "Unknown")}
Published: {item.get("published_at", "Unknown")}
Event Type: {item.get("event_type", "Unknown")}
Risk Level: {item.get("risk_level", "Unknown")}
Escalation Signal: {item.get("escalation_signal", False)}
Key Actors: {", ".join(item.get("key_actors", [])) if isinstance(item.get("key_actors"), list) else item.get("key_actors", "")}
Countries/Regions: {", ".join(item.get("country_or_region", [])) if isinstance(item.get("country_or_region"), list) else item.get("country_or_region", "")}
Summary: {item.get("summary", "")}
Why It Matters: {item.get("why_it_matters", "")}
""".strip()
        )

    return "\n\n".join(lines)


def build_brief_prompt(analyses: List[Dict[str, Any]]) -> str:
    """Build the prompt for generating a structured executive brief."""
    analysis_block = _format_analysis_items(analyses)

    return (
        f"""
You are a senior geopolitical intelligence analyst preparing an executive brief.

Using the analyzed reporting below, produce a JSON object only.

Required JSON schema:
{{
  "brief_date": "YYYY-MM-DD",
  "title": "string",
  "executive_summary": "4-6 sentence overview",
  "top_developments": [
    {{
      "headline": "string",
      "topic": "string",
      "risk_level": "Low | Medium | High",
      "why_it_matters": "1-2 short sentences (keep it compact)"
    }}
  ],
  "regional_updates": [
    {{
      "region": "string",
      "assessment": "2-4 sentence update",
      "risk_level": "Low | Medium | High"
    }}
  ],
  "escalation_watch": [
    "short bullet string",
    "short bullet string"
  ],
  "strategic_outlook": "1 concise paragraph",
  "analyst_note": "1 concise paragraph",
  "analytic_confidence": "High | Moderate | Low (overall confidence in this brief)"
}}

Guidance:
- Prioritize combat actions, daily strikes, terrorism, cyber attacks, electronic warfare (EW),
  regime change, coups, and government changes. Lead with these in the executive summary and
  top_developments. De-emphasize purely economic or market-angle coverage unless it ties directly
  to security or conflict.
- Focus on the most strategically meaningful developments, not just the most dramatic headlines.
- Prefer concise, executive-ready language. Keep the tone analytical, measured, and professional.
- Keep each top_developments.why_it_matters to at most two short sentences.
- Write escalation_watch bullets as one short sentence each.
- Use IC-style analytic confidence: High, Moderate, or Low, based on evidence quality and source consistency.
- If there is insufficient evidence for a strong conclusion, say so.
- Include no markdown, no commentary, and no text outside the JSON object.

Analyzed reporting:
{analysis_block}
""".strip()
    )


def generate_executive_brief(
    analyses: List[Dict[str, Any]],
    model: str = "gpt-4.1-mini",
) -> Dict[str, Any]:
    """Generate a structured executive brief from analyzed articles."""
    if not analyses:
        raise ValueError("No analyses provided. Cannot generate brief.")

    client = get_openai_client()
    prompt = build_brief_prompt(analyses)

    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": "You produce structured executive geopolitical briefs in valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    raw_content = response.choices[0].message.content
    brief = _safe_json_loads(raw_content)

    if "brief_date" not in brief:
        brief["brief_date"] = datetime.utcnow().strftime("%Y-%m-%d")

    return brief


def _stub_brief_no_data() -> Dict[str, Any]:
    """Return a minimal brief when pipeline has no analyses (e.g. no articles, API failure)."""
    return {
        "brief_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "title": "No Intelligence Data Available",
        "headline": "No Intelligence Data Available",
        "executive_summary": (
            "The pipeline could not produce analyses—no articles were returned from feeds "
            "or analysis. Check NEWSAPI_KEY and OPENAI_API_KEY in .env, network connectivity, "
            "and that RSS feeds are reachable. Run the update again after fixing configuration."
        ),
        "regional_updates": [],
        "strategic_outlook": "",
        "analyst_note": "Insufficient data for assessment. Verify API keys and source connectivity.",
        "analytic_confidence": "Low",
        "overall_confidence": "Low",
    }


def _stub_brief_error(message: str) -> Dict[str, Any]:
    """Return a minimal brief with an error message for display in the dashboard."""
    return {
        "brief_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "title": "Pipeline Error",
        "headline": "Pipeline Error",
        "executive_summary": message,
        "regional_updates": [],
        "strategic_outlook": "",
        "analyst_note": "Fix the issue above and run the update again.",
        "analytic_confidence": "Low",
        "overall_confidence": "Low",
    }


def generate_brief(top5: List[Dict[str, Any]], trend: str) -> Dict[str, Any]:
    """
    Adapter used by the HTML dashboard pipeline.
    Uses the existing executive brief generator on the Top 5 items,
    then normalizes keys expected by the dashboard (date, overall_confidence).
    If top5 is empty or the OpenAI call fails, returns a stub brief instead of raising.
    """
    if not top5:
        return _stub_brief_no_data()
    try:
        brief = generate_executive_brief(top5)
    except Exception as e:
        return _stub_brief_error(
            f"Brief generation failed: {e}. Check OPENAI_API_KEY in .env and network."
        )
    brief.setdefault("brief_date", datetime.utcnow().strftime("%Y-%m-%d"))
    # Mirror keys expected by dashboard_app.py
    brief.setdefault("date", brief.get("brief_date"))
    brief.setdefault("overall_confidence", brief.get("analytic_confidence", "High"))
    return brief


def format_brief_as_markdown(brief: Dict[str, Any]) -> str:
    """Convert the structured brief JSON into a markdown report for Streamlit or export."""
    lines: List[str] = []

    lines.append(f"# {brief.get('title', 'Strategic Intelligence Brief')}")
    lines.append(
        f"**Date:** {brief.get('brief_date', datetime.utcnow().strftime('%Y-%m-%d'))}"
    )
    lines.append("")

    lines.append("## Executive Summary")
    lines.append(brief.get("executive_summary", "No executive summary available."))
    lines.append("")

    top_developments = brief.get("top_developments", [])
    if top_developments:
        lines.append("## Top Developments")
        for item in top_developments:
            lines.append(
                f"- **{item.get('headline', 'Untitled')}** "
                f"({item.get('topic', 'Unknown')} | {item.get('risk_level', 'Unknown')} Risk): "
                f"{item.get('why_it_matters', '')}"
            )
        lines.append("")

    regional_updates = brief.get("regional_updates", [])
    if regional_updates:
        lines.append("## Regional Updates")
        for item in regional_updates:
            lines.append(
                f"### {item.get('region', 'Unknown Region')} "
                f"({item.get('risk_level', 'Unknown')} Risk)"
            )
            lines.append(item.get("assessment", "No assessment available."))
            lines.append("")

    escalation_watch = brief.get("escalation_watch", [])
    if escalation_watch:
        lines.append("## Escalation Watch")
        for item in escalation_watch:
            lines.append(f"- {item}")
        lines.append("")

    lines.append("## Strategic Outlook")
    lines.append(brief.get("strategic_outlook", "No outlook available."))
    lines.append("")

    lines.append("## Analyst Note")
    lines.append(brief.get("analyst_note", "No analyst note available."))

    analytic_confidence = brief.get("analytic_confidence")
    if analytic_confidence:
        lines.append("")
        lines.append("### Analytic Confidence")
        lines.append(f"Overall confidence: **{analytic_confidence}**")

    return "\n".join(lines)


def save_brief_markdown(brief: Dict[str, Any], output_path: str = "daily_brief.md") -> str:
    """Save the markdown brief to disk."""
    markdown = format_brief_as_markdown(brief)
    with open(output_path, "w", encoding="utf-8") as file:
        file.write(markdown)
    return output_path


if __name__ == "__main__":
    # Example usage with mock analyses
    sample_analyses = [
        {
            "headline": "Russian drone strikes intensify near Kharkiv",
            "topic": "Russia-Ukraine",
            "country_or_region": ["Russia", "Ukraine", "Kharkiv"],
            "key_actors": ["Russian Armed Forces", "Ukrainian Armed Forces"],
            "event_type": "Drone Strike",
            "risk_level": "High",
            "summary": "Russian forces launched a renewed series of drone attacks targeting infrastructure near Kharkiv.",
            "why_it_matters": "The activity suggests sustained pressure on Ukrainian logistics and may signal preparation for expanded operations.",
            "escalation_signal": True,
            "confidence": "High",
            "source": "Example News",
            "url": "https://example.com/russia-ukraine",
            "published_at": "2026-03-10T08:00:00Z",
        },
        {
            "headline": "Iran-linked militia activity raises alert levels in the region",
            "topic": "Iran-Israel",
            "country_or_region": ["Iran", "Israel", "Lebanon"],
            "key_actors": ["Iran", "Hezbollah", "Israel Defense Forces"],
            "event_type": "Proxy Activity",
            "risk_level": "High",
            "summary": "Regional reporting indicates increased militia coordination and heightened Israeli alert postures.",
            "why_it_matters": "The pattern may increase the risk of miscalculation and near-term retaliation.",
            "escalation_signal": True,
            "confidence": "Medium",
            "source": "Example News",
            "url": "https://example.com/iran-israel",
            "published_at": "2026-03-10T10:30:00Z",
        },
        {
            "headline": "China expands military patrols near Taiwan Strait",
            "topic": "China-Taiwan",
            "country_or_region": ["China", "Taiwan"],
            "key_actors": ["PLA", "Taiwan Ministry of National Defense"],
            "event_type": "Military Patrol",
            "risk_level": "Medium",
            "summary": "Chinese military activity increased around the Taiwan Strait, with additional patrols and public signaling.",
            "why_it_matters": "The activity reinforces coercive pressure and raises the operational tempo in a strategically sensitive area.",
            "escalation_signal": True,
            "confidence": "High",
            "source": "Example News",
            "url": "https://example.com/china-taiwan",
            "published_at": "2026-03-10T11:15:00Z",
        },
    ]

    brief_json = generate_executive_brief(sample_analyses)
    print(json.dumps(brief_json, indent=2))

    saved_path = save_brief_markdown(brief_json, "daily_brief.md")
    print(f"\nSaved markdown brief to: {saved_path}")

