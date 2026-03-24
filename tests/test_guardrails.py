from core.config import Settings
from core.guardrails import enough_evidence


def test_enough_evidence_considers_more_than_first_hit():
    settings = Settings(
        min_similarity=0.35,
        min_keyword_overlap=0.2,
        high_similarity_override=0.8,
    )
    hits = [
        {"similarity": 0.42, "text": "General office details and hours."},
        {"similarity": 0.55, "text": "Bring identity and residency documents for your driver license appointment."},
    ]

    ok, dbg = enough_evidence(settings, "What documents do I need for a driver license appointment?", hits)

    assert ok is True
    assert dbg["best_similarity"] == 0.55
    assert dbg["keyword_overlap"] > 0.2
