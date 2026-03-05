"""
CivicFlow – Texas DPS Virtual Assistant
GPT / Gemini-style chat dashboard built with Streamlit.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

import requests
import streamlit as st

# ── Page config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Texas DPS Virtual Assistant",
    page_icon="⭐",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Constants ────────────────────────────────────────────────────────────
API_DEFAULT = "http://127.0.0.1:8000"

SUGGESTED_PROMPTS: List[Dict[str, str]] = [
    {"icon": "🪪", "label": "Driver License", "prompt": "How do I apply for a Texas driver license?"},
    {"icon": "🆔", "label": "State ID Card", "prompt": "What documents do I need for a Texas ID card?"},
    {"icon": "📅", "label": "Book Appointment", "prompt": "I want to book a DL appointment"},
    {"icon": "🔄", "label": "Renew Online", "prompt": "Can I renew my driver license online?"},
    {"icon": "🚛", "label": "Commercial DL", "prompt": "What are the requirements for a CDL?"},
    {"icon": "❓", "label": "FAQ", "prompt": "What are the most common DL questions?"},
]

SERVICE_LINKS: List[Dict[str, str]] = [
    {"title": "Schedule Appointment", "url": "https://www.dps.texas.gov/section/service/new-appointment-scheduling-system"},
    {"title": "Online Services", "url": "https://www.dps.texas.gov/section/driver-license/online-services"},
    {"title": "DL Requirements", "url": "https://www.dps.texas.gov/section/driver-license/requirements"},
    {"title": "ID Cards", "url": "https://www.dps.texas.gov/section/driver-license/how-apply-texas-identification-card"},
    {"title": "CDL Info", "url": "https://www.dps.texas.gov/section/commercial-driver-license"},
    {"title": "FAQ", "url": "https://www.dps.texas.gov/section/driver-license/how-can-we-help"},
]


# ── Inject CSS ───────────────────────────────────────────────────────────
def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


_CSS = """
<style>
/* ── Root variables ──────────────────────────────────────────────── */
:root {
    --dps-navy:      #002868;
    --dps-navy-dark: #001845;
    --dps-gold:      #BF9B30;
    --dps-light:     #F5F7FA;
    --bubble-user:   #002868;
    --bubble-bot:    #FFFFFF;
    --text-user:     #FFFFFF;
    --text-bot:      #1E1E1E;
    --radius:        1rem;
    --shadow-sm:     0 1px 3px rgba(0,0,0,.08);
    --shadow-md:     0 4px 12px rgba(0,0,0,.10);
}

/* ── Global polish ───────────────────────────────────────────────── */
html, body, [data-testid="stAppViewContainer"] {
    background: var(--dps-light) !important;
}
[data-testid="stSidebar"] {
    background: var(--dps-navy-dark) !important;
}
[data-testid="stSidebar"] * {
    color: #E0E0E0 !important;
}
[data-testid="stSidebar"] input {
    background: rgba(255,255,255,.1) !important;
    border: 1px solid rgba(255,255,255,.2) !important;
    color: #fff !important;
}
header[data-testid="stHeader"] {
    background: transparent !important;
}

/* ── Top banner ──────────────────────────────────────────────────── */
.dps-banner {
    background: linear-gradient(135deg, var(--dps-navy) 0%, var(--dps-navy-dark) 100%);
    color: #fff;
    padding: 1.1rem 1.6rem;
    border-radius: var(--radius);
    text-align: center;
    margin-bottom: 1.2rem;
    box-shadow: var(--shadow-md);
}
.dps-banner .title {
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: .02em;
}
.dps-banner .subtitle {
    font-size: .82rem;
    opacity: .85;
    margin-top: 2px;
}

/* ── Welcome hero ────────────────────────────────────────────────── */
.welcome-hero {
    text-align: center;
    padding: 2.5rem 1rem 1rem;
}
.welcome-hero h2 {
    font-size: 1.6rem;
    color: var(--dps-navy);
    margin-bottom: .3rem;
}
.welcome-hero p {
    color: #555;
    font-size: .95rem;
    max-width: 520px;
    margin: 0 auto;
}

/* ── Source card ──────────────────────────────────────────────────── */
.source-card {
    background: #F0F4FF;
    border-left: 3px solid var(--dps-navy);
    border-radius: .4rem;
    padding: .5rem .8rem;
    margin-top: .45rem;
    font-size: .78rem;
    color: #333;
}
.source-card strong { color: var(--dps-navy); }

/* ── Meta caption ────────────────────────────────────────────────── */
.meta-caption {
    font-size: .72rem;
    color: #888;
    margin-top: .3rem;
    padding-left: 2px;
}

/* ── Typing dots ─────────────────────────────────────────────────── */
.typing-dots span {
    display: inline-block;
    width: 7px; height: 7px;
    margin: 0 2px;
    background: var(--dps-navy);
    border-radius: 50%;
    animation: bounce .9s infinite;
}
.typing-dots span:nth-child(2) { animation-delay: .15s; }
.typing-dots span:nth-child(3) { animation-delay: .3s; }
@keyframes bounce {
    0%, 80%, 100% { transform: translateY(0); }
    40%           { transform: translateY(-6px); }
}

/* ── Quick-link cards ────────────────────────────────────────────── */
.link-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: .55rem;
    margin-top: .8rem;
}
.link-card {
    background: #fff;
    border: 1px solid #e0e4ea;
    border-radius: .6rem;
    padding: .65rem .85rem;
    font-size: .82rem;
    font-weight: 600;
    color: var(--dps-navy);
    text-decoration: none !important;
    transition: all .15s;
    box-shadow: var(--shadow-sm);
}
.link-card:hover {
    border-color: var(--dps-navy);
    background: #EFF3FA;
}

/* ── Footer ──────────────────────────────────────────────────────── */
.dps-footer {
    text-align: center;
    font-size: .7rem;
    color: #999;
    padding: 1.5rem 0 .5rem;
}

/* ── Hide default Streamlit chrome ───────────────────────────────── */
#MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }

/* ── Chat input area ─────────────────────────────────────────────── */
[data-testid="stChatInput"] {
    max-width: 740px !important;
    margin: 0 auto !important;
}
[data-testid="stChatInput"] textarea {
    border-radius: 1.2rem !important;
    border: 1.5px solid #D0D5DD !important;
    padding: .8rem 1.2rem !important;
    box-shadow: var(--shadow-sm) !important;
    font-size: .92rem !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: var(--dps-navy) !important;
    box-shadow: 0 0 0 2px rgba(0,40,104,.15) !important;
}

/* ── Streamlit native chat messages overrides ────────────────────── */
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: .2rem 0 !important;
    max-width: 740px;
    margin: 0 auto;
}

/* ── Suggestion-pill buttons ─────────────────────────────────────── */
div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
    background: #fff !important;
    border: 1.5px solid #E0E4EA !important;
    border-radius: .8rem !important;
    padding: .65rem 1rem !important;
    font-size: .88rem !important;
    color: #333 !important;
    transition: all .18s ease !important;
    box-shadow: var(--shadow-sm) !important;
}
div[data-testid="stHorizontalBlock"] button[kind="secondary"]:hover {
    border-color: var(--dps-navy) !important;
    background: #EFF3FA !important;
    transform: translateY(-1px) !important;
    box-shadow: var(--shadow-md) !important;
}
</style>
"""


# ── Session helpers ──────────────────────────────────────────────────────
def _init_state() -> None:
    st.session_state.setdefault("session_id", "")
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("api_url", API_DEFAULT)
    st.session_state.setdefault("pending_prompt", None)
    st.session_state.setdefault("user_name", "")


# ── API call ─────────────────────────────────────────────────────────────
def _call_chat(api_url: str, session_id: str, message: str) -> Dict[str, Any]:
    payload = {"session_id": session_id or None, "message": message}
    r = requests.post(f"{api_url}/chat", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


# ── Render helpers ───────────────────────────────────────────────────────
def _render_banner() -> None:
    st.markdown(
        """
        <div class="dps-banner">
            <div class="title">Texas DPS Virtual Assistant</div>
            <div class="subtitle">Driver License &amp; ID Card Services</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_welcome() -> None:
    st.markdown(
        """
        <div class="welcome-hero">
            <h2>How can I help you today?</h2>
            <p>I'm your Texas DPS virtual assistant.  Ask me about driver licenses,
            ID cards, appointments, renewals, and more.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Suggested-prompt pills (2 rows × 3 columns)
    cols = st.columns(3)
    for idx, sp in enumerate(SUGGESTED_PROMPTS):
        col = cols[idx % 3]
        with col:
            if st.button(
                f"{sp['icon']}  {sp['label']}",
                key=f"sp_{idx}",
                use_container_width=True,
            ):
                st.session_state["pending_prompt"] = sp["prompt"]
                st.rerun()

    # Quick-link section
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("##### 🔗 Popular DPS Links")
    link_html = '<div class="link-grid">'
    for lk in SERVICE_LINKS:
        link_html += f'<a href="{lk["url"]}" target="_blank" class="link-card">{lk["title"]}</a>'
    link_html += "</div>"
    st.markdown(link_html, unsafe_allow_html=True)


def _render_message(msg: Dict[str, Any]) -> None:
    """Render a single chat message using Streamlit's native chat_message."""
    role = msg["role"]
    with st.chat_message(role, avatar="⭐" if role == "assistant" else "👤"):
        st.markdown(msg["content"])
        meta = msg.get("meta") or {}
        if role == "assistant" and meta:
            parts: List[str] = []
            if meta.get("intent"):
                parts.append(f"Intent: {meta['intent']}")
            if meta.get("best_similarity") is not None:
                parts.append(f"Confidence: {meta['best_similarity']:.2%}")
            if parts:
                st.caption(" · ".join(parts))

            sources = meta.get("sources") or []
            if sources:
                with st.expander("📚 Sources", expanded=False):
                    for src in sources:
                        title = src.get("title", "Source")
                        url = src.get("source_url", "")
                        sim = src.get("similarity", 0)
                        link_part = f' — <a href="{url}" target="_blank">link</a>' if url else ""
                        st.markdown(
                            f'<div class="source-card"><strong>{title}</strong>{link_part}'
                            f"<br>Similarity: {sim:.4f}</div>",
                            unsafe_allow_html=True,
                        )


def _render_chat_history() -> None:
    for msg in st.session_state["messages"]:
        _render_message(msg)


# ── Sidebar ──────────────────────────────────────────────────────────────
def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### ⚙️ Settings")
        st.session_state["api_url"] = st.text_input(
            "API Endpoint",
            value=st.session_state["api_url"],
        )

        st.divider()
        st.markdown("### 💬 Session")
        if st.session_state["session_id"]:
            st.code(st.session_state["session_id"], language=None)
        else:
            st.caption("No active session")

        if st.session_state.get("user_name"):
            st.markdown(f"**User:** {st.session_state['user_name']}")

        if st.button("🗑️  New Conversation", use_container_width=True):
            st.session_state["session_id"] = ""
            st.session_state["messages"] = []
            st.session_state["user_name"] = ""
            st.session_state["pending_prompt"] = None
            st.rerun()

        st.divider()
        st.markdown("### � Analytics")
        if st.button("Refresh Stats", use_container_width=True):
            try:
                r = requests.get(f"{st.session_state['api_url']}/stats", timeout=10)
                r.raise_for_status()
                data = r.json()
                st.session_state["_stats"] = data
            except Exception as exc:
                st.error(f"Stats error: {exc}")
        stats = st.session_state.get("_stats")
        if stats:
            c1, c2 = st.columns(2)
            c1.metric("Sessions", stats.get("total_sessions", 0))
            c2.metric("Messages", stats.get("total_messages", 0))
            c3, c4 = st.columns(2)
            c3.metric("Bookings", stats.get("active_bookings", 0))
            c4.metric("Cancelled", stats.get("cancelled_bookings", 0))

        st.divider()
        st.markdown("### 📅 Appointments")
        svc = st.selectbox("Service", ["", "dl_appointment", "state_id", "renewal"], label_visibility="collapsed")
        if st.button("View Open Slots", use_container_width=True):
            try:
                params = {"service_type": svc} if svc else {}
                r = requests.get(f"{st.session_state['api_url']}/appointments/slots", params=params, timeout=20)
                r.raise_for_status()
                slots = r.json().get("slots", [])
                if slots:
                    for s in slots[:6]:
                        st.markdown(f"- `{s}`")
                else:
                    st.info("No open slots found.")
            except Exception as exc:
                st.error(f"Error: {exc}")

        st.divider()
        st.markdown("### 📖 Knowledge Base")
        if st.button("Rebuild Index", use_container_width=True):
            with st.spinner("Ingesting…"):
                try:
                    r = requests.post(f"{st.session_state['api_url']}/ingest", timeout=300)
                    r.raise_for_status()
                    st.success("Index rebuilt ✓")
                except Exception as exc:
                    st.error(f"Error: {exc}")

        st.divider()
        st.markdown(
            '<div class="dps-footer">'
            "Powered by SQLite · SQLAlchemy<br>"
            "© 2026 Texas DPS – CivicFlow Demo"
            "</div>",
            unsafe_allow_html=True,
        )


# ── Process a user message ──────────────────────────────────────────────
def _handle_user_message(prompt: str) -> None:
    """Send the user message to the API and append bot reply."""
    st.session_state["messages"].append({"role": "user", "content": prompt})

    # Show the user bubble instantly
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    # Bot reply
    with st.chat_message("assistant", avatar="⭐"):
        # Typing indicator
        typing_placeholder = st.empty()
        typing_placeholder.markdown(
            '<div class="typing-dots"><span></span><span></span><span></span></div>',
            unsafe_allow_html=True,
        )

        try:
            data = _call_chat(st.session_state["api_url"], st.session_state["session_id"], prompt)
        except Exception as exc:
            typing_placeholder.empty()
            err = f"⚠️ Could not reach the API — `{exc}`"
            st.error(err)
            st.session_state["messages"].append({"role": "assistant", "content": err, "meta": {}})
            return

        typing_placeholder.empty()

        # Capture session info
        st.session_state["session_id"] = data.get("session_id", st.session_state["session_id"])
        if data.get("name"):
            st.session_state["user_name"] = data["name"]

        answer = data.get("answer", "")
        meta = {
            "intent": data.get("intent"),
            "refusal": data.get("refusal"),
            "best_similarity": data.get("best_similarity"),
            "sources": data.get("sources", []),
        }

        # Simulate incremental word reveal (Gemini-style)
        msg_placeholder = st.empty()
        revealed = ""
        words = answer.split(" ")
        for i, word in enumerate(words):
            revealed += word + " "
            if i % 4 == 0 or i == len(words) - 1:
                msg_placeholder.markdown(revealed)
                time.sleep(0.02)
        msg_placeholder.markdown(answer)

        # Meta caption
        parts: List[str] = []
        if meta.get("intent"):
            parts.append(f"Intent: {meta['intent']}")
        if meta.get("best_similarity") is not None:
            parts.append(f"Confidence: {meta['best_similarity']:.2%}")
        if parts:
            st.caption(" · ".join(parts))

        # Sources
        sources = meta.get("sources") or []
        if sources:
            with st.expander("📚 Sources", expanded=False):
                for src in sources:
                    title = src.get("title", "Source")
                    url = src.get("source_url", "")
                    sim = src.get("similarity", 0)
                    link_part = f' — <a href="{url}" target="_blank">link</a>' if url else ""
                    st.markdown(
                        f'<div class="source-card"><strong>{title}</strong>{link_part}'
                        f"<br>Similarity: {sim:.4f}</div>",
                        unsafe_allow_html=True,
                    )

        st.session_state["messages"].append({"role": "assistant", "content": answer, "meta": meta})


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════
def main() -> None:
    _init_state()
    inject_css()
    _render_banner()
    _render_sidebar()

    has_messages = len(st.session_state["messages"]) > 0

    # If no conversation yet → show welcome hero + suggestion pills
    if not has_messages:
        _render_welcome()

    # If a suggestion pill was clicked, treat it as user input
    pending = st.session_state.get("pending_prompt")
    if pending:
        st.session_state["pending_prompt"] = None
        _handle_user_message(pending)
        return

    # Render existing chat history
    if has_messages:
        _render_chat_history()

    # Chat input
    prompt = st.chat_input("Ask about DL/ID services, appointments, renewals…")
    if prompt:
        _handle_user_message(prompt)


if __name__ == "__main__":
    main()
