from pathlib import Path
import uuid

from core.agent_graph import AgentGraphRunner
from core.appointments import AppointmentStore
from core.config import Settings
from core.database import Booking, get_db
from core.router import RouteDecision
from core.session_store import update_session


class DummyKB:
    def query(self, query_text: str, top_k: int):
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}


def _runner(tmp_path: Path) -> AgentGraphRunner:
    settings = Settings(
        appointments_path=str(tmp_path / "appointments.json"),
        use_llm_router=True,
        router_min_confidence=0.65,
    )
    store = AppointmentStore(settings)
    return AgentGraphRunner(settings=settings, kb=DummyKB(), appointment_store=store)


def _ensure_open_slot(store: AppointmentStore) -> str:
    slots = store.list_open_slots(limit=1)
    if slots:
        return slots[0]
    with get_db() as db:
        booking = db.query(Booking).filter(Booking.status == "booked").first()
        if booking:
            booking.status = "cancelled"
            db.commit()
    slots = store.list_open_slots(limit=1)
    assert slots
    return slots[0]


def test_llm_router_can_override_keyword_booking_guess(tmp_path: Path, monkeypatch):
    runner = _runner(tmp_path)

    monkeypatch.setattr(
        "core.agent_graph.route_intent",
        lambda settings, session, message: RouteDecision(
            intent="kb_query",
            confidence=0.96,
            reason="General information question, not a booking request.",
        ),
    )

    out = runner.run(
        session_id=f"router-{uuid.uuid4().hex[:8]}",
        message="Do I need an appointment for a renewal?",
    )

    assert out["intent"] == "kb_query"


def test_router_does_not_break_pending_confirmation_flow(tmp_path: Path, monkeypatch):
    runner = _runner(tmp_path)
    session_id = f"router-confirm-{uuid.uuid4().hex[:8]}"

    monkeypatch.setattr(
        "core.agent_graph.route_intent",
        lambda settings, session, message: RouteDecision(
            intent="kb_query",
            confidence=0.99,
            reason="Question-like phrasing.",
        ),
    )

    update_session(
        session_id,
        pending_intent="cancel_appointment",
        awaiting_confirmation=True,
        auth_status="verified",
    )

    out = runner.run(session_id=session_id, message="yes")

    assert out["intent"] == "cancel_appointment"


def test_router_respects_transaction_payload_followup(tmp_path: Path, monkeypatch):
    runner = _runner(tmp_path)
    session_id = f"router-payload-{uuid.uuid4().hex[:8]}"
    open_slot = _ensure_open_slot(runner.appointment_store)
    service_type = open_slot.split("|", 1)[0].strip()

    monkeypatch.setattr(
        "core.agent_graph.route_intent",
        lambda settings, session, message: RouteDecision(
            intent="kb_query",
            confidence=0.93,
            reason="Could be informational.",
        ),
    )

    update_session(
        session_id,
        pending_intent="book_appointment",
        pending_booking_service_type=service_type,
        pending_booking_email="jamie@example.com",
        name="Jamie",
        stage="active",
        active_flow="booking",
        booking_stage="select_slot",
    )

    out = runner.run(session_id=session_id, message="1")

    assert out["intent"] == "book_appointment"
