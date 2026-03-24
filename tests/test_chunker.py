from core.chunker import chunk_text, make_chunks

def test_chunk_text_basic():
    text = "a" * 2000
    chunks = chunk_text(text, chunk_size=900, overlap=100)
    assert len(chunks) >= 2
    assert all(len(c) <= 900 for c in chunks)


def test_make_chunks_removes_internal_demo_section():
    md = """
## 1) Official Appointment Policy
Appointments are required for in-office visits.

## 4) Demo Behavior Specification (For Call Center AI)
For the demo, do not claim the appointment was booked on the DPS website.
Suggested disclaimer:
"For the demo, I can capture your details."
""".strip()

    chunks = make_chunks(
        doc_id="demo_doc",
        title="Appointments",
        text=md,
        metadata={"source_type": "md"},
        chunk_size=900,
        overlap=100,
    )

    assert len(chunks) == 1
    assert "appointments are required" in chunks[0].text.lower()
    assert "for the demo" not in chunks[0].text.lower()
