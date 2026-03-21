from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .session_store import SessionState


TRANSACTION_INTENTS = {
    "book_appointment",
    "reschedule_appointment",
    "cancel_appointment",
    "list_appointments",
}

HUMAN_HANDOFF_MARKERS = (
    "live agent",
    "human agent",
    "real person",
    "representative",
    "customer support",
    "someone from support",
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
    reason_codes: list[str] = field(default_factory=list)


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

    if any(marker in msg for marker in HUMAN_HANDOFF_MARKERS):
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
        if intent in {"cancel_appointment", "reschedule_appointment", "list_appointments"}:
            has_identity = bool(
                session.pending_booking_email
                or session.pending_booking_phone
                or session.auth_status == "verified"
            )
            if not has_identity:
                reasons.append("MISSING_AUTH")
                needs_auth = True
                tool_allowed = False
                next_action = "clarify"
        if session.awaiting_confirmation:
            reasons.append("PENDING_CONFIRMATION")
            needs_confirmation = True
            tool_allowed = False
            next_action = "confirm"

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
        reason_codes=reasons,
    )
