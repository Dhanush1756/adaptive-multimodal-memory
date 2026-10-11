"""Streamlit demo (brief sections 47 and 63).

    streamlit run app/streamlit_app.py

Sidebar: model status, memory statistics, reset. Main: add a memory (text + optional image),
see the extracted claim / detections / memory decision, then ask questions and inspect evidence.
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from src.agent.reasoning import MemoryAgent  # noqa: E402
from src.config import load_config  # noqa: E402

st.set_page_config(page_title="Adaptive Evidence-Grounded Memory", layout="wide")


@st.cache_resource(show_spinner="Loading models (falls back to light mode if unavailable)...")
def get_agent(light: bool) -> MemoryAgent:
    return MemoryAgent(load_config(), db_path=":memory:", image_dir="data/processed/images", light=light)


with st.sidebar:
    st.header("Memory")
    light = st.toggle("Light mode (no model downloads)", value=False)
    agent = get_agent(light)
    st.json(agent.status())
    if st.button("Reset memory"):
        agent.reset()
        st.session_state.pop("last", None)
        st.rerun()

st.title("Adaptive Evidence-Grounded Memory")
left, right = st.columns(2)

# ------------------------------------------------------------------ add memory
with left:
    st.subheader("1. Add a memory")
    text = st.text_input("What happened?", placeholder="I bought a red Tesla.")
    up = st.file_uploader("Photo (optional)", type=["jpg", "jpeg", "png"])
    when = st.date_input("Date", value=datetime.now().date())
    sid = st.text_input("Session id (optional)")
    if st.button("Store", type="primary"):
        if not text and up is None:
            st.warning("Enter text or upload an image.")
        else:
            image = None
            if up is not None:
                from PIL import Image
                image = Image.open(up).convert("RGB")
            st.session_state["last"] = agent.remember(
                text, image, datetime.combine(when, datetime.min.time()).replace(hour=10), sid or None)
    res = st.session_state.get("last")
    if res is not None:
        d = res.decision
        st.markdown(f"**Memory action: `{d.action.value}`** ({res.session_id})")
        st.write(d.reason)
        st.json({"claim": res.claim, "image": res.image, "decision": d.to_dict()}, expanded=False)
        for n in res.notes:
            st.caption(n)

# --------------------------------------------------------------------- query
with right:
    st.subheader("2. Ask")
    q = st.text_input("Question", placeholder="What color is my car now?")
    if st.button("Ask") and q:
        ans = agent.ask(q)
        st.markdown(f"### {ans.text}")
        st.caption(f"intent: {ans.intent} · confidence: {ans.confidence:.0%} · found: {ans.found}")
        if ans.evidence:
            st.markdown("**Evidence**")
            for it in ans.evidence:
                if it["modality"] == "text":
                    st.write(f"- [{it['role']}] text ({it.get('session_id', '')}, {str(it.get('timestamp', ''))[:10]}): "
                             f"“{it['text']}”")
                else:
                    st.write(f"- [{it['role']}] image {it['image_id']} looks **{it.get('visual_value')}**")
                    p = it.get("image_path")
                    if p and Path(p).exists():
                        st.image(p, width=220)
        with st.expander("Grounded prompt (what an LLM would see)"):
            st.code(ans.prompt or "(not found)")

# ------------------------------------------------------------------ timeline
st.subheader("3. Timeline")
rows = [r for e in agent.store.entities() for r in agent.timeline_for(e["entity"])]
if not rows:
    st.info("Nothing stored yet.")
else:
    for r in rows:
        badge = "🟢 CURRENT" if r.status.value == "CURRENT" else "⚪ HISTORICAL"
        imgs = ", ".join(v.image_id for v in r.visual_evidence) or "no image"
        st.write(f"**{r.entity_id}** · {r.timestamp[:10]} · **{r.value}** · {badge} · "
                 f"{r.memory_id} (prev: {r.previous_memory_id or '-'}) · {imgs} · conf {r.confidence:.2f}")
conflicts = [r for r in agent.store.all() if r.status.value == "CONTRADICTORY"]
for r in conflicts:
    st.warning(f"Conflict {r.memory_id}: '{r.value}' vs '{r.conflicting_value}' on {r.timestamp[:10]} (not applied)")
