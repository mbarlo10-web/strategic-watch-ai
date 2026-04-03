#!/usr/bin/env python3
"""
Verify RSS ingestion, NewsAPI, and OpenAI for Strategic Watch.

Usage (from this folder):
  cd ~/Desktop/ArcLight-AI/strategic-watch-ai
  python verify_intel_sources.py

Does not print secret keys — only lengths and HTTP status codes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

os.chdir(ROOT)


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")

    print("Strategic Watch — connectivity check\n")
    print(f"Working directory: {ROOT}")
    print(f".env file found: {(ROOT / '.env').exists()}\n")

    # --- RSS ---
    print("--- RSS (Defense News, Dept of War, etc.) ---")
    try:
        from ingestion.defense_rss import fetch_defense_news

        articles = fetch_defense_news()
        print(f"OK  Fetched {len(articles)} articles from RSS feeds.")
        if articles:
            a0 = articles[0]
            print(f"    Example title: {(a0.get('title') or '')[:90]}")
            print(f"    Example source: {a0.get('source', '')}")
    except Exception as e:
        print(f"FAIL  {type(e).__name__}: {e}")

    # --- NewsAPI ---
    print("\n--- NewsAPI ---")
    key = os.getenv("NEWSAPI_KEY") or os.getenv("NEWS_API_KEY")
    if not key:
        print("FAIL  Set NEWSAPI_KEY (or NEWS_API_KEY) in .env")
    else:
        print(f"OK  Key loaded ({len(key)} characters)")
        try:
            import requests

            from ingestion.news_ingestion import NEWS_API_URL

            r = requests.get(
                NEWS_API_URL,
                params={
                    "q": "defense OR military OR pentagon",
                    "pageSize": 3,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "apiKey": key,
                },
                timeout=30,
            )
            print(f"    HTTP status: {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                print(f"    API status field: {data.get('status')}")
                print(f"    totalResults (approx): {data.get('totalResults')}")
                arts = data.get("articles") or []
                print(f"    articles in this page: {len(arts)}")
            else:
                print(f"    Body (truncated): {r.text[:400]}")
        except Exception as e:
            print(f"FAIL  {type(e).__name__}: {e}")

    # --- OpenAI ---
    print("\n--- OpenAI ---")
    okey = os.getenv("OPENAI_API_KEY")
    if not okey:
        print("FAIL  Set OPENAI_API_KEY in .env")
    else:
        print(f"OK  Key loaded ({len(okey)} characters)")
        try:
            from openai import OpenAI

            from ai_pipeline.ai_analysis import default_openai_model

            client = OpenAI(api_key=okey)
            model = default_openai_model()
            print(f"    Model (OPENAI_MODEL or default): {model}")
            r = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": 'Return JSON only: {"status":"ok","test":true}',
                    }
                ],
                response_format={"type": "json_object"},
                max_tokens=40,
                temperature=0,
            )
            text = (r.choices[0].message.content or "").strip()
            print(f"    Chat completion response: {text[:200]}")
            print("OK  OpenAI chat completion succeeded.")
        except Exception as e:
            print(f"FAIL  {type(e).__name__}: {e}")
            print(
                "    Tip: Try OPENAI_MODEL=gpt-4o-mini in .env if your account "
                "does not have access to the configured model."
            )

    print("\nDone.")


if __name__ == "__main__":
    main()
