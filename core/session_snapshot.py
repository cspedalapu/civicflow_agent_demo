from __future__ import annotations

from typing import Any, Dict, List, Optional

from .database import ChatMessage, SessionModel, get_db
from .session_store import SessionState, get_session, session_to_dict

_FLOW_LABELS = {
    "booking": "Booking",
    "reschedule": "Reschedule",
    "cancel": "Cancellation",
    "lookup": "Appointment Lookup",
    "knowledge_support": "Knowledge Support",
    "smalltalk": "Conversation",
    "handoff": "Human Handoff",
}

_HANDOFF_STATUS_LABELS = {
    "recommended": "Ready For Agent",
    "claimed": "Claimed By Operator",
    "resolved": "Resolved",
    "none": "No Handoff",
}

_REASON_LABELS = {
    "user_requested_human": "Customer asked for a human agent",
    "low_evidence": "Low-evidence knowledge retrieval",
    "missing_auth": "Identity verification still needed",
    "pending_confirmation": "Waiting for customer confirmation",
    "booking_not_found": "Booking could not be located",
    "no_slots_available": "No open slots are currently available",
    "no_alternative_slots": "No alternative slots are currently available",
    "ambiguous_slot_selection": "Customer needs to choose from offered slots",
    "user_declined_confirmation": "Customer declined the change",
}

_ACTION_LABELS = {
    "request_name": "Collect customer name",
    "request_email": "Collect booking email",
    "request_service_type": "Collect service type",
    "offer_slots": "Offer available slots",
    "reoffer_slots": "Re-offer available slots",
    "booked_appointment": "Booking completed",
    "offer_reschedule_slots": "Offer replacement slots",
    "reoffer_reschedule_slots": "Re-offer replacement slots",
    "request_reschedule_confirmation": "Request reschedule confirmation",
    "rescheduled_appointment": "Reschedule completed",
    "request_cancel_confirmation": "Request cancellation confirmation",
    "cancelled_appointment": "Cancellation completed",
    "request_authentication": "Request booking verification",
    "listed_appointments": "Appointments listed",
    "recommend_handoff": "Recommend human handoff",
    "request_kb_clarification": "Ask a clarifying knowledge question",
    "answered_kb_question": "Answer grounded knowledge question",
}


def _flow_label(flow: Optional[str]) -> str:
    if not flow:
        return "Conversation"
    return _FLOW_LABELS.get(flow, flow.replace("_", " ").title())


def _humanize_reason(reason: Optional[str]) -> str:
    if not reason:
        return ""
    return _REASON_LABELS.get(reason, reason.replace("_", " ").capitalize())


def _humanize_action(action: Optional[str]) -> str:
    if not action:
        return ""
    return _ACTION_LABELS.get(action, action.replace("_", " ").capitalize())


def _progress_for_session(session: SessionState) -> int:
    goal = session.goal or session.pending_intent or ""
    stage = session.booking_stage or session.subgoal or ""

    if session.handoff_recommended:
        return 100

    if goal == "book_appointment":
        return {
            "collect_name": 20,
            "collect_email": 40,
            "collect_service_type": 55,
            "select_slot": 75,
            "confirmed": 100,
            "completed": 100,
        }.get(stage, 15)

    if goal == "reschedule_appointment":
        return {
            "identify_booking": 30,
            "select_new_slot": 65,
            "confirm_change": 85,
            "confirmed": 100,
            "completed": 100,
        }.get(stage, 20)

    if goal == "cancel_appointment":
        return {
            "identify_booking": 35,
            "confirm_cancel": 85,
            "confirmed": 100,
            "completed": 100,
        }.get(stage, 20)

    if goal == "list_appointments":
        return {
            "identify_booking": 45,
            "completed": 100,
        }.get(stage, 20)

    if session.active_flow == "knowledge_support":
        if session.subgoal == "clarify_question":
            return 55
        if session.subgoal == "answered_question":
            return 100
        return 70

    return 100 if session.last_agent_action else 0


def _status_tone(session: SessionState) -> str:
    if session.handoff_recommended:
        return "critical"
    if session.awaiting_confirmation or session.auth_status == "challenge_required":
        return "warning"
    if session.fallback_reason in {
        "low_evidence",
        "booking_not_found",
        "no_slots_available",
        "no_alternative_slots",
        "ambiguous_slot_selection",
    }:
        return "warning"
    if session.booking_stage in {"confirmed", "completed"} or session.subgoal == "completed":
        return "success"
    return "info"


def _status_headline(session: SessionState) -> str:
    if session.handoff_status == "claimed":
        return "Human handoff claimed"
    if session.handoff_recommended:
        return "Human handoff recommended"
    if session.awaiting_confirmation:
        return "Awaiting customer confirmation"
    if session.auth_status == "challenge_required":
        return "Identity verification needed"
    if session.booking_stage in {"confirmed", "completed"} or session.subgoal == "completed":
        return f"{_flow_label(session.active_flow)} complete"
    if session.goal:
        return f"{session.goal.replace('_', ' ').title()} in progress"
    if session.active_flow:
        return _flow_label(session.active_flow)
    return "Conversation ready"


def _next_step(session: SessionState) -> str:
    if session.handoff_status == "claimed":
        assignee = session.handoff_assignee or "the assigned operator"
        return f"{assignee} has claimed this case and should continue from the transcript."
    if session.handoff_recommended:
        return "A human agent should review the transcript and continue from the captured context."
    if session.awaiting_confirmation:
        return "Waiting for the customer to approve or decline the requested change."
    if session.auth_status == "challenge_required":
        return "Collect the booking email address before exposing or changing appointment details."
    if session.booking_stage == "collect_name":
        return "Collect the customer's full name."
    if session.booking_stage == "collect_email":
        return "Collect the email address that should receive the appointment confirmation."
    if session.booking_stage == "collect_service_type":
        return "Capture the service type before offering appointment slots."
    if session.booking_stage in {"select_slot", "select_new_slot"}:
        return "Waiting for the customer to choose one of the offered slots."
    if session.booking_stage in {"confirm_change", "confirm_cancel"}:
        return "Await an explicit yes/no confirmation before mutating the booking."
    if session.booking_stage in {"confirmed", "completed"} or session.subgoal == "completed":
        return "No further action is needed unless the customer asks for another change."
    if session.subgoal == "clarify_question":
        return "Ask a narrower question so the system can retrieve stronger evidence."
    return "Continue the conversation."


def _detail_lines(session: SessionState) -> List[str]:
    details: List[str] = []

    if session.name:
        details.append(f"Customer: {session.name}")
    if session.pending_booking_email:
        details.append(f"Booking email: {session.pending_booking_email}")
    if session.pending_booking_service_type:
        details.append(f"Service: {session.pending_booking_service_type}")
    if session.selected_booking_id:
        details.append(f"Booking ID: {session.selected_booking_id}")
    if session.selected_slot:
        details.append(f"Selected slot: {session.selected_slot}")
    if session.last_agent_action:
        details.append(f"Last agent action: {_humanize_action(session.last_agent_action)}")
    if session.fallback_reason:
        details.append(f"Attention point: {_humanize_reason(session.fallback_reason)}")
    if session.handoff_ticket_id:
        details.append(f"Handoff ticket: {session.handoff_ticket_id}")
    if session.handoff_assignee:
        details.append(f"Operator: {session.handoff_assignee}")
    return details


def _trim_content(text: str, limit: int = 180) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _recent_messages(session_id: str, limit: int = 6) -> List[Dict[str, Any]]:
    with get_db() as db:
        rows = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
            .all()
        )

    rows.reverse()
    return [
        {
            "role": row.role,
            "content": row.content,
            "preview": _trim_content(row.content),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


def _last_user_message(session_id: str) -> str:
    with get_db() as db:
        row = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id, ChatMessage.role == "user")
            .order_by(ChatMessage.id.desc())
            .first()
        )
    return row.content if row else ""


def _build_handoff(session_id: str, session: SessionState, recent_messages: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not session.handoff_recommended and session.handoff_status != "claimed":
        return None

    flow = _flow_label(session.active_flow)
    issue = _trim_content(_last_user_message(session_id), limit=220)
    context_bits = []
    if session.pending_booking_email:
        context_bits.append(f"verified email {session.pending_booking_email}")
    if session.selected_booking_id:
        context_bits.append(f"booking {session.selected_booking_id}")
    if session.selected_slot:
        context_bits.append(f"slot {session.selected_slot}")
    if session.fallback_reason:
        context_bits.append(_humanize_reason(session.fallback_reason).lower())

    context = ", ".join(context_bits)
    summary = f"Customer needs a human follow-up during the {flow.lower()} flow."
    if context:
        summary += f" Context captured: {context}."
    if issue:
        summary += f" Latest customer request: {issue}"

    return {
        "ticket_id": session.handoff_ticket_id or f"HND-{session_id.replace('-', '').upper()[-8:]}",
        "status": session.handoff_status or "recommended",
        "status_label": _HANDOFF_STATUS_LABELS.get(session.handoff_status or "recommended", "Ready For Agent"),
        "assignee": session.handoff_assignee,
        "reason": _humanize_reason(session.escalation_reason) or "Customer requested human support",
        "summary": summary,
        "next_step": "Share the transcript and continue with a live DPS support representative.",
        "recent_messages": recent_messages[-4:],
    }


def build_session_snapshot(session_id: str, history_limit: int = 6) -> Dict[str, Any]:
    session = get_session(session_id)
    recent_messages = _recent_messages(session_id, limit=history_limit)
    payload = session_to_dict(session)
    payload.update(
        {
            "flow_label": _flow_label(session.active_flow),
            "status_tone": _status_tone(session),
            "transaction": {
                "headline": _status_headline(session),
                "flow_label": _flow_label(session.active_flow),
                "progress": _progress_for_session(session),
                "status_tone": _status_tone(session),
                "next_step": _next_step(session),
                "details": _detail_lines(session),
            },
            "recent_messages": recent_messages,
            "handoff": _build_handoff(session_id, session, recent_messages),
        }
    )
    return payload


def get_handoff_queue(limit: int = 10) -> Dict[str, Any]:
    with get_db() as db:
        rows = (
            db.query(SessionModel)
            .filter(
                (SessionModel.handoff_recommended == True) | (SessionModel.handoff_status == "claimed")  # noqa: E712
            )
            .order_by(SessionModel.updated_at.desc())
            .limit(limit)
            .all()
        )

    items: List[Dict[str, Any]] = []
    for row in rows:
        recent_messages = _recent_messages(row.id, limit=4)
        items.append(
            {
                "session_id": row.id,
                "ticket_id": row.handoff_ticket_id or f"HND-{row.id.replace('-', '').upper()[-8:]}",
                "name": row.name,
                "flow_label": _flow_label(row.active_flow),
                "reason": _humanize_reason(row.escalation_reason) or "Customer requested human support",
                "status": row.handoff_status or "recommended",
                "status_label": _HANDOFF_STATUS_LABELS.get(row.handoff_status or "recommended", "Ready For Agent"),
                "assignee": row.handoff_assignee,
                "summary": _build_queue_summary(row, recent_messages),
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
        )
    return {"count": len(items), "items": items}


def _build_queue_summary(row: SessionModel, recent_messages: List[Dict[str, Any]]) -> str:
    latest_user = next((item["preview"] for item in reversed(recent_messages) if item["role"] == "user"), "")
    if latest_user:
        return latest_user
    if row.selected_booking_id:
        return f"{_flow_label(row.active_flow)} case for booking {row.selected_booking_id}"
    if row.pending_booking_email:
        return f"{_flow_label(row.active_flow)} case for {row.pending_booking_email}"
    return f"{_flow_label(row.active_flow)} conversation waiting for agent follow-up"
