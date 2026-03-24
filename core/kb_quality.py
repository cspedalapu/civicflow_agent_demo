from __future__ import annotations

import re
from typing import Any, Dict, List

_MOJIBAKE_REPLACEMENTS = {
    "â€”": "-",
    "â€“": "-",
    "â€¢": "-",
    "â€œ": '"',
    "â€": '"',
    "â€™": "'",
    "â€˜": "'",
    "\u00a0": " ",
}

_CONTENT_REFERENCE_RE = re.compile(r"\s*:contentReference\[[^\]]+\]\{[^}]+\}")

_INTERNAL_SECTION_MARKERS = (
    "demo behavior specification",
    "for call center ai",
    "calendar event template",
    "for later implementation",
    "suggested disclaimer",
    "do not claim that the appointment was booked",
)

_INTERNAL_LINE_MARKERS = (
    "must share when requested",
    "if a customer requests",
    "the assistant must share both",
    "recommended wording",
    "for the demo,",
    "for the demo ",
    "create a “demo appointment”",
    'create a "demo appointment"',
)


def normalize_kb_text(text: str) -> str:
    cleaned = text or ""
    for src, dest in _MOJIBAKE_REPLACEMENTS.items():
        cleaned = cleaned.replace(src, dest)
    cleaned = _CONTENT_REFERENCE_RE.sub("", cleaned)
    cleaned = cleaned.replace("\r\n", "\n")
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def is_internal_only_text(text: str, title: str = "") -> bool:
    combined = normalize_kb_text(f"{title}\n{text}").lower()
    if any(marker in combined for marker in _INTERNAL_SECTION_MARKERS):
        return True
    if re.search(r"^##\s*4\)", combined, re.MULTILINE):
        return True
    if re.search(r"^###\s*4\.\d+\s+intent:", combined, re.MULTILINE):
        return True
    return False


def infer_content_audience(title: str, text: str) -> str:
    return "internal" if is_internal_only_text(text=text, title=title) else "end_user"


def clean_user_facing_text(text: str) -> str:
    cleaned = normalize_kb_text(text)
    kept_lines: List[str] = []

    for raw in cleaned.splitlines():
        line = raw.strip()
        lower = line.lower()
        if not line:
            kept_lines.append("")
            continue
        if any(marker in lower for marker in _INTERNAL_LINE_MARKERS):
            continue
        if re.match(r"^##\s*4\)", line, re.IGNORECASE):
            continue
        if re.match(r"^###\s*4\.\d+", line, re.IGNORECASE):
            continue
        kept_lines.append(line)

    cleaned = "\n".join(kept_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def filter_user_facing_hits(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filtered: List[Dict[str, Any]] = []
    for hit in hits:
        meta = dict(hit.get("metadata") or {})
        title = str(meta.get("title") or meta.get("doc_id") or "")
        raw_text = str(hit.get("text") or hit.get("preview") or "")
        audience = str(meta.get("content_audience") or "").strip().lower()
        if audience == "internal" or is_internal_only_text(raw_text, title=title):
            continue

        cleaned = clean_user_facing_text(raw_text)
        if not cleaned:
            continue

        item = dict(hit)
        item["text"] = cleaned
        if "preview" in item:
            item["preview"] = cleaned[:400]
        meta["content_audience"] = infer_content_audience(title=title, text=cleaned)
        item["metadata"] = meta
        filtered.append(item)
    return filtered
