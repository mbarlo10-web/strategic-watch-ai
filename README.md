# Strategic Watch AI

**AI-powered geopolitical risk monitoring and executive intelligence briefing system.**

Strategic Watch AI is an open-source intelligence (OSINT) platform that monitors global geopolitical hotspots and generates automated intelligence summaries using large language models. It demonstrates the application of AI to real-world geopolitical risk monitoring and executive decision support—the kind of system used by defense contractors, geopolitical risk firms, intelligence analysts, and strategy teams.

---

## What It Does

**Pipeline:**

```
RSS feeds (Defense News) + global news ingestion (NewsAPI)
    ↓
Security relevance filter + merge + deduplicate
    ↓
AI classification and risk scoring
    ↓
Automated executive intelligence briefs
    ↓
Analyst dashboard: Top 5 risks, map, escalation watch, theater drill-down
```

The system aggregates open-source and curated defense reporting, scores items by geopolitical and defense relevance, and produces:

- **Today’s Top 5 Risks** — Ranked by a risk scoring model (escalation + military relevance + recency), not just keyword filters.
- **Executive brief** — Daily strategic summary with key developments and escalation risks.
- **Conflict map** — Visual map of monitored theaters with risk levels (High / Medium / Low).
- **Escalation watch** — Items flagged for escalation potential.
- **Confidence and trend** — Per-item confidence from the AI; overall trend (Escalating / Stable / De-escalating) from the run.

---

## Source Tiers

| Tier | Role | Examples |
|------|------|----------|
| **Tier 1** | Curated defense / trusted wire | Defense News & Department of War RSS, Reuters, AP, BBC, Al Jazeera, CSIS, IISS |
| **Tier 2** | Broader discovery | NewsAPI (international outlets), major US/UK press |
| **Tier 3** | Analysis / think tanks | Extensible for additional curated sources |

Defense News & Department of War RSS are used as primary signals; NewsAPI provides broader coverage. Articles are merged and deduplicated by URL, then filtered for **security relevance** (e.g. military, strike, missile, sanctions, defense, cyber, nuclear) so non-defense noise (e.g. lifestyle or unrelated stories) is dropped before scoring.

**Adding more RSS feeds:** Edit `ingestion/defense_rss.py` and append `( "Display Name", "https://...rss-or-atom-url..." )` to the `RSS_FEEDS` list. Any standard RSS/Atom feed with `<title>`, `<link>`, and optional `<description>`/`<pubDate>` is supported. More feeds improve article variety and theater coverage when NewsAPI quota is limited.

---

## Dashboard Experience

**Global Executive View.** The app surfaces **Today’s Top 5 Risks** first, then the executive brief, escalation watch, and conflict map. **Theater filter** is optional and applies to the intelligence feed below the fold.

- **Mode 1 (default):** Top 5 strategic risks → conflict map → executive brief → escalation watch  
- **Mode 2 (optional):** Filter by theater (Russia-Ukraine, Iran-Israel, China-Taiwan, North Korea, Venezuela, Cuba, Defense) for analyst drill-down  

**Features:**

- **Relevance filtering** — Only articles that contain defense/security keywords are analyzed.
- **Risk scoring model** — Composite score from escalation signals, risk level, and recency to select the Top 5.
- **Confidence** — AI-provided confidence (High / Medium / Low) per item.
- **Trend signal** — Escalating / Stable / De-escalating from the current run.
- **Conflict map** — Full-width dark world map with the Top 5 risks plotted near their incident locations (🔴 High, 🟠 Medium, 🟢 Low).

---

## Monitored Theaters

- Russia – Ukraine  
- Iran – Israel (including Gaza, Hezbollah, Houthi)  
- China – Taiwan / South China Sea  
- North Korea  
- Venezuela  
- Cuba  
- Defense (Defense News RSS)

---

## Technology Stack

- **Language:** Python  
- **AI:** OpenAI API (classification, summarization, briefing)  
- **Data:** Defense News RSS (`feedparser`), NewsAPI  
- **UI:** Streamlit, Plotly (conflict map)  
- **Processing:** Pandas, Requests, security relevance filter, risk scoring module  

---

## Project Structure

```
Strategic Watch AI/
  ingestion/
    news_ingestion.py    # NewsAPI hotspot queries, merge, dedupe
    defense_rss.py       # Tier-1 defense + geopolitical RSS (Defense News, Dept of War, BBC, AJ, FP, etc.)
    relevance_filter.py  # Security keyword filter
  ai_pipeline/
    ai_analysis.py       # OpenAI per-article analysis (risk, confidence, etc.)
    risk_scoring.py      # Geopolitical risk score for Top 5 ranking
    rag_store.py         # ChromaDB storage for analyzed articles (RAG index)
  briefing/
    brief_generator.py   # Executive brief generation
  dashboard_template.html # Analyst Glass HTML layout (embedded in Streamlit)
  dashboard_app.py       # Main Streamlit entrypoint for the HTML dashboard
  test_app.py            # Legacy Streamlit app (useful for experimentation)
  data/
    chroma/              # Persistent vector store (created at runtime)
    last_run.json        # Cached last successful run (fallback when no new data)
  requirements.txt
  README.md
```

---

## Installation

### 1. Clone and enter the project

```bash
git clone https://github.com/yourname/strategic-watch-ai.git
cd strategic-watch-ai
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

`feedparser` is required for Defense News RSS. `python-dateutil` is used for recency in the risk scoring model.

### 3. Environment variables

```bash
cp .env.example .env
# Edit .env: set OPENAI_API_KEY and NEWSAPI_KEY
```

### 4. Run the dashboard

```bash
streamlit run dashboard_app.py
```

Open the URL shown in the terminal (for example `http://localhost:8501` or `http://localhost:8505`).

---

## Risk Scoring Model

The Top 5 are chosen by a composite **risk score** (0–1), not only by risk level:

- **35%** — Escalation signal (yes/no from AI)  
- **25%** — Risk level (High / Medium / Low)  
- **20%** — Geopolitical impact (proxied from risk level)  
- **20%** — Recency (newer articles score higher)

This turns the product from a summarizer into a **decision-support** ranking of “what matters most today.”

---

## Use Cases

- Geopolitical risk monitoring  
- Defense and intelligence situational awareness  
- Executive briefing and escalation watch  
- OSINT and analyst workflows  

---

## Disclaimer

This project uses open-source and curated news data plus automated AI analysis. Outputs are analytical aids, not authoritative intelligence. Verify critical information with primary sources.

---

## Author

Mark Barlow  
MS Artificial Intelligence in Business Candidate, Arizona State University  
Former U.S. Army Colonel — Defense Intelligence and International Security

---

## License

MIT License
