from __future__ import annotations

import re
import time
from typing import Any, Dict, List

import requests
import streamlit as st

st.set_page_config(
    page_title="Texas DPS Virtual Assistant",
    page_icon="*",
    layout="centered",
    initial_sidebar_state="collapsed",
)

API_DEFAULT = "http://127.0.0.1:8000"

SUGGESTED_PROMPTS: List[Dict[str, str]] = [
    {"label": "Driver License", "prompt": "How do I apply for a Texas driver license?"},
    {"label": "State ID Card", "prompt": "What documents do I need for a Texas ID card?"},
    {"label": "Book Appointment", "prompt": "I want to book a DL appointment"},
    {"label": "Renew Online", "prompt": "Can I renew my driver license online?"},
    {"label": "Commercial DL", "prompt": "What are the requirements for a CDL?"},
    {"label": "FAQ", "prompt": "What are the most common DL questions?"},
]

SERVICE_LINKS: List[Dict[str, str]] = [
    {"title": "Schedule Appointment", "url": "https://www.dps.texas.gov/section/service/new-appointment-scheduling-system"},
    {"title": "Online Services", "url": "https://www.dps.texas.gov/section/driver-license/online-services"},
    {"title": "DL Requirements", "url": "https://www.dps.texas.gov/section/driver-license/requirements"},
    {"title": "ID Cards", "url": "https://www.dps.texas.gov/section/driver-license/how-apply-texas-identification-card"},
    {"title": "CDL Info", "url": "https://www.dps.texas.gov/section/commercial-driver-license"},
    {"title": "FAQ", "url": "https://www.dps.texas.gov/section/driver-license/how-can-we-help"},
]

_CSS = """
<style>
:root {
    --dps-navy: #002868;
    --dps-navy-dark: #001845;
    --dps-light: #f5f7fa;
    --radius: 1rem;
    --shadow-sm: 0 1px 3px rgba(0,0,0,.08);
    --shadow-md: 0 4px 12px rgba(0,0,0,.10);
}
html, body, [data-testid="stAppViewContainer"] {
    background: var(--dps-light) !important;
}
[data-testid="stSidebar"] {
    background: var(--dps-navy-dark) !important;
}
[data-testid="stSidebar"] * {
    color: #e0e0e0 !important;
}
[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea,
[data-testid="stSidebar"] select {
    background: rgba(255,255,255,.1) !important;
    border: 1px solid rgba(255,255,255,.2) !important;
    color: #fff !important;
}
header[data-testid="stHeader"] {
    background: transparent !important;
}
#MainMenu, footer, [data-testid="stToolbar"] { display: none !important; }

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
}
.dps-banner .subtitle {
    font-size: .82rem;
    opacity: .85;
    margin-top: 2px;
}

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

.source-card {
    background: #f0f4ff;
    border-left: 3px solid var(--dps-navy);
    border-radius: .4rem;
    padding: .5rem .8rem;
    margin-top: .45rem;
    font-size: .78rem;
    color: #333;
}
.source-card strong { color: var(--dps-navy); }

.workflow-card {
    background: linear-gradient(145deg, #ffffff 0%, #eef3fb 100%);
    border: 1px solid #d8e3f2;
    border-radius: .95rem;
    padding: .85rem 1rem;
    margin: .75rem 0 .55rem;
    box-shadow: var(--shadow-sm);
}
.workflow-card .eyebrow {
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #5b6f92;
    margin-bottom: .35rem;
    font-weight: 700;
}
.workflow-card .title {
    color: var(--dps-navy-dark);
    font-size: .98rem;
    font-weight: 700;
    margin-bottom: .25rem;
}
.workflow-card .meta {
    color: #43556f;
    font-size: .83rem;
    line-height: 1.45;
}
.workflow-actions-label {
    color: var(--dps-navy);
    font-size: .78rem;
    font-weight: 700;
    margin: .55rem 0 .35rem;
}

.status-shell {
    background: linear-gradient(145deg, #ffffff 0%, #eef4ff 100%);
    border: 1px solid #d5e0f2;
    border-radius: 1rem;
    padding: 1rem 1.1rem;
    margin: .4rem auto 1rem;
    max-width: 740px;
    box-shadow: var(--shadow-sm);
}
.status-shell.critical {
    border-color: #c94a4a;
    background: linear-gradient(145deg, #fff7f7 0%, #fff0f0 100%);
}
.status-shell.warning {
    border-color: #d59a1f;
    background: linear-gradient(145deg, #fffaf0 0%, #fff4dc 100%);
}
.status-shell.success {
    border-color: #2d8a57;
    background: linear-gradient(145deg, #f3fbf6 0%, #ebf8f0 100%);
}
.status-topline {
    display: flex;
    justify-content: space-between;
    gap: .75rem;
    align-items: baseline;
    flex-wrap: wrap;
}
.status-kicker {
    color: #5b6f92;
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .08em;
    font-weight: 700;
}
.status-headline {
    color: var(--dps-navy-dark);
    font-size: 1.05rem;
    font-weight: 700;
    margin-top: .2rem;
}
.status-chip {
    border-radius: 999px;
    padding: .25rem .65rem;
    font-size: .74rem;
    font-weight: 700;
    background: rgba(0, 40, 104, .08);
    color: var(--dps-navy);
}
.status-progress-track {
    width: 100%;
    height: 8px;
    border-radius: 999px;
    background: rgba(0, 24, 69, .10);
    overflow: hidden;
    margin: .8rem 0 .55rem;
}
.status-progress-fill {
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #0a56a8 0%, #2e89ff 100%);
}
.status-copy {
    color: #33435c;
    font-size: .86rem;
    line-height: 1.5;
}
.status-detail-list {
    margin-top: .65rem;
    display: grid;
    gap: .35rem;
}
.status-detail {
    color: #31425d;
    font-size: .82rem;
}

.handoff-shell {
    background: linear-gradient(145deg, #fff9f2 0%, #fff3e5 100%);
    border: 1px solid #ebb46a;
    border-radius: 1rem;
    padding: .95rem 1rem;
    margin: 0 auto 1rem;
    max-width: 740px;
    box-shadow: var(--shadow-sm);
}
.handoff-ticket {
    color: #9a5b12;
    font-size: .74rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .08em;
}
.handoff-title {
    color: #7a4300;
    font-size: 1rem;
    font-weight: 700;
    margin-top: .2rem;
}
.handoff-copy {
    color: #6a4a20;
    font-size: .84rem;
    line-height: 1.5;
    margin-top: .35rem;
}
.transcript-list {
    margin-top: .8rem;
    display: grid;
    gap: .45rem;
}
.transcript-line {
    background: rgba(255,255,255,.7);
    border-radius: .7rem;
    padding: .55rem .7rem;
    font-size: .8rem;
    color: #5f4b2d;
}
.transcript-line strong {
    color: #8a4d00;
}

.sidebar-card {
    background: rgba(255,255,255,.08);
    border: 1px solid rgba(255,255,255,.14);
    border-radius: .8rem;
    padding: .75rem .8rem;
    margin-bottom: .6rem;
}
.sidebar-card-title {
    font-size: .76rem;
    text-transform: uppercase;
    letter-spacing: .08em;
    font-weight: 700;
    color: #d8e4ff;
    margin-bottom: .35rem;
}
.sidebar-card-copy {
    font-size: .82rem;
    line-height: 1.45;
    color: #eef4ff;
}
.queue-item {
    background: rgba(255,255,255,.06);
    border: 1px solid rgba(255,255,255,.12);
    border-radius: .75rem;
    padding: .7rem .75rem;
    margin-bottom: .55rem;
}
.queue-ticket {
    font-size: .72rem;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #ffd796;
    font-weight: 700;
}
.queue-summary {
    font-size: .8rem;
    color: #f2f6ff;
    margin-top: .2rem;
}

.typing-dots span {
    display: inline-block;
    width: 7px;
    height: 7px;
    margin: 0 2px;
    background: var(--dps-navy);
    border-radius: 50%;
    animation: bounce .9s infinite;
}
.typing-dots span:nth-child(2) { animation-delay: .15s; }
.typing-dots span:nth-child(3) { animation-delay: .3s; }
@keyframes bounce {
    0%, 80%, 100% { transform: translateY(0); }
    40% { transform: translateY(-6px); }
}

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
    background: #eff3fa;
}

.dps-footer {
    text-align: center;
    font-size: .7rem;
    color: #999;
    padding: 1.5rem 0 .5rem;
}

[data-testid="stChatInput"] {
    max-width: 740px !important;
    margin: 0 auto !important;
}
[data-testid="stChatInput"] textarea {
    border-radius: 1.2rem !important;
    border: 1.5px solid #d0d5dd !important;
    padding: .8rem 1.2rem !important;
    box-shadow: var(--shadow-sm) !important;
    font-size: .92rem !important;
    color: #000 !important;
    -webkit-text-fill-color: #000 !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: #444 !important;
    opacity: 1 !important;
}
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
    padding: .2rem 0 !important;
    max-width: 740px;
    margin: 0 auto;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"],
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] * {
    color: #000 !important;
}

div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
    background: #fff !important;
    border: 1.5px solid #e0e4ea !important;
    border-radius: .8rem !important;
    padding: .65rem 1rem !important;
    font-size: .88rem !important;
    color: #333 !important;
    transition: all .18s ease !important;
    box-shadow: var(--shadow-sm) !important;
}
div[data-testid="stHorizontalBlock"] button[kind="secondary"]:hover {
    border-color: var(--dps-navy) !important;
    background: #eff3fa !important;
    transform: translateY(-1px) !important;
    box-shadow: var(--shadow-md) !important;
}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def _init_state() -> None:
    st.session_state.setdefault("session_id", "")
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("api_url", API_DEFAULT)
    st.session_state.setdefault("pending_prompt", None)
    st.session_state.setdefault("user_name", "")
    st.session_state.setdefault("rag_debug_query", "")
    st.session_state.setdefault("rag_hits", [])
    st.session_state.setdefault("session_snapshot", {})
    st.session_state.setdefault("handoff_queue", {"count": 0, "items": []})
    st.session_state.setdefault("handoff_operator", "Demo Agent")


def _queue_prompt(prompt: str) -> None:
    st.session_state["pending_prompt"] = prompt
    st.rerun()


def _normalize_service_label(service: str) -> str:
    labels = {
        "dl_appointment": "Driver License",
        "state_id": "State ID",
        "renewal": "Renewal",
    }
    return labels.get(service.strip().lower(), service)


def _friendly_slot_label(slot: str) -> str:
    raw = (slot or "").strip()
    if "|" not in raw:
        return raw
    service, when = [part.strip() for part in raw.split("|", 1)]
    return f"{_normalize_service_label(service)} • {when}"


def _parse_slot_actions(content: str) -> List[Dict[str, str]]:
    actions: List[Dict[str, str]] = []
    for line in (content or "").splitlines():
        match = re.match(r"\s*(?:\d+\.\s*)?\(([A-E])\)\s+(.+)$", line.strip(), re.IGNORECASE)
        if not match:
            continue
        option = match.group(1).upper()
        slot = match.group(2).strip()
        actions.append({"label": f"Pick {option}", "prompt": option.lower(), "detail": _friendly_slot_label(slot)})
    return actions


def _parse_service_actions(content: str) -> List[Dict[str, str]]:
    text = (content or "").lower()
    if "please choose:" not in text:
        return []
    if not all(token in text for token in ("dl_appointment", "state_id", "renewal")):
        return []
    return [
        {"label": "Driver License", "prompt": "dl_appointment", "detail": "Book a driver license appointment"},
        {"label": "State ID", "prompt": "state_id", "detail": "Book a Texas state ID appointment"},
        {"label": "Renewal", "prompt": "renewal", "detail": "Book a renewal appointment"},
    ]


def _parse_confirmation_actions(content: str) -> List[Dict[str, str]]:
    text = (content or "").lower()
    if "reply `yes`" not in text and "reply 'yes'" not in text and "reply yes" not in text:
        return []
    return [
        {"label": "Yes, confirm", "prompt": "yes", "detail": "Approve this change"},
        {"label": "No, keep current", "prompt": "no", "detail": "Decline and keep the current booking"},
    ]


def _booking_summary(content: str) -> Dict[str, str]:
    summary: Dict[str, str] = {}
    patterns = {
        "Booking ID": r"Booking ID:\s*([A-Z0-9-]+)",
        "Service": r"Service:\s*(.+)",
        "Slot": r"(?:New slot|Slot):\s*(.+)",
        "Email": r"Email:\s*(.+)",
    }
    for label, pattern in patterns.items():
        match = re.search(pattern, content or "", re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            summary[label] = _friendly_slot_label(value) if label == "Slot" else value
    return summary


def _render_workflow_summary(content: str, meta: Dict[str, Any]) -> None:
    summary = _booking_summary(content)
    if not summary:
        return

    title = "Booking Updated" if "New slot" in (content or "") else "Booking Summary"
    details = []
    for label in ("Booking ID", "Service", "Slot", "Email"):
        if label in summary:
            details.append(f"<strong>{label}:</strong> {summary[label]}")
    st.markdown(
        (
            '<div class="workflow-card">'
            '<div class="eyebrow">Workflow</div>'
            f'<div class="title">{title}</div>'
            f'<div class="meta">{"<br>".join(details)}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _quick_actions_for_message(content: str, meta: Dict[str, Any]) -> List[Dict[str, str]]:
    actions = _parse_slot_actions(content)
    if actions:
        return actions

    actions = _parse_confirmation_actions(content)
    if actions:
        return actions

    actions = _parse_service_actions(content)
    if actions:
        return actions

    return []


def _render_quick_actions(content: str, meta: Dict[str, Any], key_prefix: str) -> None:
    actions = _quick_actions_for_message(content, meta)
    if not actions:
        return

    st.markdown('<div class="workflow-actions-label">Quick Actions</div>', unsafe_allow_html=True)
    cols = st.columns(min(3, len(actions)))
    for idx, action in enumerate(actions):
        with cols[idx % len(cols)]:
            if st.button(action["label"], key=f"{key_prefix}_action_{idx}", use_container_width=True):
                _queue_prompt(action["prompt"])
            if action.get("detail"):
                st.caption(action["detail"])


def _call_chat(api_url: str, session_id: str, message: str) -> Dict[str, Any]:
    payload = {"session_id": session_id or None, "message": message}
    r = requests.post(f"{api_url}/chat", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def _call_retrieve(api_url: str, message: str) -> Dict[str, Any]:
    payload = {"session_id": None, "message": message}
    r = requests.post(f"{api_url}/retrieve", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def _fallback_lead(question: str) -> str:
    q = (question or "").strip().lower()
    if any(token in q for token in ("document", "documents", "what to bring", "carry", "bring")):
        return (
            "For a first-time Texas driver license or ID visit, you should bring the required application and proof "
            "documents DPS asks for, and review the official \"what to bring\" checklist before going to the office."
        )
    if any(token in q for token in ("book", "schedule", "appointment")):
        return "To book a DPS appointment, use the official appointment information page and then the scheduler site."
    if "renew" in q and "online" in q:
        return "Texas DPS does offer online renewal for eligible licenses, although eligibility depends on the applicant's situation."
    if "cdl" in q or "commercial" in q:
        return "CDL requirements depend on the license class and endorsements you need."
    if "state id" in q or "identification card" in q or "id card" in q:
        return "For a Texas ID card visit, DPS expects you to bring the required identity and residency documents for the office appointment."
    return "Here is the best answer I could assemble from the DPS knowledge base."


def _clean_retrieval_preview(text: str) -> str:
    cleaned = (text or "").replace("“", '"').replace("”", '"').replace("’", "'")
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    lines: List[str] = []
    for raw in cleaned.splitlines():
        line = raw.strip(" -\t")
        lower = line.lower()
        if not line:
            continue
        if lower.startswith(("##", "#", "q1.", "q2.", "q3.", "1)", "2)", "3)", "related services", "official links", "recommended wording")):
            continue
        if len(line) < 18:
            continue
        lines.append(line)
    return " ".join(lines)


def _answer_sentences_from_hits(hits: List[Dict[str, Any]], limit: int = 2) -> List[str]:
    sentences: List[str] = []
    seen: set[str] = set()
    for hit in hits[:3]:
        cleaned = _clean_retrieval_preview(hit.get("preview") or "")
        for piece in re.split(r"(?<=[.!?])\s+", cleaned):
            sentence = piece.strip()
            normalized = sentence.lower()
            if len(sentence) < 35:
                continue
            if normalized in seen or normalized.endswith("?"):
                continue
            if "must share both" in normalized:
                continue
            if normalized.startswith(("if a customer requests", "checklist pdf", "appointment scheduler", "appointment information page")):
                continue
            seen.add(normalized)
            sentences.append(sentence)
            if len(sentences) >= limit:
                return sentences
    return sentences


def _build_retrieval_fallback_answer(question: str, hits: List[Dict[str, Any]]) -> str:
    lead = _fallback_lead(question)
    supporting = _answer_sentences_from_hits(hits, limit=2)
    if not supporting:
        return lead

    merged = " ".join(supporting)
    if merged.lower() in lead.lower():
        return lead
    return f"{lead}\n\n{merged}"


def _retrieval_fallback_response(api_url: str, message: str) -> Dict[str, Any] | None:
    try:
        data = _call_retrieve(api_url, message=message)
    except Exception:
        return None

    hits = data.get("hits") or []
    if not hits:
        return None

    top = hits[0]
    preview = (top.get("preview") or "").strip()
    if not preview:
        return None

    similarity = float(top.get("similarity") or 0.0)
    sources = [
        {
            "title": hit.get("title") or hit.get("doc_id") or "Knowledge Base",
            "source_url": hit.get("source_url") or "",
            "doc_id": hit.get("doc_id") or "",
            "similarity": float(hit.get("similarity") or 0.0),
        }
        for hit in hits[:3]
    ]
    return {
        "answer": _build_retrieval_fallback_answer(message, hits),
        "meta": {
            "intent": "kb_query",
            "refusal": False,
            "best_similarity": similarity,
            "sources": sources,
            "timings_ms": {},
            "fallback_mode": "retrieve_only",
        },
    }

    title = top.get("title") or top.get("doc_id") or "Knowledge Base"
    similarity = float(top.get("similarity") or 0.0)
    answer = (
        "I hit a temporary issue with the live assistant, but I could still pull this from the knowledge base:\n\n"
        f"{preview}\n\n"
        "You can ask a follow-up question and I’ll keep trying through the main assistant."
    )
    return {
        "answer": answer,
        "meta": {
            "intent": "kb_query",
            "refusal": False,
            "best_similarity": similarity,
            "sources": [{"title": title, "source_url": "", "doc_id": top.get("doc_id") or "", "similarity": similarity}],
            "timings_ms": {},
            "fallback_mode": "retrieve_only",
        },
    }


def _clean_retrieval_preview(text: str) -> str:
    cleaned = (text or "").replace("“", '"').replace("”", '"').replace("’", "'")
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    lines: List[str] = []
    for raw in cleaned.splitlines():
        line = raw.strip(" -\t")
        lower = line.lower()
        if not line:
            continue
        if lower.startswith(("##", "#", "q1.", "q2.", "q3.", "1)", "2)", "3)", "related services", "official links", "recommended wording")):
            continue
        if len(line) < 18:
            continue
        lines.append(line)
    return " ".join(lines)


def _retrieval_fallback_response(api_url: str, message: str) -> Dict[str, Any] | None:
    try:
        data = _call_retrieve(api_url, message=message)
    except Exception:
        return None

    hits = data.get("hits") or []
    if not hits:
        return None

    top = hits[0]
    preview = (top.get("preview") or "").strip()
    if not preview:
        return None

    similarity = float(top.get("similarity") or 0.0)
    sources = [
        {
            "title": hit.get("title") or hit.get("doc_id") or "Knowledge Base",
            "source_url": hit.get("source_url") or "",
            "doc_id": hit.get("doc_id") or "",
            "similarity": float(hit.get("similarity") or 0.0),
        }
        for hit in hits[:3]
    ]
    return {
        "answer": _build_retrieval_fallback_answer(message, hits),
        "meta": {
            "intent": "kb_query",
            "refusal": False,
            "best_similarity": similarity,
            "sources": sources,
            "timings_ms": {},
            "fallback_mode": "retrieve_only",
        },
    }


def _call_history(api_url: str, session_id: str, limit: int = 50) -> Dict[str, Any]:
    r = requests.get(f"{api_url}/history/{session_id}", params={"limit": limit}, timeout=30)
    r.raise_for_status()
    return r.json()


def _call_session_snapshot(api_url: str, session_id: str) -> Dict[str, Any]:
    r = requests.get(f"{api_url}/sessions/{session_id}", timeout=20)
    r.raise_for_status()
    return r.json()


def _call_handoff_queue(api_url: str, limit: int = 8) -> Dict[str, Any]:
    r = requests.get(f"{api_url}/handoff/queue", params={"limit": limit}, timeout=20)
    r.raise_for_status()
    return r.json()


def _claim_handoff(api_url: str, session_id: str, assignee: str) -> Dict[str, Any]:
    r = requests.post(
        f"{api_url}/handoff/claim/{session_id}",
        json={"assignee": assignee},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def _resolve_handoff(api_url: str, session_id: str, assignee: str) -> Dict[str, Any]:
    r = requests.post(
        f"{api_url}/handoff/resolve/{session_id}",
        json={"assignee": assignee},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def _store_session_snapshot(snapshot: Dict[str, Any]) -> None:
    st.session_state["session_snapshot"] = snapshot or {}
    if snapshot and snapshot.get("name"):
        st.session_state["user_name"] = snapshot["name"]


def _clear_conversation_state() -> None:
    st.session_state["session_id"] = ""
    st.session_state["messages"] = []
    st.session_state["user_name"] = ""
    st.session_state["pending_prompt"] = None
    st.session_state["session_snapshot"] = {}


def _tone_class(tone: str) -> str:
    if tone in {"critical", "warning", "success"}:
        return tone
    return "info"


def _render_banner() -> None:
    st.markdown(
        """
        <div class="dps-banner">
            <div class="title">Texas DPS Virtual Assistant</div>
            <div class="subtitle">Driver License and ID Card Services</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_welcome() -> None:
    st.markdown(
        """
        <div class="welcome-hero">
            <h2>How can I help you today?</h2>
            <p>Ask about driver licenses, ID cards, appointments, renewals, and requirements.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    for idx, prompt in enumerate(SUGGESTED_PROMPTS):
        with cols[idx % 3]:
            if st.button(prompt["label"], key=f"sp_{idx}", use_container_width=True):
                st.session_state["pending_prompt"] = prompt["prompt"]
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("##### Popular DPS Links")
    link_html = '<div class="link-grid">'
    for item in SERVICE_LINKS:
        link_html += f'<a href="{item["url"]}" target="_blank" class="link-card">{item["title"]}</a>'
    link_html += "</div>"
    st.markdown(link_html, unsafe_allow_html=True)


def _render_session_status() -> None:
    snapshot = st.session_state.get("session_snapshot") or {}
    transaction = snapshot.get("transaction") or {}
    if not transaction:
        return

    details = transaction.get("details") or []
    details_html = "".join(f'<div class="status-detail">{detail}</div>' for detail in details[:5])
    progress = max(0, min(int(transaction.get("progress") or 0), 100))
    tone = _tone_class(transaction.get("status_tone", "info"))
    st.markdown(
        (
            f'<div class="status-shell {tone}">'
            '<div class="status-topline">'
            '<div>'
            '<div class="status-kicker">Live Session Status</div>'
            f'<div class="status-headline">{transaction.get("headline", "Conversation ready")}</div>'
            "</div>"
            f'<div class="status-chip">{transaction.get("flow_label", "Conversation")}</div>'
            "</div>"
            '<div class="status-progress-track">'
            f'<div class="status-progress-fill" style="width: {progress}%;"></div>'
            "</div>"
            f'<div class="status-copy">{transaction.get("next_step", "")}</div>'
            f'<div class="status-detail-list">{details_html}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    handoff = snapshot.get("handoff") or {}
    if not handoff:
        return

    transcript = handoff.get("recent_messages") or []
    transcript_html = "".join(
        (
            '<div class="transcript-line">'
            f"<strong>{item.get('role', 'message').title()}:</strong> {item.get('preview', '')}"
            "</div>"
        )
        for item in transcript
    )
    st.markdown(
        (
            '<div class="handoff-shell">'
            f'<div class="handoff-ticket">{handoff.get("ticket_id", "HND-READY")} • {handoff.get("status_label", handoff.get("status", "ready_for_agent").replace("_", " "))}</div>'
            f'<div class="handoff-title">{handoff.get("reason", "Human support recommended")}</div>'
            f'<div class="handoff-copy">{handoff.get("summary", "")}</div>'
            f'<div class="handoff-copy"><strong>Next step:</strong> {handoff.get("next_step", "")}</div>'
            f'<div class="transcript-list">{transcript_html}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )

    session_id = snapshot.get("session_id") or st.session_state.get("session_id")
    operator = st.session_state.get("handoff_operator", "Demo Agent")
    col1, col2 = st.columns(2)
    with col1:
        if handoff.get("status") == "recommended":
            if st.button("Claim Handoff", key="claim_handoff_btn", use_container_width=True):
                try:
                    data = _claim_handoff(st.session_state["api_url"], session_id, operator)
                    _store_session_snapshot(data.get("session", {}))
                    st.session_state["handoff_queue"] = _call_handoff_queue(st.session_state["api_url"])
                    st.rerun()
                except Exception as exc:
                    st.error(f"Claim failed: {exc}")
        else:
            st.caption(f"Claimed by: {handoff.get('assignee') or operator}")
    with col2:
        if handoff.get("status") in {"recommended", "claimed"}:
            if st.button("Resolve Handoff", key="resolve_handoff_btn", use_container_width=True):
                try:
                    data = _resolve_handoff(st.session_state["api_url"], session_id, operator)
                    _store_session_snapshot(data.get("session", {}))
                    st.session_state["handoff_queue"] = _call_handoff_queue(st.session_state["api_url"])
                    st.rerun()
                except Exception as exc:
                    st.error(f"Resolve failed: {exc}")


def _render_assistant_meta(meta: Dict[str, Any]) -> None:
    parts: List[str] = []
    if meta.get("intent"):
        parts.append(f"Intent: {meta['intent']}")
    if meta.get("best_similarity") is not None:
        parts.append(f"Confidence: {meta['best_similarity']:.2%}")
    timings = meta.get("timings_ms") or {}
    if timings:
        total_ms = sum(float(v or 0) for v in timings.values())
        parts.append(f"Latency: {int(total_ms)} ms")
    if parts:
        st.caption(" | ".join(parts))

    sources = meta.get("sources") or []
    if sources:
        with st.expander("Sources", expanded=False):
            for src in sources:
                title = src.get("title", "Source")
                url = src.get("source_url", "")
                sim = src.get("similarity", 0)
                link_part = f' - <a href="{url}" target="_blank">link</a>' if url else ""
                st.markdown(
                    f'<div class="source-card"><strong>{title}</strong>{link_part}'
                    f"<br>Similarity: {sim:.4f}</div>",
                    unsafe_allow_html=True,
                )


def _render_message(msg: Dict[str, Any], *, key_prefix: str = "") -> None:
    role = msg["role"]
    avatar = "🤖" if role == "assistant" else "👤"
    with st.chat_message(role, avatar=avatar):
        st.markdown(msg["content"])
        if role == "assistant":
            meta = msg.get("meta") or {}
            _render_workflow_summary(msg["content"], meta)
            _render_assistant_meta(meta)
            if key_prefix:
                _render_quick_actions(msg["content"], meta, key_prefix=key_prefix)


def _render_chat_history() -> None:
    messages = st.session_state["messages"]
    last_index = len(messages) - 1
    for idx, msg in enumerate(messages):
        key_prefix = f"history_{idx}" if idx == last_index and msg.get("role") == "assistant" else ""
        _render_message(msg, key_prefix=key_prefix)


def _history_to_messages(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    messages: List[Dict[str, Any]] = []
    for event in events:
        role = event.get("role")
        if role not in {"user", "assistant"}:
            continue
        item: Dict[str, Any] = {"role": role, "content": event.get("content", "")}
        if role == "assistant":
            item["meta"] = {
                "intent": event.get("intent"),
                "refusal": event.get("refusal"),
                "best_similarity": event.get("best_similarity"),
                "sources": event.get("sources", []),
                "timings_ms": event.get("timings_ms", {}),
            }
        messages.append(item)
    return messages


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### Settings")
        st.session_state["api_url"] = st.text_input("API Endpoint", value=st.session_state["api_url"])

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Health", use_container_width=True):
                try:
                    r = requests.get(f"{st.session_state['api_url']}/health", timeout=10)
                    r.raise_for_status()
                    st.success("API is reachable")
                except Exception as exc:
                    st.error(f"Health check failed: {exc}")
        with c2:
            if st.button("Reload History", use_container_width=True):
                session_id = st.session_state.get("session_id", "")
                if not session_id:
                    st.info("No active session yet.")
                else:
                    try:
                        data = _call_history(st.session_state["api_url"], session_id=session_id, limit=100)
                        events = data.get("events", [])
                        st.session_state["messages"] = _history_to_messages(events)
                        if session_id:
                            _store_session_snapshot(_call_session_snapshot(st.session_state["api_url"], session_id))
                        st.success(f"Loaded {len(events)} events")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"History error: {exc}")
        with c3:
            if st.button("Refresh Ops", use_container_width=True):
                try:
                    session_id = st.session_state.get("session_id", "")
                    if session_id:
                        _store_session_snapshot(_call_session_snapshot(st.session_state["api_url"], session_id))
                    st.session_state["handoff_queue"] = _call_handoff_queue(st.session_state["api_url"])
                    st.success("Session and handoff panels refreshed")
                except Exception as exc:
                    st.error(f"Refresh error: {exc}")

        st.divider()
        st.markdown("### Session")
        if st.session_state["session_id"]:
            st.code(st.session_state["session_id"], language=None)
        else:
            st.caption("No active session")

        if st.session_state.get("user_name"):
            st.markdown(f"**User:** {st.session_state['user_name']}")

        st.session_state["handoff_operator"] = st.text_input(
            "Operator Name",
            value=st.session_state.get("handoff_operator", "Demo Agent"),
        )

        snapshot = st.session_state.get("session_snapshot") or {}
        transaction = snapshot.get("transaction") or {}
        if transaction:
            st.markdown(
                (
                    '<div class="sidebar-card">'
                    '<div class="sidebar-card-title">Transaction Status</div>'
                    f'<div class="sidebar-card-copy"><strong>{transaction.get("headline", "Conversation ready")}</strong><br>'
                    f'{transaction.get("next_step", "")}</div>'
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
            st.caption(f"Progress: {int(transaction.get('progress') or 0)}%")
            if snapshot.get("selected_booking_id"):
                st.caption(f"Booking: {snapshot['selected_booking_id']}")
            if snapshot.get("pending_booking_email"):
                st.caption(f"Email: {snapshot['pending_booking_email']}")

        if st.button("New Conversation", use_container_width=True):
            _clear_conversation_state()
            st.rerun()

        st.divider()
        st.markdown("### Analytics")
        if st.button("Refresh Stats", use_container_width=True):
            try:
                r = requests.get(f"{st.session_state['api_url']}/stats", timeout=10)
                r.raise_for_status()
                st.session_state["_stats"] = r.json()
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
            st.metric("Handoffs", stats.get("handoffs_recommended", 0))
            st.metric("Claimed", stats.get("handoffs_claimed", 0))

        st.divider()
        st.markdown("### Handoff Queue")
        if st.button("Refresh Queue", use_container_width=True):
            try:
                st.session_state["handoff_queue"] = _call_handoff_queue(st.session_state["api_url"])
            except Exception as exc:
                st.error(f"Queue error: {exc}")

        handoff_queue = st.session_state.get("handoff_queue") or {"count": 0, "items": []}
        items = handoff_queue.get("items") or []
        if items:
            st.caption(f"{handoff_queue.get('count', len(items))} session(s) awaiting human follow-up")
            for item in items[:4]:
                st.markdown(
                    (
                        '<div class="queue-item">'
                        f'<div class="queue-ticket">{item.get("ticket_id", "HND")}</div>'
                        f'<div class="queue-summary"><strong>{item.get("flow_label", "Conversation")}</strong><br>'
                        f'{item.get("status_label", item.get("status", "recommended"))}<br>'
                        f'{item.get("summary", "")}</div>'
                        "</div>"
                    ),
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No handoff sessions captured yet.")

        st.divider()
        st.markdown("### Appointments")
        svc = st.selectbox("Service", ["", "dl_appointment", "state_id", "renewal"], label_visibility="collapsed")
        if st.button("View Open Slots", use_container_width=True):
            try:
                params = {"service_type": svc} if svc else {}
                r = requests.get(f"{st.session_state['api_url']}/appointments/slots", params=params, timeout=20)
                r.raise_for_status()
                slots = r.json().get("slots", [])
                if slots:
                    for slot in slots[:8]:
                        st.markdown(f"- `{slot}`")
                else:
                    st.info("No open slots found.")
            except Exception as exc:
                st.error(f"Slots error: {exc}")

        st.divider()
        st.markdown("### Knowledge Base")
        if st.button("Rebuild Index", use_container_width=True):
            with st.spinner("Ingesting KB..."):
                try:
                    r = requests.post(f"{st.session_state['api_url']}/ingest", timeout=300)
                    r.raise_for_status()
                    st.success("Index rebuilt")
                except Exception as exc:
                    st.error(f"Ingest error: {exc}")

        st.session_state["rag_debug_query"] = st.text_input(
            "RAG debug query",
            value=st.session_state["rag_debug_query"],
            placeholder="Test retrieval for a specific question",
        )
        if st.button("Run Retrieval Debug", use_container_width=True):
            query = st.session_state.get("rag_debug_query", "").strip()
            if not query:
                st.info("Enter a query first.")
            else:
                try:
                    data = _call_retrieve(st.session_state["api_url"], message=query)
                    st.session_state["rag_hits"] = data.get("hits", [])
                except Exception as exc:
                    st.error(f"Retrieve error: {exc}")

        rag_hits = st.session_state.get("rag_hits", [])
        if rag_hits:
            st.caption("Top retrieval hits")
            for idx, hit in enumerate(rag_hits[:5], start=1):
                title = hit.get("title") or hit.get("doc_id") or "Untitled"
                sim = float(hit.get("similarity") or 0.0)
                preview = (hit.get("preview") or "").strip()
                st.markdown(f"**{idx}. {title}** ({sim:.2%})")
                if preview:
                    st.caption(preview[:180] + ("..." if len(preview) > 180 else ""))

        st.divider()
        st.markdown(
            '<div class="dps-footer">Powered by Chroma RAG and LangGraph<br>Texas DPS - CivicFlow Demo</div>',
            unsafe_allow_html=True,
        )


def _handle_user_message(prompt: str) -> None:
    st.session_state["messages"].append({"role": "user", "content": prompt})

    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        typing_placeholder = st.empty()
        typing_placeholder.markdown(
            '<div class="typing-dots"><span></span><span></span><span></span></div>',
            unsafe_allow_html=True,
        )

        try:
            data = _call_chat(st.session_state["api_url"], st.session_state["session_id"], prompt)
        except Exception:
            typing_placeholder.empty()
            fallback = _retrieval_fallback_response(st.session_state["api_url"], prompt)
            if fallback:
                answer = fallback["answer"]
                meta = fallback["meta"]
                msg_placeholder = st.empty()
                revealed = ""
                words = answer.split(" ")
                for idx, word in enumerate(words):
                    revealed += word + " "
                    if idx % 4 == 0 or idx == len(words) - 1:
                        msg_placeholder.markdown(revealed)
                        time.sleep(0.02)
                msg_placeholder.markdown(answer)
                st.caption("Temporary fallback mode: answer assembled from retrieved DPS references.")
                _render_assistant_meta(meta)
                st.session_state["messages"].append({"role": "assistant", "content": answer, "meta": meta})
                return

            err = "I couldn't reach the assistant service right now. Please try again in a moment."
            st.error(err)
            st.session_state["messages"].append({"role": "assistant", "content": err, "meta": {}})
            return

        typing_placeholder.empty()

        st.session_state["session_id"] = data.get("session_id", st.session_state["session_id"])
        if data.get("name"):
            st.session_state["user_name"] = data["name"]
        if data.get("session"):
            _store_session_snapshot(data["session"])

        answer = data.get("answer", "")
        meta = {
            "intent": data.get("intent"),
            "refusal": data.get("refusal"),
            "best_similarity": data.get("best_similarity"),
            "sources": data.get("sources", []),
            "timings_ms": data.get("timings_ms", {}),
            "stage": data.get("stage"),
        }

        msg_placeholder = st.empty()
        revealed = ""
        words = answer.split(" ")
        for idx, word in enumerate(words):
            revealed += word + " "
            if idx % 4 == 0 or idx == len(words) - 1:
                msg_placeholder.markdown(revealed)
                time.sleep(0.02)
        msg_placeholder.markdown(answer)

        _render_workflow_summary(answer, meta)
        _render_assistant_meta(meta)
        _render_quick_actions(answer, meta, key_prefix=f"live_{len(st.session_state['messages'])}")
        st.session_state["messages"].append({"role": "assistant", "content": answer, "meta": meta})
        if (st.session_state.get("session_snapshot") or {}).get("handoff"):
            try:
                st.session_state["handoff_queue"] = _call_handoff_queue(st.session_state["api_url"])
            except Exception:
                pass


def main() -> None:
    _init_state()
    inject_css()
    _render_banner()
    _render_sidebar()
    _render_session_status()

    has_messages = len(st.session_state["messages"]) > 0
    if not has_messages:
        _render_welcome()

    pending = st.session_state.get("pending_prompt")
    if pending:
        st.session_state["pending_prompt"] = None
        _handle_user_message(pending)
        return

    if has_messages:
        _render_chat_history()

    prompt = st.chat_input("Ask about DL/ID services, appointments, renewals...")
    if prompt:
        _handle_user_message(prompt)


if __name__ == "__main__":
    main()
