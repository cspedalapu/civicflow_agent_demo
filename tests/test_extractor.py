import json
from pathlib import Path

from core.extractor import extract_all, extract_one


def test_extract_one_renders_structured_json(tmp_path: Path):
    src = tmp_path / "facts.json"
    src.write_text(
        json.dumps(
            {
                "title": "DL Appointment Facts",
                "source_url": "https://example.test/appointments",
                "in_office_services": {
                    "appointment_only": True,
                    "same_day_appointments": {
                        "available": True,
                        "notes": "Released throughout the day.",
                    },
                },
                "payment_policy": {
                    "preferred": ["credit card"],
                    "accepted": ["cashier's check"],
                },
            }
        ),
        encoding="utf-8",
    )

    doc = extract_one(src, source_root=tmp_path)

    text = doc.text.lower()
    assert "appointment only" in text
    assert "same day appointments" in text
    assert "payment policy" in text
    assert "credit card" in text
    assert not doc.metadata.get("metadata_only", False)


def test_extract_all_clears_stale_files_and_avoids_doc_id_collisions(tmp_path: Path):
    sources = tmp_path / "sources"
    extracted = tmp_path / "extracted"
    sources.mkdir(parents=True, exist_ok=True)
    extracted.mkdir(parents=True, exist_ok=True)

    (extracted / "stale.json").write_text("{}", encoding="utf-8")
    (sources / "guide.md").write_text("# Guide\nUse this in office.", encoding="utf-8")
    (sources / "guide.json").write_text(
        json.dumps({"title": "Guide JSON", "notes": "Short summary."}),
        encoding="utf-8",
    )

    count = extract_all(sources_dir=sources, extracted_dir=extracted)
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(extracted.glob("*.json"))]
    ids = [d["doc_id"] for d in docs]

    assert count == 2
    assert len(docs) == 2
    assert len(set(ids)) == 2
    assert not (extracted / "stale.json").exists()


def test_extract_one_keeps_notes_and_structured_fields(tmp_path: Path):
    src = tmp_path / "links.json"
    src.write_text(
        json.dumps(
            {
                "title": "Service Links",
                "notes": "Official service catalog.",
                "links": {
                    "renewal": "https://example.test/renewal",
                    "appointments": "https://example.test/scheduler",
                },
            }
        ),
        encoding="utf-8",
    )

    doc = extract_one(src, source_root=tmp_path)
    text = doc.text.lower()
    assert "official service catalog." in text
    assert "additional structured fields" in text
    assert "appointments" in text
