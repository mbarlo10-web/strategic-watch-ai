"""
Strategic Watch AI — Dashboard App
===================================
Drop-in replacement for test_app.py
Renders the Analyst Glass HTML dashboard inside Streamlit,
fed with live data from your existing AI pipeline.

Usage:
    streamlit run dashboard_app.py
"""

import streamlit as st
import json
import os
from pathlib import Path

# Load .env from project root so it works regardless of where streamlit is run from
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(_env_path)
except Exception:
    pass

# ── Import your existing pipeline modules ──────────────────────────────────
# These are your existing files — no changes needed to them.
PIPELINE_AVAILABLE = False
PIPELINE_ERROR = None
try:
    from ingestion.news_ingestion import fetch_news
    from ingestion.defense_rss import fetch_defense_rss
    from ingestion.relevance_filter import filter_relevant
    from ai_pipeline.ai_analysis import analyze_articles
    from ai_pipeline.risk_scoring import score_and_rank
    from briefing.brief_generator import generate_brief
    PIPELINE_AVAILABLE = True
except Exception as e:  # noqa: BLE001
    PIPELINE_ERROR = e
    PIPELINE_AVAILABLE = False

try:
    from ai_pipeline.rag_store import upsert_analyses
    RAG_STORE_AVAILABLE = True
except Exception:
    upsert_analyses = None
    RAG_STORE_AVAILABLE = False

# Path for caching last successful run (fallback when NewsAPI quota exhausted or feeds down)
DATA_DIR = Path(__file__).resolve().parent / "data"
LAST_RUN_CACHE = DATA_DIR / "last_run.json"


def _save_last_run(data: dict) -> None:
    """Persist dashboard data so we can show it when feeds return no articles."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        out = {**data, "cached_at": datetime.utcnow().isoformat() + "Z"}
        LAST_RUN_CACHE.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    except Exception as e:
        print(f"[CACHE] Could not save last run: {e}")


def _load_last_run() -> dict | None:
    """Load last successful run for fallback when no articles are returned."""
    try:
        if not LAST_RUN_CACHE.exists():
            return None
        return json.loads(LAST_RUN_CACHE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[CACHE] Could not load last run: {e}")
        return None


# ── Page config — must be first Streamlit call ─────────────────────────────
st.set_page_config(
    page_title="Strategic Watch AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Minimize Streamlit chrome but keep sidebar accessible ──────────────────
st.markdown(
    """
<style>
  /* Hide Streamlit chrome (header, toolbar, menu, footer) for full-bleed dashboard */
  header { visibility: hidden; }
  #MainMenu { visibility: hidden; }
  footer { visibility: hidden; }
  [data-testid="stHeader"] { display: none; }
  [data-testid="stToolbar"] { display: none; }
  [data-testid="stDecoration"] { display: none; }
  [data-testid="stStatusWidget"] { display: none; }

  /* Remove internal padding so the HTML dashboard can sit flush */
  .block-container { padding: 0 !important; max-width: 100% !important; }
  [data-testid="stAppViewContainer"] { padding: 0 !important; }
</style>
""",
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════════
#  DATA LAYER — runs your pipeline or uses cached session state
# ══════════════════════════════════════════════════════════════════════════════

def run_pipeline(n_articles: int = 10) -> dict:
    """
    Runs the full ingestion → analysis → scoring → brief pipeline.
    Returns a unified data dict that gets injected into the HTML dashboard.
    Never raises: on any failure returns valid dashboard data with a stub brief
    and error message so the UI always renders.
    """
    try:
        with st.spinner("Fetching intelligence feeds..."):
            rss_articles   = fetch_defense_rss()
            news_articles  = fetch_news()
            all_articles   = rss_articles + news_articles
            filtered       = filter_relevant(all_articles)[:n_articles]
            print(f"[PIPELINE] RSS={len(rss_articles)}, NewsAPI={len(news_articles)}, after filter={len(filtered)}")
            if len(news_articles) == 0 and len(rss_articles) > 0:
                print("[PIPELINE] NewsAPI returned 0 articles. Add NEWSAPI_KEY to .env for Russia-Ukraine, Iran-Israel, etc. RSS-only gives Defense theater only.")

        if not filtered:
            print(f"[PIPELINE] No articles to analyze: RSS={len(rss_articles)}, NewsAPI={len(news_articles)}, after filter={len(filtered)}. Check .env and connectivity.")
            cached = _load_last_run()
            if cached:
                data = {k: v for k, v in cached.items() if k != "cached_at"}
                b = dict(data.get("brief", {}))
                b["executive_summary"] = (
                    "No new articles this run (NewsAPI quota may be exceeded or feeds down). "
                    "Showing last cached run below. Add NEWSAPI_KEY to .env and try again later."
                )
                b["headline"] = (b.get("headline") or "Cached run") + " (no new data)"
                data["brief"] = b
                print("[PIPELINE] Using cached last run.")
                return data
            brief = generate_brief([], "Stable")
            brief["executive_summary"] = (
                "No articles from feeds. Add NEWSAPI_KEY to .env for NewsAPI. "
                "Ensure RSS feeds (Defense News, Dept of War) are reachable. "
                "Run the app from the project root so .env is loaded."
            )
            return build_dashboard_data([], "Stable", [], brief, [])

        with st.spinner("Running AI analysis..."):
            analyzed = analyze_articles(filtered)

        if not analyzed:
            print(f"[PIPELINE] No analyses: {len(filtered)} articles fetched but OpenAI returned 0. Check OPENAI_API_KEY.")
            brief = generate_brief([], "Stable")
            brief["executive_summary"] = (
                "Articles were fetched but AI analysis returned no results. "
                "Check OPENAI_API_KEY in .env and that the OpenAI API is reachable."
            )
            return build_dashboard_data([], "Stable", [], brief, [])

        with st.spinner("Scoring and ranking risks..."):
            top5, trend, escalation_items = score_and_rank(analyzed)

        with st.spinner("Generating executive brief..."):
            brief = generate_brief(top5, trend)

        data = build_dashboard_data(top5, trend, escalation_items, brief, analyzed)
        _save_last_run(data)
        if RAG_STORE_AVAILABLE and upsert_analyses and analyzed:
            try:
                n = upsert_analyses(analyzed)
                print(f"[RAG] Indexed {n} analyses in ChromaDB (data/chroma).")
            except Exception as e:
                print(f"[RAG] Could not update index: {e}")
        return data

    except Exception as e:
        brief = generate_brief([], "Stable")
        brief["headline"] = "Pipeline Error"
        brief["executive_summary"] = (
            f"Pipeline error: {e}. "
            "Check .env (NEWSAPI_KEY, OPENAI_API_KEY), network connectivity, and terminal logs. "
            "RSS and NewsAPI are optional; at least one source must succeed."
        )
        return build_dashboard_data([], "Stable", [], brief, [])


def build_dashboard_data(top5, trend, escalation_items, brief, all_analyzed) -> dict:
    """
    Transforms pipeline output into the JSON structure the HTML dashboard expects.
    Edit this function if your pipeline data shapes change.
    """
    RISK_COORDS = {
        # Theater → approximate [lat, lng] for map plotting
        # Extend this dict as you add theaters
        "Iran-Israel":   [32.5,  35.5],
        "Russia-Ukraine":[49.0,  31.0],
        "China-Taiwan":  [24.0, 121.0],
        "North Korea":   [39.0, 127.0],
        "Venezuela":     [ 8.0, -66.0],
        "Cuba":          [22.0, -79.0],
        "Defense":       [35.7,  51.4],   # default to Iran region when theater=Defense
    }
    RISK_LEVEL_MAP = {"High": "H", "Medium": "M", "Low": "L"}

    # Build risk points for map (title/theater normalized in ai_analysis; fallbacks for robustness)
    risk_points = []
    for i, item in enumerate(top5[:5]):
        theater = item.get("theater") or item.get("topic", "Defense")
        coords  = RISK_COORDS.get(theater, RISK_COORDS["Defense"])
        risk_points.append({
            "lat":     coords[0],
            "lng":     coords[1],
            "label":   f"0{i+1} · {(item.get('title') or item.get('headline') or '')[:60]}",
            "risk":    RISK_LEVEL_MAP.get(item.get("risk_level","Medium"), "M"),
            "score":   f"{item.get('risk_score', 0.5):.2f}",
            "theater": theater,
            "conf":    item.get("confidence", "Medium").upper(),
        })

    # Build top5 cards (title/theater normalized in ai_analysis; fallbacks for robustness)
    top5_cards = []
    for i, item in enumerate(top5[:5]):
        top5_cards.append({
            "rank":    i + 1,
            "title":   item.get("title") or item.get("headline", ""),
            "risk":    item.get("risk_level", "Medium"),
            "theater": item.get("theater") or item.get("topic", "Defense"),
            "conf":    item.get("confidence", "Medium"),
            "source":  item.get("source", "Defense News"),
            "score":   item.get("risk_score", 0.5),
            "why":     item.get("why_it_matters", ""),
            "url":     item.get("url", "#"),
        })

    # Theater risk index and article counts per theater (for left nav and feed filtering)
    theater_risks = {}
    theater_counts = {}
    ALL_THEATERS = [
        "Russia-Ukraine", "Iran-Israel", "China-Taiwan", "North Korea",
        "Venezuela", "Cuba", "Defense",
    ]
    for t in ALL_THEATERS:
        theater_counts[t] = 0
    for item in all_analyzed:
        t = item.get("theater") or item.get("topic", "Defense")
        theater_counts[t] = theater_counts.get(t, 0) + 1
        rl = item.get("risk_level", "Low")
        weight = {"High": 1.0, "Medium": 0.5, "Low": 0.1}.get(rl, 0.1)
        theater_risks[t] = max(theater_risks.get(t, 0), weight)

    # Escalation watch items
    esc_items = []
    for item in (escalation_items or [])[:6]:
        esc_items.append({
            "text":  item.get("escalation_note", item.get("title", "")),
            "level": item.get("risk_level", "High"),
        })

    high_count = sum(1 for i in all_analyzed if i.get("risk_level") == "High")
    esc_count  = sum(1 for i in all_analyzed if i.get("escalation_signal", False))

    # Article count per source (for left nav "Sources" section)
    source_counts: dict = {}
    for item in all_analyzed:
        src = (item.get("source") or "Other").strip()
        source_counts[src] = source_counts.get(src, 0) + 1

    return {
        "meta": {
            "high_count":    high_count,
            "esc_count":     esc_count,
            "total":         len(all_analyzed),
            "trend":         trend,
            "run_timestamp": brief.get("date", ""),
            "confidence":    brief.get("overall_confidence", "High"),
        },
        "brief": {
            "headline":      brief.get("headline", ""),
            "summary":       brief.get("executive_summary", ""),
            "regional":      brief.get("regional_updates", []),
            "outlook":       brief.get("strategic_outlook", ""),
            "analyst_note":  brief.get("analyst_note", ""),
        },
        "top5":          top5_cards,
        "risk_points":   risk_points,
        "escalation":    esc_items,
        "theater_risks": theater_risks,
        "theater_counts": theater_counts,
        "source_counts": source_counts,
        "rag_items":     [
            {
                "title":   i.get("title") or i.get("headline", ""),
                "risk":    (i.get("risk_level") or "Low").upper(),
                "theater": i.get("theater") or i.get("topic", "Defense"),
                "conf":    (i.get("confidence") or "Low").upper(),
                "score":   str(round(i.get("risk_score",0.1),3)),
                "src":     i.get("source",""),
                "url":     i.get("url","#"),
                "summary": (i.get("summary") or "") + " " + (i.get("why_it_matters") or ""),
            }
            for i in all_analyzed
        ],
    }


def get_demo_data() -> dict:
    """
    Returns hardcoded demo data matching the HTML dashboard design.
    Used when the pipeline is unavailable or in preview mode.
    """
    return {
        "meta": {
            "high_count": 3, "esc_count": 6, "total": 10,
            "trend": "Escalating", "run_timestamp": "2025-03-11T13:47Z",
            "confidence": "High",
        },
        "brief": {
            "headline":   "Escalating US–Iran Conflict and Regional Military Posturing Amid Rising Tensions",
            "summary":    "Active US combat operations between the US and Iran continue to escalate, highlighted by recent US strikes and naval engagements. The White House struggles to articulate a clear exit strategy, increasing uncertainty and risk of further destabilization.",
            "regional":   [
                {"name": "Middle East", "risk": "High",   "text": "The US–Iran conflict intensifies with active strikes and naval engagements. Iran rejects ceasefire efforts, raising the risk of broader conflict."},
                {"name": "Indian Ocean","risk": "High",   "text": "Iranian warships seeking sanctuary in India and Sri Lanka complicate regional diplomacy and increase maritime conflict risk."},
                {"name": "Asia–Pacific","risk": "Medium", "text": "China consolidating military leadership amid defense budget increase. Japan advances defense mobilization."},
            ],
            "outlook":     "The US–Iran conflict remains the primary driver of regional instability with active combat and strikes likely to continue.",
            "analyst_note":"This brief synthesizes multiple high-confidence sources indicating active combat and strategic shifts in key regions.",
        },
        "top5": [
            {"rank":1,"title":"Amid US military actions, White House struggles to explain how Iran war will end","risk":"High","theater":"Defense","conf":"High","source":"Defense News","score":0.971,"why":"US combat operations in Iran signal significant escalation. Lack of clear endgame increases risk of further destabilization.","url":"#"},
            {"rank":2,"title":"Two Iranian warships take sanctuary in India and Sri Lanka","risk":"High","theater":"Defense","conf":"High","source":"Defense News","score":0.944,"why":"Naval combat actions raise significant kinetic military risk with potential to escalate regional tensions.","url":"#"},
            {"rank":3,"title":"Iran to face 'most intense day of strikes,' Hegseth says","risk":"High","theater":"Defense","conf":"Medium","source":"Defense News","score":0.921,"why":"Parliament speaker rejection combined with warnings of intense strikes indicates high risk.","url":"#"},
            {"rank":4,"title":"Australia deploys early-warning aircraft to the Middle East amid Iran attacks","risk":"Medium","theater":"Defense","conf":"High","source":"Defense News","score":0.756,"why":"Enhanced surveillance supports allied situational awareness while avoiding direct combat involvement.","url":"#"},
            {"rank":5,"title":"Australian submariners have a brush with Iran war","risk":"Medium","theater":"Defense","conf":"Medium","source":"Defense News","score":0.712,"why":"Underwater combat tensions highlight risks of escalation. Allied cooperation raises stakes in maritime security.","url":"#"},
        ],
        "risk_points": [
            {"lat":32.5, "lng":35.5, "label":"01 · Iran–Israel Theater",           "risk":"H","score":".97","theater":"Iran–Israel","conf":"HIGH"},
            {"lat":8.5,  "lng":76.0, "label":"02 · Iranian Warships – Indian Ocean","risk":"H","score":".94","theater":"Defense",    "conf":"HIGH"},
            {"lat":35.7, "lng":51.4, "label":"03 · Iran Strike Warning",            "risk":"H","score":".92","theater":"Iran–Israel","conf":"MEDIUM"},
            {"lat":-25.0,"lng":133.0,"label":"04 · Australia EW Aircraft",          "risk":"M","score":".76","theater":"Defense",    "conf":"HIGH"},
            {"lat":-34.9,"lng":138.6,"label":"05 · Aus. Submariners – Iran War",    "risk":"M","score":".71","theater":"Defense",    "conf":"MEDIUM"},
        ],
        "escalation": [
            {"text":"Potential for further US–Iran naval clashes in the Indian Ocean and Persian Gulf.","level":"High"},
            {"text":"Risk of miscalculation in underwater operations involving allied submarines near Iran.","level":"High"},
            {"text":"Iran ceasefire rejection increases risk of direct US military retaliation.","level":"High"},
            {"text":"China's military leadership purge may lead to assertive regional posturing.","level":"Medium"},
            {"text":"Possible separation of conflict if Iran retaliates to US strikes with regional assets.","level":"Medium"},
            {"text":"Australia's enhanced surveillance posture signals growing allied commitment.","level":"Medium"},
        ],
        "theater_risks": {
            "Iran-Israel":0.94,"Russia-Ukraine":0.80,"China-Taiwan":0.62,
            "North Korea":0.50,"Venezuela":0.22,"Cuba":0.15,
        },
        "theater_counts": {
            "Russia-Ukraine":0,"Iran-Israel":0,"China-Taiwan":2,"North Korea":0,"Venezuela":0,"Cuba":0,"Defense":6,
        },
        "source_counts": {"Defense News": 6, "BBC World": 2, "Foreign Policy": 2},
        "rag_items": [
            {"title":"Two Iranian warships take sanctuary in India and Sri Lanka","risk":"HIGH","theater":"Defense","conf":"HIGH","score":"0.944","src":"Defense News","url":"#"},
            {"title":"Australian submariners have a brush with Iran war","risk":"MEDIUM","theater":"Defense","conf":"MEDIUM","score":"0.712","src":"Defense News","url":"#"},
            {"title":"Iran to face most intense day of strikes, Hegseth says","risk":"HIGH","theater":"Defense","conf":"MEDIUM","score":"0.921","src":"Defense News","url":"#"},
            {"title":"Australia deploys early-warning aircraft to the Middle East","risk":"MEDIUM","theater":"Defense","conf":"HIGH","score":"0.756","src":"Defense News","url":"#"},
            {"title":"Amid US military actions, White House struggles to explain how Iran war will end","risk":"HIGH","theater":"Defense","conf":"HIGH","score":"0.971","src":"Defense News","url":"#"},
            {"title":"China steps up 2026 defence budget by 7% amid purge of generals","risk":"MEDIUM","theater":"China-Taiwan","conf":"MEDIUM","score":"0.640","src":"Defense News","url":"#"},
            {"title":"Japan shrugs off RCAF delays but moves on export rules","risk":"LOW","theater":"China-Taiwan","conf":"LOW","score":"0.310","src":"Defense News","url":"#"},
            {"title":"US Space Force clears design milestone, advances missile-warning constellation","risk":"LOW","theater":"Defense","conf":"MEDIUM","score":"0.290","src":"Defense News","url":"#"},
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE — persists data between Streamlit reruns
# ══════════════════════════════════════════════════════════════════════════════

if "dashboard_data" not in st.session_state:
    st.session_state.dashboard_data = get_demo_data()
if "pipeline_ran" not in st.session_state:
    st.session_state.pipeline_ran = False

# ── Sidebar control (hidden by default, accessible via Streamlit ≡ menu) ───
with st.sidebar:
    st.markdown("### ⚙️ Pipeline Controls")
    n_articles = st.slider("Articles to analyze", 5, 15, 10)
    if PIPELINE_ERROR:
        st.error(f"Pipeline imports failed: {PIPELINE_ERROR}")
    if st.button("▶ Run Intelligence Update", type="primary"):
        if PIPELINE_AVAILABLE:
            try:
                st.session_state.dashboard_data = run_pipeline(n_articles)
                st.session_state.pipeline_ran = True
                st.success("Pipeline complete.")
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"Pipeline error: {e}")
        else:
            st.warning("Pipeline modules not available — using demo data.")
    st.markdown("---")
    st.markdown("**Mode:** " + ("🟢 Live Pipeline" if PIPELINE_AVAILABLE else "🟡 Demo Data"))


# ══════════════════════════════════════════════════════════════════════════════
#  HTML BUILDER — injects live data into the dashboard template
# ══════════════════════════════════════════════════════════════════════════════

def build_html(data: dict) -> str:
    """
    Reads the dashboard HTML template and injects Python data as JSON.
    The template uses __DASHBOARD_DATA__ as its injection point.
    """
    template_path = Path(__file__).parent / "dashboard_template.html"
    html = template_path.read_text(encoding="utf-8")

    # Inject data as a JS variable at the top of the script block
    data_json = json.dumps(data, ensure_ascii=False, indent=2)
    injection = f"const PIPELINE_DATA = {data_json};\n"
    html = html.replace("/* __PIPELINE_DATA_INJECTION__ */", injection)

    return html


# ══════════════════════════════════════════════════════════════════════════════
#  RENDER
# ══════════════════════════════════════════════════════════════════════════════

data = st.session_state.dashboard_data
html = build_html(data)

# Render nearly full-screen; allow internal scrolling
st.components.v1.html(html, height=1080, scrolling=True)
