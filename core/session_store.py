"""
core/session_store.py
─────────────────────
Session management backed by SQLAlchemy / SQLite.

The public API (`get_session`, `update_session`, `session_to_dict`) is
unchanged so existing callers (agent_graph, main) keep working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .database import SessionModel, get_db, _utcnow


# ── Thin dataclass facade (keeps agent_graph compatible) ─────────────────
@dataclass
class SessionState:
    session_id: str
    name: Optional[str] = None
    stage: str = "new"
    pending_intent: Optional[str] = None
    pending_booking_phone: Optional[str] = None
    pending_booking_service_type: Optional[str] = None
    created_ts: float = 0.0
    last_ts: float = 0.0


def _model_to_state(m: SessionModel) -> SessionState:
    return SessionState(
        session_id=m.id,
        name=m.name,
        stage=m.stage,
        pending_intent=m.pending_intent,
        pending_booking_phone=m.pending_booking_phone,
        pending_booking_service_type=m.pending_booking_service_type,
        created_ts=m.created_at.timestamp() if m.created_at else 0.0,
        last_ts=m.updated_at.timestamp() if m.updated_at else 0.0,
    )


# ── Public API ───────────────────────────────────────────────────────────

def get_session(session_id: str) -> SessionState:
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
    with get_db() as db:
        m = db.query(SessionModel).filter_by(id=session_id).first()
        if not m:
            m = SessionModel(id=session_id)
            db.add(m)
            db.flush()
        for k, v in kwargs.items():
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
        "pending_booking_service_type": s.pending_booking_service_type,
        "created_ts": s.created_ts,
        "last_ts": s.last_ts,
    }
