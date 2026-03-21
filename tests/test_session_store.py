import uuid

from core.session_store import get_session, session_to_dict, update_session


def test_session_store_persists_rich_task_state():
    session_id = f"session-{uuid.uuid4().hex[:8]}"

    update_session(
        session_id,
        goal="book_appointment",
        subgoal="select_slot",
        active_flow="booking",
        booking_stage="select_slot",
        last_offered_slots=["renewal | 2026-03-25 09:00", "renewal | 2026-03-25 10:00"],
        selected_slot="renewal | 2026-03-25 09:00",
        selected_booking_id="APT-TEST12345",
        unresolved_question="What documents do I need?",
        confirmation_status="pending",
        awaiting_confirmation=True,
        last_agent_action="offer_slots",
        fallback_reason="low_evidence",
        escalation_reason="user_requested_human",
        handoff_recommended=True,
        auth_status="verified",
    )

    session = get_session(session_id)

    assert session.goal == "book_appointment"
    assert session.subgoal == "select_slot"
    assert session.active_flow == "booking"
    assert session.booking_stage == "select_slot"
    assert session.last_offered_slots == [
        "renewal | 2026-03-25 09:00",
        "renewal | 2026-03-25 10:00",
    ]
    assert session.selected_slot == "renewal | 2026-03-25 09:00"
    assert session.selected_booking_id == "APT-TEST12345"
    assert session.unresolved_question == "What documents do I need?"
    assert session.confirmation_status == "pending"
    assert session.awaiting_confirmation is True
    assert session.last_agent_action == "offer_slots"
    assert session.fallback_reason == "low_evidence"
    assert session.escalation_reason == "user_requested_human"
    assert session.handoff_recommended is True
    assert session.auth_status == "verified"

    payload = session_to_dict(session)
    assert payload["last_offered_slots"][0].startswith("renewal |")
