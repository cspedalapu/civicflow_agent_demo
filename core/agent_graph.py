from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Literal, Optional, TypedDict
import re

from langgraph.graph import END, START, StateGraph

from .agent import answer_question, build_clarifying_question
from .appointments import AppointmentRequest, AppointmentStore
from .config import Settings
from .handoff import ensure_handoff
from .name_parser import extract_name
from .policies import TRANSACTION_INTENTS, evaluate_policy, parse_confirmation_response
from .router import RouteDecision, route_intent
from .session_store import get_session, update_session

Intent = Literal["book_appointment", "reschedule_appointment", "cancel_appointment", "list_appointments", "kb_query", "smalltalk"]


class AgentState(TypedDict, total=False):
    session_id: str
    message: str
    intent: Intent
    answer: str
    payload: Dict[str, Any]


@dataclass
class AgentGraphRunner:
    settings: Settings
    kb: Any
    appointment_store: AppointmentStore

    def __post_init__(self) -> None:
        self.graph = _build_graph(self)

    def run(self, session_id: str, message: str) -> Dict[str, Any]:
        state: AgentState = {"session_id": session_id, "message": message}
        out = self.graph.invoke(state, config={"configurable": {"thread_id": session_id}})
        return {
            "answer": out.get("answer", "I don't have that information in my knowledge base."),
            "refusal": bool(out.get("payload", {}).get("refusal", False)),
            "sources": out.get("payload", {}).get("sources", []),
            "best_similarity": out.get("payload", {}).get("best_similarity"),
            "timings_ms": out.get("payload", {}).get("timings_ms", {}),
            "intent": out.get("intent"),
        }


def _build_graph(runner: AgentGraphRunner):
    graph = StateGraph(AgentState)
    graph.add_node("route", lambda s: _route_node(runner, s))
    graph.add_node("smalltalk", lambda s: _smalltalk_node(runner, s))
    graph.add_node("kb_query", lambda s: _kb_node(runner, s))
    graph.add_node("book_appointment", lambda s: _book_node(runner, s))
    graph.add_node("reschedule_appointment", lambda s: _reschedule_node(runner, s))
    graph.add_node("cancel_appointment", lambda s: _cancel_node(runner, s))
    graph.add_node("list_appointments", lambda s: _list_node(runner, s))

    graph.add_edge(START, "route")
    graph.add_conditional_edges(
        "route",
        lambda s: s["intent"],
        {
            "smalltalk": "smalltalk",
            "kb_query": "kb_query",
            "book_appointment": "book_appointment",
            "reschedule_appointment": "reschedule_appointment",
            "cancel_appointment": "cancel_appointment",
            "list_appointments": "list_appointments",
        },
    )
    graph.add_edge("smalltalk", END)
    graph.add_edge("kb_query", END)
    graph.add_edge("book_appointment", END)
    graph.add_edge("reschedule_appointment", END)
    graph.add_edge("cancel_appointment", END)
    graph.add_edge("list_appointments", END)
    return graph.compile()


def _record_intent_state(session_id: str, session, message: str, intent: Intent) -> None:
    decision = evaluate_policy(session=session, message=message, intent=intent)

    updates: Dict[str, Any] = {
        "handoff_recommended": decision.handoff_recommended,
        "escalation_reason": "user_requested_human" if decision.handoff_recommended else None,
        "fallback_reason": decision.reason_codes[0].lower() if decision.reason_codes else None,
    }

    if intent == "book_appointment":
        updates.update(
            {
                "goal": "book_appointment",
                "subgoal": "collect_booking_details",
                "active_flow": "booking",
                "booking_stage": session.booking_stage or "intent_captured",
            }
        )
    elif intent == "reschedule_appointment":
        updates.update(
            {
                "goal": "reschedule_appointment",
                "subgoal": "identify_booking",
                "active_flow": "reschedule",
                "booking_stage": "identify_booking",
            }
        )
    elif intent == "cancel_appointment":
        updates.update(
            {
                "goal": "cancel_appointment",
                "subgoal": "identify_booking",
                "active_flow": "cancel",
                "booking_stage": "identify_booking",
            }
        )
    elif intent == "list_appointments":
        updates.update(
            {
                "goal": "list_appointments",
                "subgoal": "identify_booking",
                "active_flow": "lookup",
                "booking_stage": "identify_booking",
            }
        )
    elif intent == "kb_query":
        updates.update(
            {
                "active_flow": "knowledge_support",
                "subgoal": "answer_question",
                "unresolved_question": message,
            }
        )
    elif intent == "smalltalk":
        updates.update(
            {
                "active_flow": "smalltalk",
                "subgoal": "converse",
            }
        )

    update_session(session_id, **updates)


def _handoff_response(session_id: str) -> AgentState:
    update_session(
        session_id,
        handoff_recommended=True,
        escalation_reason="user_requested_human",
        active_flow="handoff",
        subgoal="human_support",
        last_agent_action="recommend_handoff",
        fallback_reason="user_requested_human",
        awaiting_confirmation=False,
    )
    ensure_handoff(session_id, reason="user_requested_human")
    return {
        "answer": (
            "A human agent would be the best next step here. "
            "I created a handoff ticket so an operator can claim the case and continue from the captured context."
        ),
        "payload": {"refusal": False, "policy": ["USER_REQUESTED_HUMAN"]},
    }


def _auth_prompt(intent: Intent) -> str:
    if intent == "reschedule_appointment":
        return "Before I change an appointment, please share the email address used for the booking."
    if intent == "cancel_appointment":
        return "Before I cancel an appointment, please share the email address used for the booking."
    if intent == "list_appointments":
        return "Please share the email address used for your booking so I can look it up."
    return "Please share the email address used for the booking so I can verify it."


def _confirmation_prompt(intent: Intent) -> str:
    if intent == "cancel_appointment":
        return "Please reply `yes` to confirm the cancellation, or `no` to keep the appointment."
    if intent == "reschedule_appointment":
        return "Please reply `yes` to confirm the change, or `no` to keep your current appointment."
    return "Please reply `yes` to confirm, or `no` to cancel."


def _continue_support_prompt() -> str:
    return "What else can I help you with today?"


def _abort_confirmation(session_id: str, intent: Intent) -> AgentState:
    update_session(
        session_id,
        pending_intent=None,
        awaiting_confirmation=False,
        confirmation_status="declined",
        fallback_reason="user_declined_confirmation",
        last_agent_action="confirmation_declined",
    )
    if intent == "cancel_appointment":
        answer = "Okay, I will keep the appointment as it is."
    elif intent == "reschedule_appointment":
        answer = "Okay, I will leave your appointment unchanged."
    else:
        answer = "Okay, I will not make that change."
    return {
        "answer": answer,
        "payload": {"refusal": False, "policy": ["USER_DECLINED"]},
    }


def _prompt_for_missing_auth(session_id: str, intent: Intent) -> AgentState:
    update_session(
        session_id,
        pending_intent=intent,
        auth_status="challenge_required",
        fallback_reason="missing_auth",
        last_agent_action="request_authentication",
    )
    return {
        "answer": _auth_prompt(intent),
        "payload": {"refusal": False, "policy": ["MISSING_AUTH"]},
    }


def _apply_transaction_policy(session_id: str, session, message: str, intent: Intent) -> tuple[Any, Optional[AgentState]]:
    decision = evaluate_policy(session=session, message=message, intent=intent)

    if decision.handoff_recommended:
        return decision, _handoff_response(session_id)

    if decision.confirmation_resolution == "declined":
        return decision, _abort_confirmation(session_id, intent)

    if decision.needs_confirmation:
        update_session(
            session_id,
            pending_intent=intent,
            awaiting_confirmation=True,
            confirmation_status="pending",
            fallback_reason="pending_confirmation",
            last_agent_action="awaiting_confirmation",
        )
        return decision, {
            "answer": _confirmation_prompt(intent),
            "payload": {"refusal": False, "policy": ["PENDING_CONFIRMATION"]},
        }

    if decision.needs_auth:
        return decision, _prompt_for_missing_auth(session_id, intent)

    return decision, None


def _route_node(runner: AgentGraphRunner, state: AgentState) -> AgentState:
    session_id = state["session_id"]
    session = get_session(session_id)
    message = (state.get("message") or "").strip()
    msg = message.lower()

    if _wants_to_reset_flow(msg):
        _reset_flow_state(session_id)
        return {"intent": "kb_query"}

    forced_intent = _forced_transaction_intent(session, message)
    if forced_intent:
        _prepare_route_state(session_id, session, msg, forced_intent)
        return {"intent": forced_intent}

    rule_intent = _rule_based_intent(session, msg)
    chosen_intent = rule_intent

    llm_decision = route_intent(runner.settings, session, message)
    if llm_decision and llm_decision.confidence >= runner.settings.router_min_confidence:
        chosen_intent = _resolve_router_choice(session, msg, llm_decision, rule_intent)

    _prepare_route_state(session_id, session, msg, chosen_intent)
    return {"intent": chosen_intent}


def _reset_flow_state(session_id: str) -> None:
    update_session(
        session_id,
        pending_intent=None,
        pending_booking_phone=None,
        pending_booking_email=None,
        pending_booking_service_type=None,
        goal=None,
        subgoal=None,
        active_flow="knowledge_support",
        booking_stage=None,
        last_offered_slots=[],
        selected_slot=None,
        selected_booking_id=None,
        unresolved_question=None,
        confirmation_status="not_requested",
        awaiting_confirmation=False,
        last_agent_action="reset_flow",
        fallback_reason=None,
        escalation_reason=None,
        handoff_recommended=False,
        handoff_ticket_id=None,
        handoff_status="none",
        handoff_assignee=None,
        handoff_claimed_at=None,
        handoff_resolved_at=None,
    )


def _prepare_route_state(session_id: str, session, message: str, intent: Intent) -> None:
    if intent in TRANSACTION_INTENTS:
        update_session(session_id, pending_intent=intent)
    _record_intent_state(session_id, session, message, intent)


def _rule_based_intent(session, message: str) -> Intent:
    if any(k in message for k in ("cancel appointment", "cancel booking", "cancel my", "rescind")):
        return "cancel_appointment"
    if _wants_to_reschedule(message):
        return "reschedule_appointment"
    if _resolve_post_booking_correction_slot(session, message):
        return "reschedule_appointment"
    if any(k in message for k in ("my booking", "my appointment", "list appointment", "status appointment", "check booking")):
        return "list_appointments"

    if _is_booking_side_question(message):
        return "kb_query"

    if session.pending_intent == "book_appointment":
        if _is_smalltalk_only(message):
            return "smalltalk"
        if _is_booking_side_question(message):
            return "kb_query"

    if any(k in message for k in ("book", "appointment", "schedule", "slot")):
        return "book_appointment"

    if session.pending_intent in {"book_appointment", "reschedule_appointment", "cancel_appointment", "list_appointments"}:
        return session.pending_intent

    if _is_smalltalk_only(message):
        return "smalltalk"

    return "kb_query"


def _forced_transaction_intent(session, message: str) -> Optional[Intent]:
    pending = session.pending_intent
    if pending not in {"book_appointment", "reschedule_appointment", "cancel_appointment", "list_appointments"}:
        return None

    if session.awaiting_confirmation:
        return pending

    if _looks_like_transaction_followup(message):
        return pending

    return None


def _looks_like_transaction_followup(message: str) -> bool:
    msg = (message or "").strip().lower()
    if not msg:
        return False
    if parse_confirmation_response(msg) is not None:
        return True
    if _extract_email(msg) or _extract_slot(msg):
        return True
    if _extract_datetime(msg):
        return True
    if _parse_slot_index_choice(msg) is not None:
        return True
    if _extract_day_of_month(msg) is not None:
        return True
    if _extract_time_parts(msg)[0] is not None:
        return True
    if re.search(r"\bAPT-[A-Z0-9]{10}\b", msg.upper()):
        return True
    if re.fullmatch(
        r"\s*(dl_appointment|state_id|renewal|renew|state id|id card|driver license|driver licence|dl)\s*",
        msg,
    ):
        return True
    return False


def _resolve_router_choice(session, message: str, decision: RouteDecision, fallback_intent: Intent) -> Intent:
    candidate = decision.intent
    pending = session.pending_intent

    if pending in {"book_appointment", "reschedule_appointment", "cancel_appointment", "list_appointments"}:
        if candidate in {"kb_query", "smalltalk"} and _looks_like_transaction_followup(message):
            return pending

    if candidate == "book_appointment" and _is_booking_side_question(message):
        return "kb_query"

    return candidate


def _smalltalk_node(runner: AgentGraphRunner, state: AgentState) -> AgentState:
    session = get_session(state["session_id"])
    text = (state.get("message") or "").strip().lower()
    category = _smalltalk_category(text)
    name = session.name or ""

    if category == "thanks":
        greeting = f"You're welcome, {name}." if name else "You're welcome."
        return {"answer": f"{greeting} If you need anything else about DL, ID, or appointments, just ask.", "payload": {"refusal": False}}
    if category == "bye":
        closing = f"Take care, {name}." if name else "Take care."
        return {"answer": f"{closing} Reach out anytime you need help with Texas DPS services.", "payload": {"refusal": False}}
    if category == "greeting":
        lead = f"Hi {name}," if name else "Hi,"
        return {"answer": f"{lead} how can I help you today?", "payload": {"refusal": False}}

    return {"answer": "I am here to help with DL, ID, and appointment questions.", "payload": {"refusal": False}}


def _kb_node(runner: AgentGraphRunner, state: AgentState) -> AgentState:
    message = state.get("message", "")
    session_id = state["session_id"]
    session = get_session(session_id)
    precheck = evaluate_policy(session=session, message=message, intent="kb_query")
    if precheck.handoff_recommended:
        return _handoff_response(session_id)

    result = answer_question(runner.settings, runner.kb, state.get("message", ""))
    decision = evaluate_policy(
        session=session,
        message=message,
        intent="kb_query",
        best_similarity=result.get("best_similarity"),
    )
    if decision.needs_clarification:
        update_session(
            session_id,
            active_flow="knowledge_support",
            subgoal="clarify_question",
            unresolved_question=message,
            fallback_reason="low_evidence",
            handoff_recommended=decision.handoff_recommended,
            escalation_reason="user_requested_human" if decision.handoff_recommended else None,
            last_agent_action="request_kb_clarification",
        )
        answer = result.get("answer") or build_clarifying_question(message)
        return {
            "answer": answer,
            "payload": {
                "refusal": False,
                "clarification": True,
                "sources": result.get("sources", []),
                "best_similarity": result.get("best_similarity"),
                "timings_ms": result.get("timings_ms", {}),
            },
        }

    update_session(
        session_id,
        active_flow="knowledge_support",
        subgoal="answered_question",
        unresolved_question=message,
        fallback_reason=decision.reason_codes[0].lower() if decision.reason_codes else None,
        handoff_recommended=decision.handoff_recommended,
        escalation_reason="user_requested_human" if decision.handoff_recommended else None,
        last_agent_action="answered_kb_question",
    )
    return {"answer": result["answer"], "payload": result}


def _book_node(runner: AgentGraphRunner, state: AgentState) -> AgentState:
    session_id = state["session_id"]
    message = state.get("message", "")
    session = get_session(session_id)
    decision = evaluate_policy(session=session, message=message, intent="book_appointment")
    if decision.handoff_recommended:
        return _handoff_response(session_id)

    name = session.name or extract_name(message)
    if not name:
        update_session(
            session_id,
            pending_intent="book_appointment",
            goal="book_appointment",
            subgoal="collect_name",
            active_flow="booking",
            booking_stage="collect_name",
            last_agent_action="request_name",
        )
        return {"answer": "To book your appointment, may I have your full name first?", "payload": {"refusal": False}}
    if not session.name:
        update_session(session_id, name=name, stage="active")

    email = _extract_email(message) or session.pending_booking_email or ""
    requested_slot = _extract_slot(message)
    slot_service = _service_from_slot(requested_slot)
    service_type = _extract_service_type(message) or slot_service or session.pending_booking_service_type

    update_session(
        session_id,
        pending_intent="book_appointment",
        pending_booking_phone=None,
        pending_booking_email=email or None,
        pending_booking_service_type=service_type or None,
    )

    if not email:
        update_session(
            session_id,
            goal="book_appointment",
            subgoal="collect_email",
            active_flow="booking",
            booking_stage="collect_email",
            last_agent_action="request_email",
        )
        return {
            "answer": "Great, please share the best email address for your appointment confirmation.",
            "payload": {"refusal": False},
        }

    if not service_type:
        update_session(
            session_id,
            goal="book_appointment",
            subgoal="collect_service_type",
            active_flow="booking",
            booking_stage="collect_service_type",
            last_agent_action="request_service_type",
        )
        return {
            "answer": (
                "What service do you need an appointment for? "
                "Please choose: `dl_appointment`, `state_id`, or `renewal`."
            ),
            "payload": {"refusal": False},
        }

    slots = runner.appointment_store.list_open_slots(service_type=service_type)
    if not slots:
        update_session(
            session_id,
            pending_booking_service_type=None,
            goal="book_appointment",
            subgoal="collect_service_type",
            active_flow="booking",
            booking_stage="collect_service_type",
            last_offered_slots=[],
            fallback_reason="no_slots_available",
            last_agent_action="no_slots_available",
        )
        return {
            "answer": (
                "I could not find open slots for that service right now.\n"
                "Please choose another service: `dl_appointment`, `state_id`, or `renewal`."
            ),
            "payload": {"refusal": False},
        }

    # Accept shorthand choices such as "1", "first one", or just "YYYY-MM-DD HH:MM".
    if not requested_slot:
        requested_slot = _resolve_slot_choice(message, slots)

    if not requested_slot:
        options = _format_slot_options(slots, limit=3)
        update_session(
            session_id,
            goal="book_appointment",
            subgoal="select_slot",
            active_flow="booking",
            booking_stage="select_slot",
            last_offered_slots=slots[:3],
            last_agent_action="offer_slots",
            fallback_reason=None,
        )
        return {
            "answer": f"Please pick one of these available slots:\n{options}",
            "payload": {"refusal": False},
        }

    if requested_slot not in slots:
        options = _format_slot_options(slots, limit=3)
        update_session(
            session_id,
            goal="book_appointment",
            subgoal="select_slot",
            active_flow="booking",
            booking_stage="select_slot",
            last_offered_slots=slots[:3],
            fallback_reason="ambiguous_slot_selection",
            last_agent_action="reoffer_slots",
        )
        return {
            "answer": f"That slot is unavailable. Please choose one of:\n{options}",
            "payload": {"refusal": False},
        }

    booking = runner.appointment_store.create_booking(
        AppointmentRequest(
            service_type=service_type,
            customer_name=name,
            customer_email=email,
            customer_phone="",
            slot=requested_slot,
        )
    )
    update_session(
        session_id,
        pending_intent=None,
        pending_booking_phone=None,
        pending_booking_email=email or None,
        auth_status="verified",
        pending_booking_service_type=service_type or None,
        goal="book_appointment",
        subgoal="completed",
        active_flow="booking",
        booking_stage="completed",
        last_offered_slots=slots[:3],
        selected_slot=requested_slot,
        selected_booking_id=booking["booking_id"],
        confirmation_status="confirmed",
        awaiting_confirmation=False,
        last_agent_action="booked_appointment",
        fallback_reason=None,
    )
    return {
        "answer": (
            f"You're all set. Your appointment is confirmed.\n"
            f"Booking ID: {booking['booking_id']}\n"
            f"Service: {booking['service_type']}\n"
            f"Slot: {booking['slot']}\n"
            f"Email: {booking.get('customer_email', email)}\n\n"
            f"{_continue_support_prompt()}"
        ),
        "payload": {"refusal": False, "booking": booking},
    }


def _reschedule_node(runner: AgentGraphRunner, state: AgentState) -> AgentState:
    session_id = state["session_id"]
    message = state.get("message", "")
    session = get_session(session_id)

    email = _extract_email(message) or session.pending_booking_email or ""
    if email and email != session.pending_booking_email:
        update_session(session_id, pending_booking_email=email, auth_status="verified")
        session = get_session(session_id)

    decision, blocked = _apply_transaction_policy(session_id, session, message, "reschedule_appointment")
    if blocked:
        return blocked

    if not email:
        return _prompt_for_missing_auth(session_id, "reschedule_appointment")

    booking = runner.appointment_store.latest_booking_for_email(email)
    if not booking:
        update_session(
            session_id,
            pending_intent="reschedule_appointment",
            pending_booking_email=email,
            auth_status="challenge_required",
            goal="reschedule_appointment",
            subgoal="identify_booking",
            active_flow="reschedule",
            booking_stage="identify_booking",
            fallback_reason="booking_not_found",
            last_agent_action="no_booking_found_for_reschedule",
        )
        return {
            "answer": "I couldn't find an active appointment for that email address.",
            "payload": {"refusal": False},
        }

    service_type = booking["service_type"]
    current_slot = booking["slot"]
    slots = [slot for slot in runner.appointment_store.list_open_slots(service_type=service_type) if slot != current_slot]
    if not slots:
        update_session(
            session_id,
            pending_intent=None,
            pending_booking_email=email,
            pending_booking_service_type=service_type,
            goal="reschedule_appointment",
            subgoal="select_new_slot",
            active_flow="reschedule",
            booking_stage="select_new_slot",
            selected_booking_id=booking["booking_id"],
            selected_slot=current_slot,
            fallback_reason="no_alternative_slots",
            last_agent_action="no_reschedule_slots_available",
        )
        return {
            "answer": "I couldn't find any alternative open slots for that appointment right now.",
            "payload": {"refusal": False},
        }

    correction_slot = _resolve_post_booking_correction_slot(session, message, current_slot=current_slot)
    requested_slot = _extract_slot(message) or correction_slot
    if not requested_slot:
        requested_slot = _resolve_slot_choice(message, slots)

    if session.awaiting_confirmation and decision.confirmation_resolution == "approved":
        requested_slot = session.selected_slot or requested_slot

    update_session(
        session_id,
        pending_intent="reschedule_appointment",
        pending_booking_email=email,
        auth_status="verified",
        pending_booking_service_type=service_type,
        goal="reschedule_appointment",
        subgoal="select_new_slot",
        active_flow="reschedule",
        booking_stage="select_new_slot",
        selected_booking_id=booking["booking_id"],
        selected_slot=current_slot,
    )

    if not requested_slot:
        options = _format_slot_options(slots, limit=3)
        update_session(
            session_id,
            last_offered_slots=slots[:3],
            last_agent_action="offer_reschedule_slots",
            fallback_reason=None,
        )
        return {
            "answer": (
                f"Sure, I can help change your appointment.\n"
                f"Your current slot is: {current_slot}\n"
                f"Please pick one of these available slots:\n{options}"
            ),
            "payload": {"refusal": False},
        }

    if requested_slot not in slots:
        options = _format_slot_options(slots, limit=3)
        update_session(
            session_id,
            last_offered_slots=slots[:3],
            fallback_reason="ambiguous_slot_selection",
            last_agent_action="reoffer_reschedule_slots",
        )
        return {
            "answer": (
                f"That slot isn't available for a change.\n"
                f"Your current slot is: {current_slot}\n"
                f"Please choose one of these available slots:\n{options}"
            ),
            "payload": {"refusal": False},
        }

    if not (session.awaiting_confirmation and decision.confirmation_resolution == "approved"):
        update_session(
            session_id,
            pending_intent="reschedule_appointment",
            pending_booking_email=email,
            pending_booking_service_type=service_type,
            goal="reschedule_appointment",
            subgoal="confirm_change",
            active_flow="reschedule",
            booking_stage="confirm_change",
            selected_booking_id=booking["booking_id"],
            selected_slot=requested_slot,
            awaiting_confirmation=True,
            confirmation_status="pending",
            fallback_reason="pending_confirmation",
            last_agent_action="request_reschedule_confirmation",
        )
        return {
            "answer": (
                f"I found your appointment.\n"
                f"Current slot: {current_slot}\n"
                f"Requested new slot: {requested_slot}\n"
                f"Reply `yes` to confirm the change or `no` to keep the current appointment."
            ),
            "payload": {"refusal": False, "policy": ["PENDING_CONFIRMATION"]},
        }

    updated = runner.appointment_store.reschedule_booking(booking["booking_id"], requested_slot)
    update_session(
        session_id,
        pending_intent=None,
        pending_booking_email=email,
        auth_status="verified",
        pending_booking_service_type=service_type,
        goal="reschedule_appointment",
        subgoal="completed",
        active_flow="reschedule",
        booking_stage="completed",
        last_offered_slots=slots[:3],
        selected_slot=requested_slot,
        selected_booking_id=booking["booking_id"],
        confirmation_status="confirmed",
        awaiting_confirmation=False,
        last_agent_action="rescheduled_appointment",
        fallback_reason=None,
    )
    return {
        "answer": (
            f"Your appointment has been updated.\n"
            f"Booking ID: {updated['booking_id']}\n"
            f"Service: {updated['service_type']}\n"
            f"New slot: {updated['slot']}\n"
            f"Email: {updated.get('customer_email', email)}\n\n"
            f"{_continue_support_prompt()}"
        ),
        "payload": {"refusal": False, "booking": updated},
    }


def _cancel_node(runner: AgentGraphRunner, state: AgentState) -> AgentState:
    session_id = state["session_id"]
    message = state.get("message", "")
    session = get_session(session_id)

    email = _extract_email(message) or session.pending_booking_email or ""
    if email and email != session.pending_booking_email:
        update_session(session_id, pending_booking_email=email, auth_status="verified")
        session = get_session(session_id)

    decision, blocked = _apply_transaction_policy(session_id, session, message, "cancel_appointment")
    if blocked:
        return blocked

    bookings = runner.appointment_store.bookings_for_email(email)
    if not bookings:
        update_session(
            session_id,
            pending_intent="cancel_appointment",
            pending_booking_email=email or None,
            auth_status="challenge_required",
            goal="cancel_appointment",
            subgoal="identify_booking",
            active_flow="cancel",
            booking_stage="identify_booking",
            fallback_reason="booking_not_found",
            last_agent_action="cancel_not_found",
        )
        return {"answer": "I could not find an active booking for that email address.", "payload": {"refusal": False}}

    m = re.search(r"\bAPT-[A-Z0-9]{10}\b", message.upper())
    booking_id = m.group(0) if m else session.selected_booking_id

    if not booking_id:
        if len(bookings) == 1:
            booking_id = bookings[0]["booking_id"]
            slot = bookings[0]["slot"]
            update_session(
                session_id,
                pending_intent="cancel_appointment",
                pending_booking_email=email,
                auth_status="verified",
                goal="cancel_appointment",
                subgoal="confirm_cancel",
                active_flow="cancel",
                booking_stage="confirm_cancel",
                selected_booking_id=booking_id,
                selected_slot=slot,
                awaiting_confirmation=True,
                confirmation_status="pending",
                fallback_reason="pending_confirmation",
                last_agent_action="request_cancel_confirmation",
            )
            return {
                "answer": (
                    f"I found booking {booking_id} for {slot}.\n"
                    f"Reply `yes` to confirm cancellation or `no` to keep the appointment."
                ),
                "payload": {"refusal": False, "policy": ["PENDING_CONFIRMATION"]},
            }

        lines = [f"- {item['booking_id']} | {item['service_type']} | {item['slot']}" for item in bookings]
        update_session(
            session_id,
            pending_intent="cancel_appointment",
            goal="cancel_appointment",
            subgoal="identify_booking",
            active_flow="cancel",
            booking_stage="identify_booking",
            pending_booking_email=email,
            auth_status="verified",
            selected_booking_id=None,
            last_agent_action="request_booking_id",
        )
        return {
            "answer": "I found multiple active bookings for that email. Please reply with the booking ID you want to cancel:\n" + "\n".join(lines),
            "payload": {"refusal": False},
        }

    booking = next((item for item in bookings if item["booking_id"] == booking_id), None)
    if not booking:
        update_session(
            session_id,
            pending_intent="cancel_appointment",
            pending_booking_email=email,
            auth_status="verified",
            goal="cancel_appointment",
            subgoal="identify_booking",
            active_flow="cancel",
            booking_stage="identify_booking",
            fallback_reason="booking_not_found",
            last_agent_action="cancel_not_found",
        )
        return {"answer": "I could not find an active booking with that ID for the verified email address.", "payload": {"refusal": False}}

    if not (session.awaiting_confirmation and decision.confirmation_resolution == "approved"):
        update_session(
            session_id,
            pending_intent="cancel_appointment",
            pending_booking_email=email,
            auth_status="verified",
            goal="cancel_appointment",
            subgoal="confirm_cancel",
            active_flow="cancel",
            booking_stage="confirm_cancel",
            selected_booking_id=booking_id,
            selected_slot=booking["slot"],
            awaiting_confirmation=True,
            confirmation_status="pending",
            fallback_reason="pending_confirmation",
            last_agent_action="request_cancel_confirmation",
        )
        return {
            "answer": (
                f"Please confirm the cancellation for booking {booking_id}.\n"
                f"Appointment: {booking['service_type']} | {booking['slot']}\n"
                f"Reply `yes` to cancel it or `no` to keep it."
            ),
            "payload": {"refusal": False, "policy": ["PENDING_CONFIRMATION"]},
        }

    ok = runner.appointment_store.cancel_booking(booking_id)
    if not ok:
        update_session(
            session_id,
            pending_intent="cancel_appointment",
            pending_booking_email=email,
            auth_status="verified",
            goal="cancel_appointment",
            subgoal="identify_booking",
            active_flow="cancel",
            booking_stage="identify_booking",
            fallback_reason="booking_not_found",
            last_agent_action="cancel_not_found",
        )
        return {"answer": "I could not find an active booking with that ID.", "payload": {"refusal": False}}
    update_session(
        session_id,
        pending_intent=None,
        pending_booking_email=email,
        auth_status="verified",
        goal="cancel_appointment",
        subgoal="completed",
        active_flow="cancel",
        booking_stage="completed",
        selected_booking_id=booking_id,
        confirmation_status="confirmed",
        awaiting_confirmation=False,
        last_agent_action="cancelled_appointment",
        fallback_reason=None,
    )
    return {
        "answer": f"Your appointment {booking_id} has been cancelled.\n\n{_continue_support_prompt()}",
        "payload": {"refusal": False},
    }


def _list_node(runner: AgentGraphRunner, state: AgentState) -> AgentState:
    session_id = state["session_id"]
    message = state.get("message", "")
    session = get_session(session_id)
    email = _extract_email(message) or session.pending_booking_email or ""
    if email and email != session.pending_booking_email:
        update_session(session_id, pending_booking_email=email, auth_status="verified")
        session = get_session(session_id)

    decision, blocked = _apply_transaction_policy(session_id, session, message, "list_appointments")
    if blocked:
        return blocked

    items = runner.appointment_store.bookings_for_email(email)
    if not items:
        update_session(
            session_id,
            pending_intent="list_appointments",
            goal="list_appointments",
            subgoal="identify_booking",
            active_flow="lookup",
            booking_stage="identify_booking",
            pending_booking_email=email,
            auth_status="challenge_required",
            fallback_reason="booking_not_found",
            last_agent_action="lookup_not_found",
        )
        return {"answer": "I couldn't find active appointments for that email address.", "payload": {"refusal": False}}
    update_session(
        session_id,
        pending_intent=None,
        goal="list_appointments",
        subgoal="completed",
        active_flow="lookup",
        booking_stage="completed",
        pending_booking_email=email,
        auth_status="verified",
        selected_booking_id=items[0]["booking_id"],
        last_agent_action="listed_appointments",
        fallback_reason=None,
    )
    lines = [f"- {b['booking_id']} | {b['service_type']} | {b['slot']}" for b in items]
    return {
        "answer": "Here are your active appointments:\n" + "\n".join(lines) + f"\n\n{_continue_support_prompt()}",
        "payload": {"refusal": False},
    }


def _extract_phone(text: str) -> str:
    digits = "".join(ch for ch in (text or "") if ch.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    return ""


def _extract_email(text: str) -> str:
    m = re.search(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", text or "", re.IGNORECASE)
    return m.group(0).strip().lower() if m else ""


def _extract_service_type(text: str) -> Optional[str]:
    t = (text or "").lower()
    if "dl_appointment" in t:
        return "dl_appointment"
    if "state_id" in t:
        return "state_id"
    if "renewal" in t:
        return "renewal"
    if "renew" in t:
        return "renewal"
    if "state id" in t or "id card" in t:
        return "state_id"
    if "driver license" in t or "driver licence" in t or "dl" in t:
        return "dl_appointment"
    return None


def _extract_slot(text: str) -> str:
    m = re.search(r"(dl_appointment|state_id|renewal)\s*\|\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", text or "", re.IGNORECASE)
    return m.group(0).lower() if m else ""


def _extract_datetime(text: str) -> str:
    m = re.search(r"\b\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\b", text or "")
    return m.group(0) if m else ""


def _extract_time_parts(text: str) -> tuple[Optional[int], Optional[int]]:
    raw = text or ""

    m = re.search(r"\b(\d{1,2}):(\d{2})\s*([ap])\.?m?\.?\b", raw, re.IGNORECASE)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2))
        meridiem = m.group(3).lower()
        if 1 <= hour <= 12:
            if meridiem == "p" and hour != 12:
                hour += 12
            elif meridiem == "a" and hour == 12:
                hour = 0
            return hour, minute

    m = re.search(r"\b(\d{1,2})\s*([ap])\.?m?\.?\b", raw, re.IGNORECASE)
    if m:
        hour = int(m.group(1))
        meridiem = m.group(2).lower()
        if 1 <= hour <= 12:
            if meridiem == "p" and hour != 12:
                hour += 12
            elif meridiem == "a" and hour == 12:
                hour = 0
            return hour, 0

    m = re.search(r"\b(\d{1,2}):(\d{2})\b", raw)
    if m:
        return int(m.group(1)), int(m.group(2))

    return None, None


def _extract_day_of_month(text: str) -> Optional[int]:
    m = re.search(r"\b(?:on\s+)?(\d{1,2})(?:st|nd|rd|th)?\b", text or "", re.IGNORECASE)
    if not m:
        return None
    day = int(m.group(1))
    return day if 1 <= day <= 31 else None


def _slot_to_datetime(slot: str) -> Optional[datetime]:
    if "|" not in slot:
        return None
    try:
        dt_text = slot.split("|", 1)[1].strip()
        return datetime.strptime(dt_text, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def _parse_slot_index_choice(text: str) -> Optional[int]:
    t = (text or "").strip().lower()
    if not t:
        return None

    letters = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}

    # Bare numeric choice: "1", "2"
    m = re.fullmatch(r"\s*(\d{1,2})\s*", t)
    if m:
        return int(m.group(1))

    # Bare letter choice: "a", "b"
    m = re.fullmatch(r"\s*([a-e])\s*", t)
    if m:
        return letters[m.group(1)]

    # "option 1", "slot 2", "pick 3", etc.
    m = re.search(r"\b(?:option|slot|pick|choose|select|go with|take)\s*(\d{1,2})\b", t)
    if m:
        return int(m.group(1))

    # "option a", "slot b", "go with c", etc.
    m = re.search(r"\b(?:option|slot|pick|choose|select|go with|take)\s*([a-e])\b", t)
    if m:
        return letters[m.group(1)]

    # "sorry b", "actually 2", "meant c", etc.
    m = re.search(r"\b(?:sorry|actually|meant|instead|rather)\s+([a-e])\b", t)
    if m:
        return letters[m.group(1)]

    m = re.search(r"\b(?:sorry|actually|meant|instead|rather)\s+(\d{1,2})\b", t)
    if m:
        return int(m.group(1))

    # Common ordinals.
    if "first" in t:
        return 1
    if "second" in t:
        return 2
    if "third" in t:
        return 3
    if "fourth" in t:
        return 4
    if "fifth" in t:
        return 5
    return None


def _resolve_slot_choice(text: str, slots: list[str]) -> str:
    if not slots:
        return ""

    idx = _parse_slot_index_choice(text)
    if idx is not None and 1 <= idx <= len(slots):
        return slots[idx - 1]

    dt = _extract_datetime(text)
    if dt:
        for slot in slots:
            if dt in slot:
                return slot

    slot_dts = [(slot, _slot_to_datetime(slot)) for slot in slots]

    day = _extract_day_of_month(text)
    hour, minute = _extract_time_parts(text)
    if day is not None or hour is not None:
        matches: list[str] = []
        for slot, slot_dt in slot_dts:
            if slot_dt is None:
                continue
            if day is not None and slot_dt.day != day:
                continue
            if hour is not None and slot_dt.hour != hour:
                continue
            if minute is not None and slot_dt.minute != minute:
                continue
            matches.append(slot)
        if len(matches) == 1:
            return matches[0]

    if hour is not None:
        matches = []
        for slot, slot_dt in slot_dts:
            if slot_dt is None or slot_dt.hour != hour:
                continue
            if minute is not None and slot_dt.minute != minute:
                continue
            matches.append(slot)
        if len(matches) == 1:
            return matches[0]

    return ""


def _format_slot_options(slots: list[str], limit: int = 3) -> str:
    chosen = slots[:limit]
    letters = "ABCDE"
    return "\n".join(f"{i}. ({letters[i - 1]}) {slot}" for i, slot in enumerate(chosen, start=1))


def _service_from_slot(slot: str) -> Optional[str]:
    if not slot:
        return None
    return slot.split("|", 1)[0].strip().lower()


def _resolve_post_booking_correction_slot(
    session,
    message: str,
    *,
    current_slot: Optional[str] = None,
) -> str:
    if not session.selected_booking_id:
        return ""
    if session.confirmation_status != "confirmed":
        return ""
    offered_slots = session.last_offered_slots or []
    if len(offered_slots) < 2:
        return ""

    active_slot = (current_slot or session.selected_slot or "").strip().lower()
    requested_slot = _extract_slot(message)
    if not requested_slot:
        requested_slot = _resolve_slot_choice(message, offered_slots)
    if not requested_slot:
        return ""

    requested_slot = requested_slot.strip().lower()
    if not active_slot or requested_slot == active_slot:
        return ""
    if requested_slot not in {slot.lower() for slot in offered_slots}:
        return ""
    return requested_slot


def _wants_to_reset_flow(message: str) -> bool:
    msg = (message or "").lower()
    return any(
        token in msg
        for token in (
            "never mind",
            "nevermind",
            "start over",
            "new topic",
            "forget it",
            "stop booking",
        )
    )


def _smalltalk_category(message: str) -> str:
    msg = (message or "").strip().lower()
    if re.search(r"\b(thank you|thanks|thx|appreciate it)\b", msg):
        return "thanks"
    if re.search(r"\b(bye|goodbye|see you|talk to you later|have a good day)\b", msg):
        return "bye"
    if re.search(r"\b(hi|hello|hey|good morning|good afternoon|good evening)\b", msg):
        return "greeting"
    return ""


def _is_smalltalk_only(message: str) -> bool:
    msg = (message or "").strip().lower()
    if not msg:
        return False
    category = _smalltalk_category(msg)
    if not category:
        return False

    # Avoid stealing messages that include concrete task intent.
    task_tokens = (
        "book",
        "appointment",
        "schedule",
        "cancel",
        "renew",
        "license",
        "dl",
        "id",
        "cdl",
        "slot",
        "document",
        "requirements",
        "how",
        "what",
        "where",
    )
    for t in task_tokens:
        if t in msg and category != "thanks":
            return False
    return True


def _is_booking_side_question(message: str) -> bool:
    msg = (message or "").strip().lower()
    if not msg:
        return False

    # Keep booking flow when user is providing booking payloads.
    if _extract_email(msg) or _extract_slot(msg):
        return False
    if _parse_slot_index_choice(msg) is not None:
        return False
    if re.fullmatch(
        r"\s*(dl_appointment|state_id|renewal|renew|state id|id card|driver license|driver licence|dl)\s*",
        msg,
    ):
        return False

    # Side info questions that should hit KB/RAG without discarding booking context.
    kb_tokens = (
        "document",
        "documents",
        "paperwork",
        "bring",
        "requirement",
        "requirements",
        "proof",
        "carry",
        "fees",
        "fee",
        "cost",
        "eligibility",
        "online",
        "process",
    )
    if any(t in msg for t in kb_tokens):
        return True

    question_markers = (
        "before that",
        "want to know",
        "need to know",
        "tell me",
        "not for appointment",
        "not for the appointment",
    )
    if any(marker in msg for marker in question_markers):
        return True

    return False


def _wants_to_reschedule(message: str) -> bool:
    msg = (message or "").lower()
    return any(
        token in msg
        for token in (
            "reschedule",
            "change appointment",
            "change my appointment",
            "move appointment",
            "move my appointment",
            "change to ",
        )
    )
