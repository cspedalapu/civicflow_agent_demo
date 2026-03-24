from core.agent import answer_question
from core.config import Settings


class FakeKB:
    def query(self, query_text: str, top_k: int):
        return {
            "documents": [[
                "Renewal applicants should review required identity and residency documents before the appointment."
            ]],
            "metadatas": [[{"title": "Renewal Requirements"}]],
            "distances": [[0.1]],
        }


class FailingLLM:
    def available(self) -> bool:
        return True

    def generate(self, question: str, evidence: str) -> str:
        raise RuntimeError("simulated llm failure")


def test_answer_question_falls_back_when_llm_fails(monkeypatch):
    monkeypatch.setattr("core.agent.get_llm", lambda settings: FailingLLM())

    settings = Settings(
        use_reranker=False,
        llm_provider="openai",
        openai_api_key="bad-key",
        min_similarity=0.2,
        min_keyword_overlap=0.0,
        high_similarity_override=0.8,
    )

    out = answer_question(settings, FakeKB(), "What documents do I need for renewal?")

    assert out["refusal"] is False
    assert "based on my knowledge base" not in out["answer"].lower()
    assert "required application and proof documents" in out["answer"].lower() or "review the official checklist" in out["answer"].lower()


class MixedKB:
    def query(self, query_text: str, top_k: int):
        return {
            "documents": [[
                "## 4) Demo Behavior Specification\nFor the demo, do not claim that the appointment was booked on the DPS website.",
                "Bring identity and residency documents for your driver license appointment.",
            ]],
            "metadatas": [[
                {"title": "Appointments Demo Notes"},
                {"title": "Driver License Requirements"},
            ]],
            "distances": [[0.1, 0.2]],
        }


def test_answer_question_filters_internal_instructional_hits(monkeypatch):
    monkeypatch.setattr("core.agent.get_llm", lambda settings: FailingLLM())

    settings = Settings(
        use_reranker=False,
        llm_provider="openai",
        openai_api_key="bad-key",
        min_similarity=0.2,
        min_keyword_overlap=0.0,
        high_similarity_override=0.8,
    )

    out = answer_question(settings, MixedKB(), "What documents do I need for a driver license appointment?")

    assert "demo behavior specification" not in out["answer"].lower()
    assert "bring identity and residency documents" in out["answer"].lower()


class NeverUsedKB:
    def query(self, query_text: str, top_k: int):
        raise AssertionError("broad question should clarify before retrieval")


def test_answer_question_clarifies_broad_questions_before_retrieval():
    settings = Settings()

    out = answer_question(settings, NeverUsedKB(), "I have a question about driver license.")

    assert out["clarification"] is True
    assert "driver license" in out["answer"].lower()
