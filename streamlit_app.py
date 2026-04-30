"""Streamlit page that calls the FastAPI endpoint and renders the campaign."""

from __future__ import annotations

import json
import os

import httpx
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Klaviyo Agent Demo", layout="wide")
st.title("Marketing Campaign Generator")
st.caption(
    "Multi-agent demo: segmenter → strategist → content writer → A/B generator → reviewer. "
    "Backed by Claude + LangGraph; traces emit to Langfuse if configured."
)

if "campaign" not in st.session_state:
    st.session_state.campaign = None
if "error" not in st.session_state:
    st.session_state.error = None

col1, col2 = st.columns([1, 4])
with col1:
    if st.button("Generate campaign", type="primary"):
        st.session_state.error = None
        with st.spinner("Running graph (5 agents, ~20s)..."):
            try:
                resp = httpx.post(f"{API_URL}/generate-campaign", json={}, timeout=120)
                resp.raise_for_status()
                st.session_state.campaign = resp.json()
            except Exception as e:
                st.session_state.error = str(e)
                st.session_state.campaign = None

if st.session_state.error:
    st.error(st.session_state.error)

campaign = st.session_state.campaign
if campaign is None:
    st.info("Click **Generate campaign** to run the full agent graph.")
    st.stop()


# ----- segments -------------------------------------------------------------
st.subheader("Segments")
seg_cols = st.columns(len(campaign["segments"]))
for col, seg in zip(seg_cols, campaign["segments"], strict=True):
    with col:
        st.metric(seg["name"], f"{seg['customer_count']} customers")
        st.caption(seg["description"])

# ----- per-segment content + A/B + scores ----------------------------------
st.subheader("Per-segment campaigns")

ab_by_segment = {a["segment"]: a for a in campaign["ab_tests"]}
quality_by_segment = {q["segment"]: q for q in campaign["quality"]["scores"]}
strategy_by_segment = {s["segment"]: s for s in campaign["strategy"]["strategies"]}

for content in campaign["content"]:
    seg = content["segment"]
    strategy = strategy_by_segment.get(seg, {})
    ab = ab_by_segment.get(seg, {})
    score = quality_by_segment.get(seg, {})

    with st.expander(f"**{seg}** — {content['campaign_type']}", expanded=True):
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"**Subject:** {content['email']['subject_line']}")
            st.markdown(f"**Preview:** _{content['email']['preview_text']}_")
            st.markdown("**Email body:**")
            st.text(content["email"]["body"])
            st.markdown(f"**SMS:** {content['sms']['body']}")
            if ab:
                st.markdown("**Subject line A/B variants:**")
                for v in ab.get("variants", []):
                    st.markdown(f"- *{v['angle']}*: {v['text']}")
        with c2:
            if strategy:
                st.markdown(f"**Send time:** {strategy.get('recommended_send_time', '—')}")
                st.markdown(f"**Goal:** {strategy.get('primary_goal', '—')}")
                st.caption(strategy.get("rationale", ""))
            st.divider()
            if score:
                st.markdown("**Quality scores**")
                st.markdown(
                    f"- Brand voice: {score['brand_voice']}/5\n"
                    f"- Clarity: {score['clarity']}/5\n"
                    f"- Actionability: {score['actionability']}/5\n"
                    f"- **Overall: {score['overall']}/5**"
                )
                if score.get("sounds_ai_generated"):
                    st.warning("Reviewer flagged: sounds AI-generated")
                for flag in score.get("flags", []):
                    st.caption(f"flag: {flag}")
                st.caption(f"Verdict: {score.get('one_line_verdict', '')}")

# ----- blocking issues + raw ------------------------------------------------
blocking = campaign["quality"].get("blocking_issues", [])
if blocking:
    st.error("Reviewer flagged blocking issues:")
    for b in blocking:
        st.markdown(f"- {b}")

with st.expander("Raw JSON"):
    st.code(json.dumps(campaign, indent=2), language="json")
