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
