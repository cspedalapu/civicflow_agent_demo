from core.policies import evaluate_policy
from core.session_store import SessionState


def test_policy_marks_user_requested_handoff():
    decision = evaluate_policy(
        session=SessionState(session_id="s1"),
        message="Please connect me to a live agent.",
        intent="kb_query",
    )

    assert decision.handoff_recommended is True
    assert decision.escalate is True
    assert "USER_REQUESTED_HUMAN" in decision.reason_codes


def test_policy_requires_auth_for_reschedule_without_identity():
    decision = evaluate_policy(
        session=SessionState(session_id="s2"),
        message="change my appointment",
        intent="reschedule_appointment",
    )

    assert decision.needs_auth is True
    assert decision.tool_allowed is False
    assert "MISSING_AUTH" in decision.reason_codes


def test_policy_requests_clarification_for_low_evidence_kb_query():
    decision = evaluate_policy(
        session=SessionState(session_id="s3"),
        message="What are the rules?",
        intent="kb_query",
        best_similarity=0.1,
    )

    assert decision.needs_clarification is True
    assert decision.next_action == "clarify"
    assert "LOW_EVIDENCE" in decision.reason_codes


def test_policy_uses_configurable_clarify_threshold():
    decision = evaluate_policy(
        session=SessionState(session_id="s3b"),
        message="What are the rules?",
        intent="kb_query",
        best_similarity=0.3,
        clarify_min_similarity=0.35,
    )

    assert decision.needs_clarification is True
    assert decision.next_action == "clarify"


def test_policy_blocks_tool_use_when_confirmation_pending():
    decision = evaluate_policy(
        session=SessionState(session_id="s4", awaiting_confirmation=True, auth_status="verified"),
        message="please wait",
        intent="cancel_appointment",
    )

    assert decision.needs_confirmation is True
    assert decision.tool_allowed is False
    assert "PENDING_CONFIRMATION" in decision.reason_codes


def test_policy_allows_confirmed_action_after_yes_reply():
    decision = evaluate_policy(
        session=SessionState(session_id="s5", awaiting_confirmation=True, auth_status="verified"),
        message="yes do it",
        intent="cancel_appointment",
    )

    assert decision.needs_confirmation is False
    assert decision.confirmation_resolution == "approved"
    assert decision.next_action == "proceed"
    assert "USER_CONFIRMED" in decision.reason_codes


def test_policy_captures_declined_confirmation():
    decision = evaluate_policy(
        session=SessionState(session_id="s6", awaiting_confirmation=True, auth_status="verified"),
        message="no keep it",
        intent="reschedule_appointment",
    )

    assert decision.confirmation_resolution == "declined"
    assert decision.next_action == "cancel"
    assert "USER_DECLINED" in decision.reason_codes
