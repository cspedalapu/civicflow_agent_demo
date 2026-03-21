from pathlib import Path
import uuid

from core.agent_graph import AgentGraphRunner
from core.appointments import AppointmentStore
from core.config import Settings
from core.database import Booking, get_db
from core.session_store import update_session


class DummyKB:
    def query(self, query_text: str, top_k: int):
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}


def _runner(tmp_path: Path) -> AgentGraphRunner:
    settings = Settings(appointments_path=str(tmp_path / "appointments.json"))
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


def test_cancel_routes_before_book(tmp_path: Path):
    runner = _runner(tmp_path)
    out = runner.run(session_id="s1", message="please cancel appointment APT-1234567890")
    assert out["intent"] == "cancel_appointment"


def test_list_route(tmp_path: Path):
    runner = _runner(tmp_path)
    out = runner.run(session_id="s2", message="show my appointment using 5125551212")
    assert out["intent"] == "list_appointments"


def test_booking_flow_continues_across_turns(tmp_path: Path):
    runner = _runner(tmp_path)
    session_id = f"s3-{uuid.uuid4().hex[:8]}"
    open_slot = _ensure_open_slot(runner.appointment_store)
    service_type = open_slot.split("|", 1)[0].strip()

    first = runner.run(session_id=session_id, message="I am John, want to book an appointment")
    assert first["intent"] == "book_appointment"
    assert "email address" in first["answer"].lower()

    second = runner.run(session_id=session_id, message="john@example.com")
    assert second["intent"] == "book_appointment"
    assert "what service" in second["answer"].lower()

    third = runner.run(session_id=session_id, message=service_type)
    assert third["intent"] == "book_appointment"
    assert "please pick one of these available slots" in third["answer"].lower()
    assert "1." in third["answer"]

    fourth = runner.run(session_id=session_id, message="1")
    assert fourth["intent"] == "book_appointment"
    assert "appointment is confirmed" in fourth["answer"].lower()
    assert "booking id:" in fourth["answer"].lower()


def test_booking_accepts_datetime_only_slot_selection(tmp_path: Path):
    runner = _runner(tmp_path)
    session_id = f"s4-{uuid.uuid4().hex[:8]}"
    open_slot = _ensure_open_slot(runner.appointment_store)
    service_type = open_slot.split("|", 1)[0].strip()
    dt_only = open_slot.split("|", 1)[1].strip()

    runner.run(session_id=session_id, message="My name is Jamie, I need an appointment")
    runner.run(session_id=session_id, message="jamie@example.com")
    runner.run(session_id=session_id, message=service_type)
    out = runner.run(session_id=session_id, message=dt_only)

    assert out["intent"] == "book_appointment"
    assert "appointment is confirmed" in out["answer"].lower()


def test_booking_accepts_letter_choice(tmp_path: Path):
    runner = _runner(tmp_path)
    session_id = f"s4b-{uuid.uuid4().hex[:8]}"
    open_slot = _ensure_open_slot(runner.appointment_store)
    service_type = open_slot.split("|", 1)[0].strip()

    runner.run(session_id=session_id, message="My name is Jamie, I need an appointment")
    runner.run(session_id=session_id, message="jamie@example.com")
    options = runner.run(session_id=session_id, message=service_type)

    assert "(A)" in options["answer"]
    out = runner.run(session_id=session_id, message="I will go with option A")

    assert out["intent"] == "book_appointment"
    assert "appointment is confirmed" in out["answer"].lower()


def test_booking_accepts_natural_day_time_reply(tmp_path: Path):
    runner = _runner(tmp_path)
    session_id = f"s4c-{uuid.uuid4().hex[:8]}"
    open_slot = _ensure_open_slot(runner.appointment_store)
    service_type = open_slot.split("|", 1)[0].strip()
    slot_dt = open_slot.split("|", 1)[1].strip()
    date_part, time_part = slot_dt.split(" ")
    day = str(int(date_part.split("-")[2]))

    runner.run(session_id=session_id, message="My name is Jamie, I need an appointment")
    runner.run(session_id=session_id, message="jamie@example.com")
    runner.run(session_id=session_id, message=service_type)
    out = runner.run(
        session_id=session_id,
        message=f"On {day}, {time_part} is best for me.",
    )

    assert out["intent"] == "book_appointment"
    assert "appointment is confirmed" in out["answer"].lower()


def test_booking_no_slots_resets_service_selection(tmp_path: Path):
    runner = _runner(tmp_path)
    session_id = f"s5-{uuid.uuid4().hex[:8]}"

    # Force no-slot condition for any service query.
    runner.appointment_store.list_open_slots = lambda service_type=None, limit=10: []  # type: ignore[method-assign]

    runner.run(session_id=session_id, message="My name is Chris and I need an appointment")
    runner.run(session_id=session_id, message="chris@example.com")
    out1 = runner.run(session_id=session_id, message="renewal")
    assert "could not find open slots" in out1["answer"].lower()

    # After no slots, next message should re-prompt for service choice, not repeat stale no-slot loop.
    out2 = runner.run(session_id=session_id, message="what other services do you provide")
    assert "what service do you need an appointment for" in out2["answer"].lower()


def test_booking_allows_side_kb_question(tmp_path: Path):
    runner = _runner(tmp_path)
    session_id = f"s8-{uuid.uuid4().hex[:8]}"

    # Force no-slot condition so flow remains in booking mode.
    runner.appointment_store.list_open_slots = lambda service_type=None, limit=10: []  # type: ignore[method-assign]

    runner.run(session_id=session_id, message="My name is Chris and I need an appointment")
    runner.run(session_id=session_id, message="chris@example.com")
    runner.run(session_id=session_id, message="renewal")

    out = runner.run(session_id=session_id, message="what documents should I carry for appointment")
    assert out["intent"] == "kb_query"


def test_booking_allows_side_kb_question_with_service_wording(tmp_path: Path):
    runner = _runner(tmp_path)
    session_id = f"s9-{uuid.uuid4().hex[:8]}"

    runner.run(session_id=session_id, message="My name is Chandra and I want to book a renewal appointment")
    runner.run(session_id=session_id, message="chandra@example.com")

    out = runner.run(
        session_id=session_id,
        message="Before that I want to know what documents I need for the renewal.",
    )
    assert out["intent"] == "kb_query"


def test_smalltalk_thanks_does_not_trigger_kb_clarification(tmp_path: Path):
    runner = _runner(tmp_path)
    out = runner.run(session_id=f"s6-{uuid.uuid4().hex[:8]}", message="thank you")
    assert out["intent"] == "smalltalk"
    assert "you're welcome" in out["answer"].lower()


def test_smalltalk_greeting_with_name(tmp_path: Path):
    runner = _runner(tmp_path)
    session_id = f"s7-{uuid.uuid4().hex[:8]}"
    update_session(session_id, name="Alex", stage="active", pending_intent=None)
    out = runner.run(session_id=session_id, message="hello")
    assert out["intent"] == "smalltalk"
    assert "hi alex" in out["answer"].lower()
