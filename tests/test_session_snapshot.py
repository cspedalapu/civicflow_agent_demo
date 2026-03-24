import uuid

from core.logger import log_chat_event
from core.session_snapshot import build_session_snapshot, get_handoff_queue
from core.session_store import update_session


def test_session_snapshot_tracks_transaction_progress():
    session_id = f"snapshot-{uuid.uuid4().hex[:8]}"

    update_session(
        session_id,
        name="Jordan",
        goal="reschedule_appointment",
        subgoal="confirm_change",
        active_flow="reschedule",
        booking_stage="confirm_change",
        pending_booking_email="jordan@example.com",
        pending_booking_service_type="renewal",
        selected_booking_id="APT-TEST12345",
        selected_slot="renewal | 2026-03-25 10:00",
        awaiting_confirmation=True,
        confirmation_status="pending",
        auth_status="verified",
        last_agent_action="request_reschedule_confirmation",
    )
    log_chat_event(
        {
            "session_id": session_id,
            "question": "Please change my appointment.",
            "answer": "Reply `yes` to confirm the change or `no` to keep the current appointment.",
            "intent": "reschedule_appointment",
        }
    )

    snapshot = build_session_snapshot(session_id)

    assert snapshot["flow_label"] == "Reschedule"
    assert snapshot["transaction"]["headline"] == "Awaiting customer confirmation"
    assert snapshot["transaction"]["progress"] >= 80
    assert "Waiting for the customer to approve" in snapshot["transaction"]["next_step"]
    assert any("Booking ID: APT-TEST12345" in item for item in snapshot["transaction"]["details"])
    assert snapshot["recent_messages"][-1]["role"] == "assistant"


def test_session_snapshot_builds_handoff_brief_and_queue_item():
    session_id = f"handoff-{uuid.uuid4().hex[:8]}"

    update_session(
        session_id,
        name="Riley",
        goal="cancel_appointment",
        subgoal="human_support",
        active_flow="handoff",
        booking_stage="confirm_cancel",
        pending_booking_email="riley@example.com",
        selected_booking_id="APT-HANDOFF1",
        selected_slot="dl_appointment | 2026-04-02 09:00",
        handoff_recommended=True,
        escalation_reason="user_requested_human",
        fallback_reason="pending_confirmation",
        last_agent_action="recommend_handoff",
        auth_status="verified",
    )
    log_chat_event(
        {
            "session_id": session_id,
            "question": "I want a live agent to finish this cancellation.",
            "answer": "A human agent would be the best next step here.",
            "intent": "cancel_appointment",
        }
    )

    snapshot = build_session_snapshot(session_id)
    handoff = snapshot["handoff"]

    assert handoff is not None
    assert handoff["ticket_id"].startswith("HND-")
    assert handoff["status"] == "ready_for_agent"
    assert "customer asked for a human agent" in handoff["reason"].lower()
    assert "booking apt-handoff1" in handoff["summary"].lower()

    queue = get_handoff_queue(limit=10)
    item = next(entry for entry in queue["items"] if entry["session_id"] == session_id)
    assert item["ticket_id"] == handoff["ticket_id"]
    assert "live agent" in item["summary"].lower()
