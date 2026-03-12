from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ai_analysis import analyze_articles
from brief_generator import generate_executive_brief, format_brief_as_markdown
from news_ingestion import fetch_all_sources
from ai_pipeline.risk_scoring import rank_and_select_top
from ai_pipeline.rag_store import query_analyses, upsert_analyses

# Risk level color coding: High = Red, Medium = Orange/Yellow, Low = Green
RISK_COLOR = {"High": "#c0392b", "Medium": "#e67e22", "Low": "#27ae60"}
RISK_EMOJI = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}

# Theater approximate coordinates for conflict map (lat, lon) by theater
THEATER_COORDS = {
    "Russia-Ukraine": (49.0, 32.0),
    "Iran-Israel": (32.0, 35.0),
    "China-Taiwan": (25.0, 121.5),
    "North Korea": (39.0, 125.8),
    "Venezuela": (10.5, -66.9),
    "Cuba": (22.0, -80.0),
    "Defense": (38.9, -77.0),
}

# Finer-grained incident locations by country/region name
LOCATION_COORDS = {
    "Ukraine": (49.0, 32.0),
    "Russia": (55.0, 37.0),
    "Kharkiv": (49.99, 36.23),
    "Crimea": (44.6, 34.0),
    "Iran": (32.0, 53.0),
    "Tehran": (35.7, 51.4),
    "Israel": (31.5, 35.0),
    "Gaza": (31.5, 34.45),
    "Lebanon": (33.8, 35.8),
    "Syria": (34.8, 38.0),
    "Iraq": (33.3, 44.4),
    "Yemen": (15.6, 48.5),
    "China": (35.0, 103.0),
    "Taiwan": (23.7, 121.0),
    "South China Sea": (15.0, 115.0),
    "North Korea": (40.0, 127.0),
    "South Korea": (37.5, 127.0),
    "Venezuela": (7.0, -66.0),
    "Caracas": (10.5, -66.9),
    "Cuba": (22.0, -80.0),
    "Havana": (23.1, -82.4),
    "India": (21.0, 78.0),
    # place Sri Lanka incidents slightly offshore to reflect naval activity
    "Sri Lanka": (6.5, 82.0),
    "Red Sea": (18.0, 40.0),
    "Persian Gulf": (26.0, 52.0),
}


def risk_emoji(risk: str) -> str:
    """Return color indicator emoji for expander titles."""
    r = (risk or "").strip()
    return RISK_EMOJI.get(r, "⚪")


def risk_colored_html(risk: str) -> str:
    """Return HTML span with risk level colored (for use with st.markdown(..., unsafe_allow_html=True))."""
    r = (risk or "").strip()
    color = RISK_COLOR.get(r, "#95a5a6")
    return f'<span style="color: {color}; font-weight: 600;">{r or "N/A"}</span>'


def truncate(text: str, max_chars: int = 220) -> str:
    """Approximate two-line truncation with ellipsis."""
    if not text:
        return "—"
    t = str(text).strip()
    if len(t) <= max_chars:
        return t
    return t[:max_chars].rstrip() + "…"


st.set_page_config(
    page_title="Strategic Watch AI",
    page_icon="🌍",
    layout="wide",
)

st.markdown(
    """
<style>
  .sw-panel {
    background: rgba(15, 26, 38, 0.70);
    border: 1px solid rgba(110, 130, 150, 0.25);
    border-radius: 10px;
    padding: 12px 14px;
  }
  .sw-muted { color: rgba(255,255,255,0.70); }
  .sw-kicker { letter-spacing: 0.08em; text-transform: uppercase; font-size: 0.75rem; color: rgba(255,255,255,0.55); }
  .sw-divider { height: 1px; background: rgba(110,130,150,0.25); margin: 10px 0; }
</style>
""",
    unsafe_allow_html=True,
)

st.title("🌍 Strategic Watch AI")
st.caption("Geopolitical Intelligence Dashboard · Executive OSINT Monitor")
st.write(
    "**Global Executive View.** Today's top strategic risks surface first, then the executive brief and "
    "escalation watch. Use **Filter by theater** in the sidebar for analyst drill-down. "
    "Run an intelligence update to refresh."
)
st.caption("Tip: use the **▸ settings arrow** in the top-left to open or close the settings panel.")

with st.expander("📋 Risk level guide (applies to all conflict zones)", expanded=True):
    st.caption("Same definitions for Russia-Ukraine, Iran-Israel, China-Taiwan, North Korea, Venezuela, Cuba.")
    st.markdown(
        '<span style="color: #c0392b; font-weight: 600;">High</span> — Active combat, strikes, or kinetic attack; '
        "terrorism or major attack; imminent escalation or regime collapse; significant cyber/EW attack on critical "
        "systems; coup or violent government overthrow; direct threat to sovereignty or mass casualties.",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<span style="color: #f1c40f; font-weight: 600;">Medium</span> — Significant military buildup or tension; '
        "sanctions or coercion with escalation risk; serious instability or protests with security impact; "
        "indirect threat or proxy activity; cyber/EW incident with limited impact.",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<span style="color: #27ae60; font-weight: 600;">Low</span> — Monitoring or routine activity; '
        "de-escalation or diplomatic outreach; commentary or analysis with no new event; "
        "economic/market impact only; no direct security or combat implication.",
        unsafe_allow_html=True,
    )
    st.caption("🔴 High  ·  🟠 Medium  ·  🟢 Low")

ALL_TOPICS = [
    "Russia-Ukraine",
    "Iran-Israel",
    "China-Taiwan",
    "North Korea",
    "Venezuela",
    "Cuba",
    "Defense",
]

if "article_limit" not in st.session_state:
    st.session_state.article_limit = 15
if "selected_topics" not in st.session_state:
    st.session_state.selected_topics = ALL_TOPICS.copy()

if "prefer_tier1_only" not in st.session_state:
    st.session_state.prefer_tier1_only = False
if "layout_mode" not in st.session_state:
    st.session_state.layout_mode = "Executive"

with st.sidebar:
    st.header("Settings")
    st.session_state.layout_mode = st.selectbox(
        "Layout",
        options=["Executive", "Ops (dense)"],
        index=0 if st.session_state.layout_mode == "Executive" else 1,
        help="Ops layout approximates a Palantir-style dense panel view.",
    )
    article_limit = st.slider(
        "Articles to analyze",
        min_value=5,
        max_value=15,
        value=int(st.session_state.article_limit),
    )
    st.caption(
        "Global view uses Defense News + Department of War RSS + NewsAPI; "
        "Top 5 are ranked by a risk score model."
    )
    selected_topics = st.multiselect(
        "Filter by theater (optional)",
        options=ALL_TOPICS,
        default=list(st.session_state.selected_topics),
        help="Applies to the Intelligence feed below the fold. Top 5 and brief use all sources.",
    )
    prefer_tier1 = st.checkbox(
        "Tier 1 sources only (Reuters, AP, BBC, Defense News, CSIS, IISS, etc.)",
        value=bool(st.session_state.prefer_tier1_only),
    )
    st.session_state.prefer_tier1_only = prefer_tier1
    st.markdown("### Controls")
    run_clicked = st.button("Run Intelligence Update", use_container_width=True)


st.write("---")

if run_clicked:
    st.session_state.article_limit = int(article_limit)
    st.session_state.selected_topics = list(selected_topics)
    st.success("Fetching Defense News + Department of War RSS + NewsAPI and running AI analysis...")

    try:
        raw_articles = fetch_all_sources()
    except Exception as exc:
        st.error(f"Ingestion failed: {exc}")
    else:
        # Global view: use all articles up to limit (no theater filter for Top 5 / brief)
        limited = raw_articles[: st.session_state.article_limit]
        st.session_state.last_run_ts = datetime.utcnow()
        st.session_state.last_sources_count = len(raw_articles)

        if not limited:
            st.warning("No articles returned from Defense News RSS or NewsAPI.")
        else:
            with st.spinner("Analyzing articles with OpenAI..."):
                try:
                    analyses = analyze_articles(limited, limit=len(limited))
                except Exception as exc:
                    st.error(f"AI analysis failed: {exc}")
                    analyses = []

            if analyses:
                if st.session_state.get("prefer_tier1_only"):
                    analyses_tier1 = [a for a in analyses if a.get("source_tier", 3) == 1]
                    if analyses_tier1:
                        analyses = analyses_tier1
                    else:
                        st.warning("No Tier 1 sources in this run. Showing all sources.")

                # Top 5 via geopolitical risk scoring model (escalation + risk level + recency)
                top5_list = rank_and_select_top(analyses, top_n=5)
                top5 = [a for a in top5_list]  # already have risk_score attached

                df = pd.DataFrame(analyses)
                total = len(df)
                high_risk = (df["risk_level"] == "High").sum() if "risk_level" in df.columns else 0
                escalation_count = df["escalation_signal"].fillna(False).astype(bool).sum() if "escalation_signal" in df.columns else 0

                # ----- Run info -----
                ts = st.session_state.get("last_run_ts") or datetime.utcnow()
                src_count = st.session_state.get("last_sources_count", 0)
                st.markdown("#### Run info")
                info1, info2, info3 = st.columns(3)
                info1.caption(f"**Last updated:** {ts.strftime('%Y-%m-%d %H:%M')} UTC")
                info2.caption(
                    f"**Sources queried:** {src_count} (Defense News + Department of War RSS + NewsAPI, deduped)"
                )
                info3.caption("**Models:** OpenAI + Tier 1 RSS (Defense News, Department of War) + NewsAPI")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Articles analyzed", total)
                m2.metric("High risk events", int(high_risk))
                m3.metric("Escalation signals", int(escalation_count))
                # Trend signal from current run
                if escalation_count >= 2 or high_risk >= 2:
                    trend_label, trend_color = "Escalating", "#c0392b"
                elif high_risk == 0 and escalation_count == 0:
                    trend_label, trend_color = "De-escalating", "#27ae60"
                else:
                    trend_label, trend_color = "Stable", "#f1c40f"
                m4.markdown(f"**Trend:** <span style='color: {trend_color}; font-weight: 600;'>{trend_label}</span>", unsafe_allow_html=True)

                if st.session_state.layout_mode == "Ops (dense)":
                    st.markdown("---")
                    left, mid, right = st.columns([1.05, 2.2, 1.15], gap="medium")

                    with left:
                        st.markdown('<div class="sw-panel">', unsafe_allow_html=True)
                        st.markdown('<div class="sw-kicker">Top risks</div>', unsafe_allow_html=True)
                        for i, a in enumerate(top5, 1):
                            risk = a.get("risk_level", "N/A")
                            headline = a.get("headline", "Untitled")
                            st.markdown(
                                f"{risk_emoji(risk)} <strong>{i}. {headline}</strong><br/><span class='sw-muted'>{risk_colored_html(risk)} · {(a.get('topic') or '—')}</span>",
                                unsafe_allow_html=True,
                            )
                            st.markdown('<div class="sw-divider"></div>', unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)

                    with mid:
                        st.markdown('<div class="sw-panel">', unsafe_allow_html=True)
                        st.markdown('<div class="sw-kicker">Conflict map</div>', unsafe_allow_html=True)
                        # map already rendered below; in ops mode we keep the same map section for now
                        st.markdown("<span class='sw-muted'>Scroll down for map and details.</span>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)

                    with right:
                        st.markdown('<div class="sw-panel">', unsafe_allow_html=True)
                        st.markdown('<div class="sw-kicker">Escalation watch</div>', unsafe_allow_html=True)
                        esc_candidates = [a for a in analyses if a.get("escalation_signal")]
                        esc_sorted = sorted(
                            esc_candidates,
                            key=lambda a: {"High": 0, "Medium": 1, "Low": 2}.get(
                                (a.get("risk_level") or "").strip(), 3
                            ),
                        )
                        for a in esc_sorted[:6]:
                            risk = a.get("risk_level", "N/A")
                            st.markdown(
                                f"{risk_emoji(risk)} <strong>{a.get('headline','Untitled')}</strong><br/><span class='sw-muted'>{risk_colored_html(risk)} · {a.get('topic','')}</span>",
                                unsafe_allow_html=True,
                            )
                            st.markdown('<div class="sw-divider"></div>', unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)

                # ----- Conflict map -----
                st.markdown("---")
                st.markdown("## Conflict map")
                map_points = []
                for i, a in enumerate(top5, 1):
                    topic = a.get("topic") or "Other"
                    risk = (a.get("risk_level") or "").strip()
                    headline = a.get("headline", "Untitled")
                    lat = lon = None
                    # Prefer specific incident locations from country_or_region list
                    locations = a.get("country_or_region") or []
                    if isinstance(locations, str):
                        locations = [locations]
                    for loc in locations:
                        if loc in LOCATION_COORDS:
                            lat, lon = LOCATION_COORDS[loc]
                            break
                    # Fallback: theater centroid
                    if lat is None and topic in THEATER_COORDS:
                        lat, lon = THEATER_COORDS[topic]
                    if lat is not None and lon is not None:
                        # jitter markers a bit so overlapping incidents are visible
                        jitter_lat = lat + (i - 3) * 0.8
                        jitter_lon = lon + (i - 3) * 1.2
                        map_points.append(
                            {
                                "lat": jitter_lat,
                                "lon": jitter_lon,
                                "theater": topic,
                                "risk": risk or "N/A",
                                "index": i,
                                "headline": headline,
                            }
                        )
                if map_points:
                    df_map = pd.DataFrame(map_points)
                    color_map = {"High": "#c0392b", "Medium": "#e67e22", "Low": "#27ae60"}
                    df_map["color"] = df_map["risk"].map(color_map).fillna("#95a5a6")
                    fig = go.Figure(
                        data=go.Scattergeo(
                            lat=df_map["lat"],
                            lon=df_map["lon"],
                            text=df_map["index"].astype(str),
                            hovertext=df_map["headline"],
                            hoverinfo="text",
                            mode="markers+text",
                            textposition="top center",
                            marker=dict(
                                size=18,
                                color=df_map["color"],
                                line=dict(width=1, color="#ecf0f1"),
                            ),
                        )
                    )
                    fig.update_layout(
                        height=420,
                        margin=dict(l=0, r=0, t=0, b=0),
                        showlegend=False,
                        template="plotly_dark",
                        geo=dict(
                            projection_type="equirectangular",
                            bgcolor="rgba(0,0,0,0)",
                            showland=True,
                            landcolor="#22313f",
                            showocean=True,
                            oceancolor="#0b1b2b",
                            showcountries=True,
                            countrycolor="#7f8c8d",
                        ),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                st.caption("Top 5 risks plotted near their incident locations. 🔴 High  ·  🟠 Medium  ·  🟢 Low")

                # ----- Mode 1: Top 5 strategic risks -----
                st.markdown("---")
                st.markdown("## Today's Top 5 Risks")
                st.caption("Ranked by risk score (escalation + military relevance + recency). Confidence from AI. Risk: 🔴 High  ·  🟠 Medium  ·  🟢 Low")
                for i, a in enumerate(top5, 1):
                    headline = a.get("headline", "Untitled")
                    risk = a.get("risk_level", "N/A")
                    confidence = (a.get("confidence") or "—").strip() or "—"
                    topic = a.get("topic", "—")
                    why = a.get("why_it_matters") or "—"
                    source = a.get("source", "Unknown")
                    url = a.get("url", "")
                    score = a.get("risk_score")
                    risk_icon = risk_emoji(risk)
                    with st.container():
                        st.markdown(f"### {risk_icon} {i}. {headline}")
                        st.markdown(
                            f"**Risk:** {risk_colored_html(risk)} · **Confidence:** {confidence} · **Theater:** {topic} · **Source:** {source}",
                            unsafe_allow_html=True,
                        )
                        if score is not None:
                            st.caption(f"Risk score: {score}")
                        st.markdown("**Why it matters:**  \n" + truncate(why, 220))
                        if url:
                            st.markdown(f"[Read: {source}]({url})")
                        st.write("")

                # ----- Executive brief -----
                st.markdown("---")
                st.markdown("## Executive brief")
                with st.spinner("Generating executive brief..."):
                    try:
                        # RAG: store current run analyses for semantic retrieval
                        try:
                            upserted = upsert_analyses(analyses)
                            if upserted:
                                st.caption(f"RAG index updated: {upserted} item(s) embedded and stored.")
                        except Exception:
                            # RAG is an enhancement; brief generation must still work if indexing fails.
                            pass

                        # RAG-assisted brief: retrieve the most relevant items for the global question
                        rag_hits = []
                        try:
                            rag_hits = query_analyses(
                                "What are the top geopolitical and military risks today? Focus on escalation, strikes, cyber, missiles, deployments.",
                                n_results=min(10, len(analyses)),
                            )
                        except Exception:
                            rag_hits = []

                        if rag_hits:
                            hit_urls = {h.get("url") for h in rag_hits if h.get("url")}
                            rag_subset = [a for a in analyses if a.get("url") in hit_urls]
                            brief_input = rag_subset if rag_subset else analyses
                        else:
                            brief_input = analyses

                        brief = generate_executive_brief(brief_input)
                        brief_md = format_brief_as_markdown(brief)
                        st.markdown(brief_md)
                        with st.expander("View brief JSON"):
                            st.json(brief)
                    except Exception as exc:
                        st.error(f"Executive brief generation failed: {exc}")

                # ----- Escalation watch -----
                escalation_items = [a for a in analyses if a.get("escalation_signal")]
                st.markdown("---")
                st.markdown("## Escalation watch")
                st.caption(
                    "🔴 High — active combat or imminent major attack · "
                    "🟠 Medium — significant military tension or coercion with escalation risk · "
                    "🟢 Low — monitoring, de-escalation, or commentary only."
                )
                if escalation_items:
                    # Order items from High → Medium → Low based on risk_level
                    risk_order = {"High": 0, "Medium": 1, "Low": 2}
                    escalation_items_sorted = sorted(
                        escalation_items,
                        key=lambda a: risk_order.get((a.get("risk_level") or "").strip(), 3),
                    )
                    st.caption(f"{len(escalation_items_sorted)} item(s) flagged for escalation potential.")
                    for a in escalation_items_sorted:
                        risk = a.get("risk_level", "N/A")
                        topic = a.get("topic", "")
                        headline = a.get("headline", "Untitled")
                        why = a.get("why_it_matters") or ""
                        st.markdown(
                            f"- **{headline}** — {risk_emoji(risk)} {risk_colored_html(risk)} · {topic}",
                            unsafe_allow_html=True,
                        )
                        st.caption(truncate(why, 220))
                else:
                    st.caption("No items flagged for escalation in this run.")

                # ----- Below the fold: Theater drill-down + Intelligence feed -----
                st.markdown("---")
                st.markdown("## Theater drill-down · Intelligence feed")
                feed_analyses = [a for a in analyses if a.get("topic") in st.session_state.selected_topics]
                if not feed_analyses:
                    st.caption("No items match the selected theaters. Select more in the sidebar or show all.")
                    feed_analyses = analyses

                st.caption("Optional filter by theater applies here. Top 5 and brief use the full global set.")

                # Order theater drill-down from High → Medium → Low based on risk level
                risk_order = {"High": 0, "Medium": 1, "Low": 2}
                feed_analyses_sorted = sorted(
                    feed_analyses,
                    key=lambda a: risk_order.get((a.get("risk_level") or "").strip(), 3),
                )

                for a in feed_analyses_sorted:
                    row_dict = a
                    headline = row_dict.get("headline", "Untitled")
                    risk = row_dict.get("risk_level", "N/A")
                    topic = row_dict.get("topic", "N/A")
                    event_type = row_dict.get("event_type", "N/A")
                    actors = row_dict.get("key_actors", [])
                    actors_str = ", ".join(actors) if isinstance(actors, list) else str(actors)
                    source = row_dict.get("source", "Unknown")
                    tier = row_dict.get("source_tier", 3)
                    tier_label = "Tier 1" if tier == 1 else ("Tier 2" if tier == 2 else "Other")
                    risk_icon = risk_emoji(risk)
                    confidence = (row_dict.get("confidence") or "—").strip() or "—"
                    with st.expander(f"{risk_icon} {headline} | {risk} risk"):
                        st.markdown(
                            f"<strong>Risk:</strong> {risk_colored_html(risk)} · <strong>Confidence:</strong> {confidence} · "
                            f"<strong>Topic:</strong> {topic} · <strong>Event type:</strong> {event_type}",
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"**Actors:** {actors_str or '—'}")
                        st.markdown("---")
                        st.markdown("**Summary**  \n" + (row_dict.get("summary") or "—"))
                        st.markdown("**Why it matters**  \n" + truncate(row_dict.get("why_it_matters") or "—", 220))
                        st.markdown("---")
                        st.caption("**Why this article matched**  \nMatched topic: " + str(topic) + " · Event type: " + str(event_type))
                        st.caption(f"Source: {source} ({tier_label})")
                        url = row_dict.get("url")
                        if url:
                            st.markdown(f"[Read article]({url})")
            else:
                st.warning("No AI analyses were returned.")
else:
    st.info(
        "Click **Run Intelligence Update** for the global view: Top 5 risks, executive brief, escalation watch, "
        "then optional theater drill-down below. Defense News RSS + NewsAPI are used by default."
    )

# ----- Semantic search (RAG) -----
st.markdown("---")
st.markdown("## Semantic search (RAG)")
st.caption("Ask a question and retrieve the most relevant indexed items (vector search over prior runs).")
rag_query = st.text_input("Search", placeholder="e.g., Iranian naval escalation near Sri Lanka")
if rag_query:
    try:
        rag_hits = query_analyses(rag_query, n_results=5)
    except Exception as exc:
        rag_hits = []
        st.error(f"RAG search failed: {exc}")
    if rag_hits:
        for h in rag_hits:
            risk = h.get("risk_level") or "N/A"
            topic = h.get("topic") or "—"
            src = h.get("source") or "—"
            url = h.get("url") or ""
            doc = (h.get("document") or "").splitlines()[0] if h.get("document") else "Result"
            st.markdown(
                f"- **{doc}** — {risk_emoji(risk)} {risk_colored_html(risk)} · {topic} · {src}",
                unsafe_allow_html=True,
            )
            if url:
                st.markdown(f"  - [Read source]({url})")
    else:
        st.caption("No results found (or index is empty).")
