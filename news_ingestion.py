from ingestion.news_ingestion import *  # noqa: F403


if __name__ == "__main__":
    articles = fetch_all_hotspot_articles()

    print(f"\nFetched {len(articles)} total articles\n")

    for article in articles[:5]:
        print("-" * 70)
        print(f"Topic: {article['topic']}")
        print(f"Title: {article['title']}")
        print(f"Source: {article['source']}")
        print(f"Published: {article['published_at']}")
        print(f"URL: {article['url']}")

