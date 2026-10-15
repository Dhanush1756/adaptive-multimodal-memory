"""Streamlit demo (brief sections 47 and 63).

    streamlit run app/streamlit_app.py

Sidebar: model status, memory statistics, reset. Main: add a memory (text + optional image),
see the extracted claim / detections / memory decision, then ask questions and inspect evidence.
"""
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402

from src.agent.reasoning import MemoryAgent, build_components  # noqa: E402
from src.config import load_config, resolve_path  # noqa: E402
from src.memory.state_tracker import timeline  # noqa: E402

st.set_page_config(page_title="Adaptive Evidence-Grounded Memory", layout="wide")


def get_agent(light: bool) -> MemoryAgent:
    """One mutable agent and private disk namespace per Streamlit browser session.

    The configured database names the storage root; the unscoped database is never
    opened/reset by this demo. Reruns and model-mode changes reuse the same memory.
    """
    if "memory_agent" not in st.session_state:
        cfg = load_config()
        namespace = uuid4().hex
        configured_db = cfg["paths"]["db_path"]
        if configured_db == ":memory:":
            db_path = configured_db
        else:
            base = Path(resolve_path(configured_db))
            db_path = str(base.parent / f"{base.stem}_sessions" / namespace / base.name)
        image_dir = Path(resolve_path(cfg["paths"]["image_dir"])) / "sessions" / namespace
        st.session_state["memory_agent"] = MemoryAgent(
            cfg, db_path=db_path, image_dir=str(image_dir), light=light)
    agent = st.session_state["memory_agent"]
    if agent.light != light:
        components = build_components(agent.cfg, light=light)
        agent.comp = components
        agent.hybrid.embedder = components.embedder
        agent.light = light
    return agent


def timeline_rows(agent: MemoryAgent, selected_entity_id: str | None = None):
    """Return each stored identity's history without category-level ambiguity.

    Explicit identities go through the public agent API with their entity reference.
    Legacy rows without ``entity_ref`` use their already-persisted entity ID, which
    avoids inventing a new identity when more than one old row shares a category.
    """
    rows = []
    for entity in agent.store.entities():
        if selected_entity_id and entity["entity_id"] != selected_entity_id:
            continue
        entity_ref = entity.get("entity_ref") or None
        if entity_ref:
            history = agent.timeline_for(entity["entity"], entity_ref=entity_ref)
        else:
            history = timeline(agent.store, entity["entity_id"], "color")
        rows.extend(history)
    return rows


with st.sidebar:
    st.header("Memory")
    light = st.toggle("Light mode (no model downloads)", value=True)
    agent = get_agent(light)
    st.caption("Memory belongs to this browser session. A new browser session starts a separate memory.")
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
    up = st.file_uploader("Photo (optional)", type=["jpg", "jpeg", "png"], key="memory_image")
    when = st.date_input("Date", value=datetime.now().date())
    sid = st.text_input("Session id (optional)")
    if st.button("Store", type="primary"):
        if not text and up is None:
            st.warning("Enter text or upload an image.")
        else:
            image = None
            image_error = ""
            if up is not None:
                from PIL import Image
                try:
                    image = Image.open(up).convert("RGB")
                except Exception as exc:
                    image_error = f"The uploaded image could not be read ({exc.__class__.__name__}). Text will still be stored."
            st.session_state["last"] = agent.remember(
                text, image, datetime.combine(when, datetime.min.time()).replace(hour=10), sid or None)
            if image_error:
                st.session_state["last"].notes.append(image_error)
    res = st.session_state.get("last")
    if res is not None:
        d = res.decision
        st.markdown(f"**Memory action: `{d.action.value}`** ({res.session_id})")
        st.write(d.reason)
        st.json({"claim": res.claim, "image": res.image, "decision": d.to_dict()}, expanded=False)
        for n in res.notes:
            if "warning" in n.lower():
                st.warning(n)
            else:
                st.caption(n)

# --------------------------------------------------------------------- query
with right:
    st.subheader("2. Ask")
    q = st.text_input("Question", placeholder="What color is my car now?")
    ask_up = st.file_uploader(
        "Image to ask about (optional)", type=["jpg", "jpeg", "png"], key="ask_image",
        help="The image is stored as dated evidence. In Light mode it cannot rewrite a state without detector verification.",
    )
    ask_when = st.date_input("Image date", value=datetime.now().date(), key="ask_image_date")
    ans = None
    if st.button("Ask"):
        if not q and ask_up is None:
            st.warning("Enter a question or upload an image.")
        else:
            if ask_up is not None:
                from PIL import Image
                try:
                    ask_image = Image.open(ask_up).convert("RGB")
                except Exception as exc:
                    st.session_state.pop("last_ask_image", None)
                    st.warning(f"The uploaded image could not be read ({exc.__class__.__name__}).")
                else:
                    st.session_state["last_ask_image"] = agent.remember(
                        "", ask_image,
                        datetime.combine(ask_when, datetime.min.time()).replace(hour=10),
                    )
            else:
                st.session_state.pop("last_ask_image", None)
            if q:
                ans = agent.ask(q)

    ask_ingest = st.session_state.get("last_ask_image")
    if ask_ingest is not None:
        decision = ask_ingest.decision
        st.markdown(f"**Image memory action: `{decision.action.value}`** ({ask_ingest.session_id})")
        if "warning" in decision.reason.lower() or decision.action.value in {"CONTRADICTORY", "IGNORE"}:
            st.warning(decision.reason)
        else:
            st.info(decision.reason)
        st.json({"image": ask_ingest.image, "decision": decision.to_dict()}, expanded=False)
        for note in ask_ingest.notes:
            if "warning" in note.lower():
                st.warning(note)
            else:
                st.caption(note)

    if ans is not None:
        st.markdown(f"### {ans.text}")
        st.caption(
            f"intent: {ans.intent} · status: {ans.status} · "
            f"confidence: {ans.confidence:.0%} · found: {ans.found}"
        )
        if ans.evidence:
            st.markdown("**Evidence**")
            for it in ans.evidence:
                if it["modality"] == "text":
                    st.write(f"- [{it['role']}] text ({it.get('session_id', '')}, {str(it.get('timestamp', ''))[:10]}): "
                             f"“{it['text']}”")
                else:
                    association = it.get("association_status", "unknown")
                    support = "supporting" if it.get("supports_state") else "non-supporting"
                    st.write(
                        f"- [{it['role']}] image {it['image_id']} "
                        f"({it.get('session_id', '')}, {str(it.get('timestamp', ''))[:10]}; "
                        f"{association}, {support}) looks **{it.get('visual_value')}**"
                    )
                    p = it.get("image_path")
                    if p and Path(p).exists():
                        st.image(p, width=220)
        with st.expander("Grounded prompt (what an LLM would see)"):
            st.code(ans.prompt or "(not found)")

# ------------------------------------------------------------------ timeline
st.subheader("3. Timeline")
entities = agent.store.entities()
selected_entity_id = None
if entities:
    by_id = {entity["entity_id"]: entity for entity in entities}
    selected = st.selectbox(
        "Timeline entity",
        ["all"] + list(by_id),
        format_func=lambda entity_id: (
            "All identities" if entity_id == "all" else
            f"{by_id[entity_id]['entity_ref'] or by_id[entity_id]['entity']} ({entity_id})"
        ),
    )
    selected_entity_id = None if selected == "all" else selected
rows = timeline_rows(agent, selected_entity_id)
if not rows:
    st.info("Nothing stored yet.")
else:
    for r in rows:
        badge = "🟢 CURRENT" if r.status.value == "CURRENT" else "⚪ HISTORICAL"
        imgs = ", ".join(v.image_id for v in r.visual_evidence) or "no image"
        identity = f" · {r.entity_ref}" if r.entity_ref else ""
        st.write(f"**{r.entity_id}**{identity} · {r.timestamp[:10]} · **{r.value}** · {badge} · "
                 f"{r.memory_id} (prev: {r.previous_memory_id or '-'}) · {imgs} · conf {r.confidence:.2f}")
conflicts = [r for r in agent.store.all() if r.status.value == "CONTRADICTORY"]
for r in conflicts:
    st.warning(f"Conflict {r.memory_id}: '{r.value}' vs '{r.conflicting_value}' on {r.timestamp[:10]} (not applied)")
