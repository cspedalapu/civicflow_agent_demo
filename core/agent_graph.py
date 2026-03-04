from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, TypedDict
import re

from langgraph.graph import END, START, StateGraph

from .agent import answer_question
from .appointments import AppointmentRequest, AppointmentStore
from .config import Settings
from .name_parser import extract_name
from .session_store import get_session, update_session

Intent = Literal["book_appointment", "cancel_appointment", "list_appointments", "kb_query"]


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
    graph.add_node("kb_query", lambda s: _kb_node(runner, s))
    graph.add_node("book_appointment", lambda s: _book_node(runner, s))
    graph.add_node("cancel_appointment", lambda s: _cancel_node(runner, s))
    graph.add_node("list_appointments", lambda s: _list_node(runner, s))

    graph.add_edge(START, "route")
    graph.add_conditional_edges(
        "route",
        lambda s: s["intent"],
        {
            "kb_query": "kb_query",
            "book_appointment": "book_appointment",
            "cancel_appointment": "cancel_appointment",
            "list_appointments": "list_appointments",
        },
    )
    graph.add_edge("kb_query", END)
    graph.add_edge("book_appointment", END)
    graph.add_edge("cancel_appointment", END)
    graph.add_edge("list_appointments", END)
    return graph.compile()


def _route_node(runner: AgentGraphRunner, state: AgentState) -> AgentState:
    session_id = state["session_id"]
    session = get_session(session_id)
    msg = (state.get("message") or "").strip().lower()

    if _wants_to_reset_flow(msg):
        update_session(
            session_id,
            pending_intent=None,
            pending_booking_phone=None,
            pending_booking_service_type=None,
        )
        return {"intent": "kb_query"}

    if any(k in msg for k in ("cancel appointment", "cancel booking", "cancel my", "rescind")):
        update_session(session_id, pending_intent="cancel_appointment")
        return {"intent": "cancel_appointment"}
    if any(k in msg for k in ("my booking", "my appointment", "list appointment", "status appointment", "check booking")):
        update_session(session_id, pending_intent="list_appointments")
        return {"intent": "list_appointments"}
    if any(k in msg for k in ("book", "appointment", "schedule", "slot")):
        update_session(session_id, pending_intent="book_appointment")
        return {"intent": "book_appointment"}

    if session.pending_intent in {"book_appointment", "cancel_appointment", "list_appointments"}:
        return {"intent": session.pending_intent}

    return {"intent": "kb_query"}


def _kb_node(runner: AgentGraphRunner, state: AgentState) -> AgentState:
    result = answer_question(runner.settings, runner.kb, state.get("message", ""))
    return {"answer": result["answer"], "payload": result}


def _book_node(runner: AgentGraphRunner, state: AgentState) -> AgentState:
    session_id = state["session_id"]
    message = state.get("message", "")
    session = get_session(session_id)

    name = session.name or extract_name(message)
    if not name:
        update_session(session_id, pending_intent="book_appointment")
        return {"answer": "To book your appointment, may I have your full name first?", "payload": {"refusal": False}}
    if not session.name:
        update_session(session_id, name=name, stage="active")

    requested_slot = _extract_slot(message)
    slot_service = _service_from_slot(requested_slot)

    phone = _extract_phone(message) or session.pending_booking_phone or ""
    service_type = _extract_service_type(message) or slot_service or session.pending_booking_service_type

    update_session(
        session_id,
        pending_intent="book_appointment",
        pending_booking_phone=phone or None,
        pending_booking_service_type=service_type or None,
    )

    if not phone:
        return {
            "answer": "Please share a contact phone number for the booking (10 digits).",
            "payload": {"refusal": False},
        }

    if not service_type:
        return {
            "answer": (
                "What service do you need an appointment for? "
                "Please choose: `dl_appointment`, `state_id`, or `renewal`."
            ),
            "payload": {"refusal": False},
        }

    slots = runner.appointment_store.list_open_slots(service_type=service_type)
    if not slots:
        return {
            "answer": "I could not find open slots for that service right now. Try a different service type.",
            "payload": {"refusal": False},
        }

    if not requested_slot:
        options = "\n".join(f"- {s}" for s in slots[:3])
        return {
            "answer": f"Please pick one of these available slots:\n{options}",
            "payload": {"refusal": False},
        }

    if requested_slot not in slots:
        options = "\n".join(f"- {s}" for s in slots[:3])
        return {
            "answer": f"That slot is unavailable. Please choose one of:\n{options}",
            "payload": {"refusal": False},
        }

    booking = runner.appointment_store.create_booking(
        AppointmentRequest(
            service_type=service_type,
            customer_name=name,
            customer_phone=phone,
            slot=requested_slot,
        )
    )
    update_session(
        session_id,
        pending_intent=None,
        pending_booking_phone=None,
        pending_booking_service_type=None,
    )
    return {
        "answer": (
            f"Your appointment is confirmed.\n"
            f"Booking ID: {booking['booking_id']}\n"
            f"Service: {booking['service_type']}\n"
            f"Slot: {booking['slot']}"
        ),
        "payload": {"refusal": False, "booking": booking},
    }


def _cancel_node(runner: AgentGraphRunner, state: AgentState) -> AgentState:
    session_id = state["session_id"]
    msg = state.get("message", "")
    m = re.search(r"\bAPT-[A-Z0-9]{10}\b", msg.upper())
    if not m:
        update_session(session_id, pending_intent="cancel_appointment")
        return {
            "answer": "Please provide your booking ID in this format: APT-XXXXXXXXXX",
            "payload": {"refusal": False},
        }
    booking_id = m.group(0)
    ok = runner.appointment_store.cancel_booking(booking_id)
    if not ok:
        return {"answer": "I could not find an active booking with that ID.", "payload": {"refusal": False}}
    update_session(session_id, pending_intent=None)
    return {"answer": f"Your appointment {booking_id} has been cancelled.", "payload": {"refusal": False}}


def _list_node(runner: AgentGraphRunner, state: AgentState) -> AgentState:
    session_id = state["session_id"]
    phone = _extract_phone(state.get("message", ""))
    if not phone:
        update_session(session_id, pending_intent="list_appointments")
        return {
            "answer": "Please share the phone number used for your booking so I can look it up.",
            "payload": {"refusal": False},
        }
    items = runner.appointment_store.bookings_for_phone(phone)
    if not items:
        return {"answer": "I couldn't find active appointments for that phone number.", "payload": {"refusal": False}}
    update_session(session_id, pending_intent=None)
    lines = [f"- {b['booking_id']} | {b['service_type']} | {b['slot']}" for b in items]
    return {"answer": "Here are your active appointments:\n" + "\n".join(lines), "payload": {"refusal": False}}


def _extract_phone(text: str) -> str:
    digits = "".join(ch for ch in (text or "") if ch.isdigit())
    if len(digits) >= 10:
        return digits[-10:]
    return ""


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


def _service_from_slot(slot: str) -> Optional[str]:
    if not slot:
        return None
    return slot.split("|", 1)[0].strip().lower()


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
