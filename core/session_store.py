"""
core/session_store.py
─────────────────────
Session management backed by SQLAlchemy / SQLite.

The public API (`get_session`, `update_session`, `session_to_dict`) is
unchanged so existing callers (agent_graph, main) keep working.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from .database import SessionModel, get_db, init_db, _utcnow


# ── Thin dataclass facade (keeps agent_graph compatible) ─────────────────
@dataclass
class SessionState:
    session_id: str
    name: Optional[str] = None
    stage: str = "new"
    pending_intent: Optional[str] = None
    pending_booking_phone: Optional[str] = None
    pending_booking_email: Optional[str] = None
    pending_booking_service_type: Optional[str] = None
    goal: Optional[str] = None
    subgoal: Optional[str] = None
    active_flow: Optional[str] = None
    booking_stage: Optional[str] = None
    last_offered_slots: list[str] = field(default_factory=list)
    selected_slot: Optional[str] = None
    selected_booking_id: Optional[str] = None
    unresolved_question: Optional[str] = None
    confirmation_status: str = "not_requested"
    awaiting_confirmation: bool = False
    last_agent_action: Optional[str] = None
    fallback_reason: Optional[str] = None
    escalation_reason: Optional[str] = None
    handoff_recommended: bool = False
    auth_status: str = "unknown"
    created_ts: float = 0.0
    last_ts: float = 0.0


_JSON_FIELD_MAP = {
    "last_offered_slots": "last_offered_slots_json",
}


def _load_json_list(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in data if item]


def _prepare_session_updates(kwargs: dict[str, Any]) -> dict[str, Any]:
    prepared: dict[str, Any] = {}
    for key, value in kwargs.items():
        mapped = _JSON_FIELD_MAP.get(key, key)
        if key == "last_offered_slots":
            prepared[mapped] = json.dumps(value or [])
        else:
            prepared[mapped] = value
    return prepared


def _model_to_state(m: SessionModel) -> SessionState:
    return SessionState(
        session_id=m.id,
        name=m.name,
        stage=m.stage,
        pending_intent=m.pending_intent,
        pending_booking_phone=m.pending_booking_phone,
        pending_booking_email=m.pending_booking_email,
        pending_booking_service_type=m.pending_booking_service_type,
        goal=m.goal,
        subgoal=m.subgoal,
        active_flow=m.active_flow,
        booking_stage=m.booking_stage,
        last_offered_slots=_load_json_list(m.last_offered_slots_json),
        selected_slot=m.selected_slot,
        selected_booking_id=m.selected_booking_id,
        unresolved_question=m.unresolved_question,
        confirmation_status=m.confirmation_status or "not_requested",
        awaiting_confirmation=bool(m.awaiting_confirmation),
        last_agent_action=m.last_agent_action,
        fallback_reason=m.fallback_reason,
        escalation_reason=m.escalation_reason,
        handoff_recommended=bool(m.handoff_recommended),
        auth_status=m.auth_status or "unknown",
        created_ts=m.created_at.timestamp() if m.created_at else 0.0,
        last_ts=m.updated_at.timestamp() if m.updated_at else 0.0,
    )


# ── Public API ───────────────────────────────────────────────────────────

def get_session(session_id: str) -> SessionState:
    init_db()
    with get_db() as db:
        m = db.query(SessionModel).filter_by(id=session_id).first()
        if not m:
            m = SessionModel(id=session_id)
            db.add(m)
            db.commit()
            db.refresh(m)
        else:
            m.updated_at = _utcnow()
            db.commit()
        return _model_to_state(m)


def update_session(session_id: str, **kwargs) -> SessionState:
    init_db()
    with get_db() as db:
        m = db.query(SessionModel).filter_by(id=session_id).first()
        if not m:
            m = SessionModel(id=session_id)
            db.add(m)
            db.flush()
        for k, v in _prepare_session_updates(kwargs).items():
            if hasattr(m, k):
                setattr(m, k, v)
        m.updated_at = _utcnow()
        db.commit()
        db.refresh(m)
        return _model_to_state(m)


def session_to_dict(s: SessionState) -> dict:
    return {
        "session_id": s.session_id,
        "name": s.name,
        "stage": s.stage,
        "pending_intent": s.pending_intent,
        "pending_booking_phone": s.pending_booking_phone,
        "pending_booking_email": s.pending_booking_email,
        "pending_booking_service_type": s.pending_booking_service_type,
        "goal": s.goal,
        "subgoal": s.subgoal,
        "active_flow": s.active_flow,
        "booking_stage": s.booking_stage,
        "last_offered_slots": s.last_offered_slots,
        "selected_slot": s.selected_slot,
        "selected_booking_id": s.selected_booking_id,
        "unresolved_question": s.unresolved_question,
        "confirmation_status": s.confirmation_status,
        "awaiting_confirmation": s.awaiting_confirmation,
        "last_agent_action": s.last_agent_action,
        "fallback_reason": s.fallback_reason,
        "escalation_reason": s.escalation_reason,
        "handoff_recommended": s.handoff_recommended,
        "auth_status": s.auth_status,
        "created_ts": s.created_ts,
        "last_ts": s.last_ts,
    }
