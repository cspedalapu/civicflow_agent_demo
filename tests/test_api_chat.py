import uuid

from apps.api.main import ChatRequest, chat
from core.session_store import get_session


def test_chat_answers_support_question_when_name_and_question_share_turn(monkeypatch):
    session_id = f"api-chat-{uuid.uuid4().hex[:8]}"
    captured = {}

    def fake_run(session_id: str, message: str):
        captured["session_id"] = session_id
        captured["message"] = message
        return {
            "answer": "For a DL appointment, please bring your required identity and residency documents.",
            "refusal": False,
            "sources": [],
            "best_similarity": 0.72,
            "timings_ms": {},
            "intent": "kb_query",
        }

    monkeypatch.setattr("apps.api.main.graph_runner.run", fake_run)

    out = chat(
        ChatRequest(
            session_id=session_id,
            message="i am chandra, i need more information about documents required for the DL appointment",
        )
    )

    assert captured["session_id"] == session_id
    assert captured["message"] == "i need more information about documents required for the DL appointment"
    assert out["name"] == "chandra"
    assert "identity and residency documents" in out["answer"].lower()
    assert "nice to meet you" not in out["answer"].lower()

    session = get_session(session_id)
    assert session.name == "chandra"
    assert session.stage == "active"


def test_chat_keeps_name_only_turn_as_greeting():
    session_id = f"api-chat-name-{uuid.uuid4().hex[:8]}"

    out = chat(ChatRequest(session_id=session_id, message="i am chandra"))

    assert out["name"] == "chandra"
    assert "nice to meet you" in out["answer"].lower()
