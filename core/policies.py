from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .session_store import SessionState


TRANSACTION_INTENTS = {
    "book_appointment",
    "reschedule_appointment",
    "cancel_appointment",
    "list_appointments",
}

AUTH_REQUIRED_INTENTS = {
    "reschedule_appointment",
    "cancel_appointment",
    "list_appointments",
}

DESTRUCTIVE_TRANSACTION_INTENTS = {
    "reschedule_appointment",
    "cancel_appointment",
}

HUMAN_HANDOFF_MARKERS = (
    "live agent",
    "human agent",
    "real person",
    "representative",
    "customer support",
    "someone from support",
)

AFFIRMATIVE_CONFIRMATION_MARKERS = (
    "yes",
    "yeah",
    "yep",
    "confirm",
    "confirmed",
    "go ahead",
    "do it",
    "please do",
    "that works",
    "sounds good",
)

NEGATIVE_CONFIRMATION_MARKERS = (
    "no",
    "nope",
    "do not",
    "don't",
    "stop",
    "keep it",
    "leave it",
    "not now",
)


@dataclass(frozen=True)
class PolicyDecision:
    next_action: str = "respond"
    response_mode: str = "conversation"
    tool_allowed: bool = False
    needs_clarification: bool = False
    needs_confirmation: bool = False
    needs_auth: bool = False
    escalate: bool = False
    handoff_recommended: bool = False
    confirmation_resolution: Optional[str] = None
    reason_codes: list[str] = field(default_factory=list)


def _contains_marker(message: str, marker: str) -> bool:
    if " " in marker:
        return marker in message
    return bool(re.search(rf"\b{re.escape(marker)}\b", message))


def _message_contains_any(message: str, markers: tuple[str, ...]) -> bool:
    return any(_contains_marker(message, marker) for marker in markers)


def has_verified_identity(session: SessionState) -> bool:
    return bool(
        session.pending_booking_email
        or session.pending_booking_phone
        or session.auth_status == "verified"
    )


def parse_confirmation_response(message: str) -> Optional[str]:
    msg = (message or "").strip().lower()
    if not msg:
        return None
    if _message_contains_any(msg, NEGATIVE_CONFIRMATION_MARKERS):
        return "declined"
    if _message_contains_any(msg, AFFIRMATIVE_CONFIRMATION_MARKERS):
        return "approved"
    return None


def evaluate_policy(
    session: SessionState,
    message: str,
    intent: Optional[str] = None,
    best_similarity: Optional[float] = None,
) -> PolicyDecision:
    msg = (message or "").strip().lower()
    reasons: list[str] = []
    response_mode = "conversation"
    next_action = "respond"
    tool_allowed = bool(intent in TRANSACTION_INTENTS)
    needs_clarification = False
    needs_confirmation = False
    needs_auth = False
    escalate = False
    handoff_recommended = False
    confirmation_resolution: Optional[str] = None

    if _message_contains_any(msg, HUMAN_HANDOFF_MARKERS):
        reasons.append("USER_REQUESTED_HUMAN")
        return PolicyDecision(
            next_action="handoff",
            response_mode="handoff",
            tool_allowed=False,
            escalate=True,
            handoff_recommended=True,
            reason_codes=reasons,
        )

    if intent == "kb_query":
        response_mode = "knowledge"
        if best_similarity is not None and best_similarity < 0.25:
            reasons.append("LOW_EVIDENCE")
            needs_clarification = True
            next_action = "clarify"
    elif intent in TRANSACTION_INTENTS:
        response_mode = "transaction"

        if intent in AUTH_REQUIRED_INTENTS and not has_verified_identity(session):
            reasons.append("MISSING_AUTH")
            needs_auth = True
            tool_allowed = False
            next_action = "clarify"

        if session.awaiting_confirmation:
            confirmation_resolution = parse_confirmation_response(msg)
            if confirmation_resolution == "approved":
                reasons.append("USER_CONFIRMED")
                next_action = "proceed"
            elif confirmation_resolution == "declined":
                reasons.append("USER_DECLINED")
                tool_allowed = False
                next_action = "cancel"
            else:
                reasons.append("PENDING_CONFIRMATION")
                needs_confirmation = True
                tool_allowed = False
                next_action = "confirm"
                confirmation_resolution = "pending"

    if session.handoff_recommended and not handoff_recommended:
        reasons.append("PREVIOUS_ESCALATION_SIGNAL")

    return PolicyDecision(
        next_action=next_action,
        response_mode=response_mode,
        tool_allowed=tool_allowed,
        needs_clarification=needs_clarification,
        needs_confirmation=needs_confirmation,
        needs_auth=needs_auth,
        escalate=escalate,
        handoff_recommended=handoff_recommended,
        confirmation_resolution=confirmation_resolution,
        reason_codes=reasons,
    )
