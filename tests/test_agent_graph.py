from pathlib import Path

from core.agent_graph import AgentGraphRunner
from core.appointments import AppointmentStore
from core.config import Settings


class DummyKB:
    def query(self, query_text: str, top_k: int):
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}


def _runner(tmp_path: Path) -> AgentGraphRunner:
    settings = Settings(appointments_path=str(tmp_path / "appointments.json"))
    store = AppointmentStore(settings)
    return AgentGraphRunner(settings=settings, kb=DummyKB(), appointment_store=store)


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
    session_id = "s3"

    first = runner.run(session_id=session_id, message="I am John, want to book an appointment")
    assert first["intent"] == "book_appointment"
    assert "phone number" in first["answer"].lower()

    second = runner.run(session_id=session_id, message="3456789090")
    assert second["intent"] == "book_appointment"
    assert "what service" in second["answer"].lower()

    third = runner.run(session_id=session_id, message="renewal")
    assert third["intent"] == "book_appointment"
    assert "please pick one of these available slots" in third["answer"].lower()

    slot = runner.appointment_store.list_open_slots(service_type="renewal", limit=1)[0]
    fourth = runner.run(session_id=session_id, message=slot)
    assert fourth["intent"] == "book_appointment"
    assert "appointment is confirmed" in fourth["answer"].lower()
    assert "booking id:" in fourth["answer"].lower()
