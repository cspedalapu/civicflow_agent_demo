from __future__ import annotations
from dataclasses import dataclass, asdict, field
from typing import Dict, Optional
import time
import threading

_LOCK = threading.RLock()

@dataclass
class SessionState:
    session_id: str
    name: Optional[str] = None
    stage: str = "new"   # new -> awaiting_name -> active
    pending_intent: Optional[str] = None
    pending_booking_phone: Optional[str] = None
    pending_booking_service_type: Optional[str] = None
    created_ts: float = field(default_factory=time.time)
    last_ts: float = field(default_factory=time.time)

_SESSIONS: Dict[str, SessionState] = {}

def get_session(session_id: str) -> SessionState:
    with _LOCK:
        s = _SESSIONS.get(session_id)
        if not s:
            s = SessionState(session_id=session_id)
            _SESSIONS[session_id] = s
        s.last_ts = time.time()
        return s

def update_session(session_id: str, **kwargs) -> SessionState:
    with _LOCK:
        s = _SESSIONS.get(session_id)
        if not s:
            s = SessionState(session_id=session_id)
            _SESSIONS[session_id] = s
        for k, v in kwargs.items():
            setattr(s, k, v)
        s.last_ts = time.time()
        return s

def session_to_dict(s: SessionState) -> dict:
    return asdict(s)
