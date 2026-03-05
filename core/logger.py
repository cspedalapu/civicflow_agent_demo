"""
core/logger.py
──────────────
Chat event logging backed by SQLAlchemy / SQLite.

Public API unchanged: `ensure_session_id`, `log_chat_event`.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List

from .database import ChatMessage, get_db


def ensure_session_id(session_id: str | None) -> str:
    return session_id.strip() if session_id and session_id.strip() else str(uuid.uuid4())


def log_chat_event(event: Dict[str, Any]) -> None:
    """Persist a chat event to the database.

    Expected keys (all optional except session_id & question/answer):
        session_id, question, answer, stage, name,
        intent, refusal, best_similarity, sources
    """
    session_id = event.get("session_id", "")
    question = event.get("question", "")
    answer = event.get("answer", "")
    sources = event.get("sources")

    with get_db() as db:
        # Store the user message
        if question:
            db.add(
                ChatMessage(
                    session_id=session_id,
                    role="user",
                    content=question,
                )
            )
        # Store the assistant reply
        if answer:
            db.add(
                ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=answer,
                    intent=event.get("intent"),
                    refusal=bool(event.get("refusal", False)),
                    best_similarity=event.get("best_similarity"),
                    sources_json=json.dumps(sources, ensure_ascii=False) if sources else None,
                )
            )
        db.commit()


def get_chat_history(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Return recent chat messages for a session (newest last)."""
    with get_db() as db:
        rows = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
            .all()
        )
    rows.reverse()  # oldest first
    return [
        {
            "role": r.role,
            "content": r.content,
            "intent": r.intent,
            "refusal": r.refusal,
            "best_similarity": r.best_similarity,
            "sources": json.loads(r.sources_json) if r.sources_json else [],
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
