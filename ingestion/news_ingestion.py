import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv


# Load environment variables from .env (project root)
load_dotenv()

NEWS_API_URL = "https://newsapi.org/v2/everything"

# Theater-centered queries: country/region AND conflict-relevant terms to reduce peripheral hits.
HOTSPOT_QUERIES = {
    "Russia-Ukraine": (
        '(Russia OR Ukraine OR Donbas OR Crimea) AND '
        '(war OR invasion OR offensive OR missile OR drone OR strike OR frontline OR sanctions '
        'OR NATO OR military OR mobilization OR ceasefire OR shelling OR Zelenskyy OR Putin) '
        '-sports -football -soccer -tennis -hockey'
    ),
    # Iran-Israel: combat, strikes, terrorism, cyber/EW, regime change. Query kept matchable.
    "Iran-Israel": (
        '(Iran OR Israel OR Hezbollah OR Gaza OR "IRGC" OR "IDF" OR Houthi) AND '
        '(strike OR attack OR combat OR terrorism OR cyber OR "regime change" OR coup OR missile OR drone '
        'OR war OR military OR conflict OR bombing OR escalation OR assassination OR "military operation") '
        '-sports -football -soccer -basketball'
    ),
    "China-Taiwan": (
        '(China OR Taiwan OR "South China Sea" OR PLA) AND '
        '(military OR warships OR drills OR exercises OR jets OR incursions OR blockade OR '
        'missile OR sanctions OR tensions OR deterrence OR invasion OR coercion OR Xi) '
        '-sports -basketball -NBA -Olympics'
    ),
    "North Korea": (
        '"North Korea" AND '
        '(missile OR launch OR nuclear OR test OR sanctions OR artillery OR provocation '
        'OR submarine OR ICBM OR Kim) '
        '-sports -football -soccer'
    ),
    # Constrained: Venezuela + explicit security/policy terms (user-specified style).
    "Venezuela": (
        '("Venezuela" OR "Maduro" OR "Caracas") AND '
        '("military" OR "sanctions" OR "oil" OR "security" OR "China" OR "Russia" OR "Iran" '
        'OR "government" OR "crisis" OR "migration" OR "protests") '
        '-baseball -soccer -WBC -sports -MLB'
    ),
    # Constrained: Cuba + explicit security/policy terms.
    "Cuba": (
        '("Cuba" OR "Havana") AND '
        '("military" OR "security" OR "economic crisis" OR "Russia" OR "China" OR "migration" '
        'OR "sanctions" OR "protests" OR "government") '
        '-baseball -sports -MLB'
    ),
}

# Source credibility tiers for analyst-oriented filtering and display.
SOURCE_TIER_1 = {
    "Reuters", "Associated Press", "AP News", "BBC News", "BBC", "Al Jazeera English",
    "Al Jazeera", "Financial Times", "Defense News", "CSIS", "IISS", "The Economist",
    "Wall Street Journal", "Politico", "Foreign Affairs", "Foreign Policy",
}
SOURCE_TIER_2 = {
    "CNN", "NBC News", "CBS News", "ABC News", "The Guardian", "Washington Post",
    "New York Times", "Bloomberg", "Axios", "The Hill", "USA Today",
}


def get_source_tier(source_name: str) -> int:
    """Return 1 (trusted), 2 (other major), or 3 (unclassified)."""
    if not source_name:
        return 3
    name = (source_name or "").strip()
    for tier, names in enumerate((SOURCE_TIER_1, SOURCE_TIER_2), start=1):
        if any(n.lower() in name.lower() for n in names):
            return tier
    return 3


def get_newsapi_key() -> str:
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        raise EnvironmentError("NEWSAPI_KEY not found. Please set it in your .env file.")
    return api_key


def fetch_articles_for_topic(
    topic_name: str,
    query: str,
    from_days_ago: int = 3,
    page_size: int = 20,
    language: str = "en",
    sort_by: str = "publishedAt",
) -> List[Dict[str, Any]]:
    """Fetch articles from NewsAPI for a single geopolitical topic."""
    api_key = get_newsapi_key()
    from_date = (datetime.utcnow() - timedelta(days=from_days_ago)).strftime("%Y-%m-%d")

    params = {
        "q": query,
        "from": from_date,
        "language": language,
        "sortBy": sort_by,
        "pageSize": page_size,
        "apiKey": api_key,
    }

    response = requests.get(NEWS_API_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "ok":
        raise RuntimeError(f"NewsAPI returned an error: {data}")

    articles = data.get("articles", [])
    cleaned_articles: List[Dict[str, Any]] = []

    for article in articles:
        source_name = article.get("source", {}).get("name") or ""
        tier = get_source_tier(source_name)
        cleaned_articles.append(
            {
                "topic": topic_name,
                "source": source_name,
                "source_tier": tier,
                "author": article.get("author"),
                "title": article.get("title"),
                "description": article.get("description"),
                "content": article.get("content"),
                "url": article.get("url"),
                "published_at": article.get("publishedAt"),
            }
        )

    return cleaned_articles


def fetch_all_hotspot_articles() -> List[Dict[str, Any]]:
    """Fetch articles across all predefined hotspot regions."""
    all_articles: List[Dict[str, Any]] = []

    for topic_name, query in HOTSPOT_QUERIES.items():
        try:
            topic_articles = fetch_articles_for_topic(topic_name, query)
            all_articles.extend(topic_articles)
        except Exception as exc:
            print(f"[WARN] Failed to fetch articles for {topic_name}: {exc}")

    return all_articles


def fetch_all_sources() -> List[Dict[str, Any]]:
    """
    Hybrid pipeline: Tier 1 Defense News RSS + NewsAPI hotspot articles.
    Merges and deduplicates by URL. If RSS is unavailable (e.g. feedparser not installed), uses NewsAPI only.
    """
    rss_articles: List[Dict[str, Any]] = []
    try:
        from .defense_rss import fetch_defense_news
        rss_articles = fetch_defense_news()
    except Exception as exc:
        print(f"[WARN] Defense RSS skipped: {exc}. Install feedparser for RSS. Using NewsAPI only.")

    newsapi_articles = fetch_all_hotspot_articles()
    combined = rss_articles + newsapi_articles

    seen_urls: set = set()
    deduped: List[Dict[str, Any]] = []
    for a in combined:
        url = (a.get("url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(a)

    # Keep only articles that mention security/defense relevance (discard noise)
    from .relevance_filter import filter_by_security_relevance
    return filter_by_security_relevance(deduped)


def fetch_news() -> List[Dict[str, Any]]:
    """
    Wrapper used by the HTML dashboard pipeline.
    Returns NewsAPI hotspot articles; relevance filtering happens in the pipeline layer.
    On missing API key or request failure, returns [] so RSS-only pipeline can still run.
    """
    try:
        articles = fetch_all_hotspot_articles()
        if len(articles) == 0:
            _log_newsapi_diagnostic()
        return articles
    except Exception as exc:
        print(f"[WARN] NewsAPI fetch failed: {exc}")
        if "NEWSAPI_KEY" in str(exc) or "not found" in str(exc).lower():
            print("[TIP] Add NEWSAPI_KEY to .env in the project root, then restart Streamlit.")
        elif "429" in str(exc) or "rate" in str(exc).lower():
            print("[TIP] NewsAPI free tier: 100 requests/day. Limit resets at midnight UTC. Use fewer runs or wait.")
        return []


def _log_newsapi_diagnostic() -> None:
    """Run one test request to see why NewsAPI might return no articles."""
    try:
        key = get_newsapi_key()
        if not key or len(key) < 10:
            print("[NewsAPI] Key is missing or too short in .env.")
            return
        # One test request (minimal query)
        from_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
        r = requests.get(
            NEWS_API_URL,
            params={"q": "defense", "from": from_date, "pageSize": 1, "apiKey": key, "language": "en"},
            timeout=10,
        )
        if r.status_code == 401:
            print("[NewsAPI] 401 Unauthorized — key invalid or expired. Check NEWSAPI_KEY at newsapi.org.")
        elif r.status_code == 429:
            print("[NewsAPI] 429 Rate limit — free tier is 100 requests/day. Resets midnight UTC.")
        elif r.status_code != 200:
            print(f"[NewsAPI] HTTP {r.status_code}: {r.text[:200]}")
        else:
            data = r.json()
            total = data.get("totalResults", 0)
            if total == 0:
                print("[NewsAPI] Key OK but test query returned 0 results. Other queries may still return data.")
            else:
                print(f"[NewsAPI] Key OK (test returned {total}+ results). If you see 0 articles, queries may be too narrow or date range empty.")
    except Exception as e:
        print(f"[NewsAPI] Diagnostic failed: {e}")


if __name__ == "__main__":
    articles = fetch_all_hotspot_articles()
    print(f"Fetched {len(articles)} total articles.")
    for article in articles[:3]:
        print("-" * 80)
        print(f"Topic: {article['topic']}")
        print(f"Title: {article['title']}")
        print(f"Source: {article['source']}")
        print(f"Published: {article['published_at']}")
        print(f"URL: {article['url']}")

