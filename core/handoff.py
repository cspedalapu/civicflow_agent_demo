from __future__ import annotations

from typing import Any, Dict, Optional

from .database import _utcnow
from .session_store import get_session, session_to_dict, update_session


def _ticket_id_for_session(session_id: str) -> str:
    compact = "".join(ch for ch in session_id.upper() if ch.isalnum())
    return f"HND-{compact[-8:] or 'DEMO0001'}"


def ensure_handoff(session_id: str, *, reason: Optional[str] = None) -> Dict[str, Any]:
    session = get_session(session_id)
    updates: Dict[str, Any] = {
        "handoff_recommended": True,
        "handoff_ticket_id": session.handoff_ticket_id or _ticket_id_for_session(session_id),
        "handoff_status": "recommended",
        "handoff_resolved_at": None,
    }
    if reason:
        updates["escalation_reason"] = reason
    if session.handoff_status == "resolved":
        updates["handoff_assignee"] = None
        updates["handoff_claimed_at"] = None
    return session_to_dict(update_session(session_id, **updates))


def claim_handoff(session_id: str, assignee: str) -> Dict[str, Any]:
    session = get_session(session_id)
    if not session.handoff_recommended:
        raise ValueError("No active handoff is available for this session.")

    assignee = (assignee or "").strip() or "Demo Agent"
    updated = update_session(
        session_id,
        handoff_ticket_id=session.handoff_ticket_id or _ticket_id_for_session(session_id),
        handoff_status="claimed",
        handoff_assignee=assignee,
        handoff_claimed_at=_utcnow(),
        handoff_resolved_at=None,
    )
    return session_to_dict(updated)


def resolve_handoff(session_id: str, assignee: str = "") -> Dict[str, Any]:
    session = get_session(session_id)
    if not session.handoff_recommended:
        raise ValueError("No active handoff is available for this session.")

    chosen_assignee = (assignee or session.handoff_assignee or "Demo Agent").strip()
    updated = update_session(
        session_id,
        handoff_ticket_id=session.handoff_ticket_id or _ticket_id_for_session(session_id),
        handoff_status="resolved",
        handoff_assignee=chosen_assignee,
        handoff_resolved_at=_utcnow(),
        handoff_recommended=False,
        escalation_reason=None,
    )
    return session_to_dict(updated)
