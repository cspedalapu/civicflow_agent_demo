from pathlib import Path

from core.agent_graph import AgentGraphRunner
from core.appointments import AppointmentStore
from core.config import Settings


class DummyKB:
    pass


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
