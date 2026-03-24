import uuid

from core.handoff import claim_handoff, ensure_handoff, resolve_handoff
from core.session_store import get_session, update_session


def test_handoff_can_be_claimed_and_resolved():
    session_id = f"handoff-flow-{uuid.uuid4().hex[:8]}"
    update_session(
        session_id,
        handoff_recommended=True,
        escalation_reason="user_requested_human",
        active_flow="handoff",
        subgoal="human_support",
    )

    created = ensure_handoff(session_id, reason="user_requested_human")
    assert created["handoff_ticket_id"].startswith("HND-")
    assert created["handoff_status"] == "recommended"

    claimed = claim_handoff(session_id, assignee="Case Worker")
    assert claimed["handoff_status"] == "claimed"
    assert claimed["handoff_assignee"] == "Case Worker"
    assert claimed["handoff_claimed_at"] is not None

    resolved = resolve_handoff(session_id, assignee="Case Worker")
    assert resolved["handoff_status"] == "resolved"
    assert resolved["handoff_assignee"] == "Case Worker"
    assert resolved["handoff_resolved_at"] is not None
    assert resolved["handoff_recommended"] is False

    session = get_session(session_id)
    assert session.handoff_status == "resolved"
    assert session.handoff_assignee == "Case Worker"
