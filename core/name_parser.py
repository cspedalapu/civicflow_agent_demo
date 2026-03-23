from __future__ import annotations
import re
from typing import Optional

# Handles: "my name is John", "I'm John", "I am John", "this is John"
_PATTERNS = [
    re.compile(r"\bmy name is\s+([A-Za-z][A-Za-z\s.'-]{0,40})\b", re.IGNORECASE),
    re.compile(r"\bi am\s+([A-Za-z][A-Za-z\s.'-]{0,40})\b", re.IGNORECASE),
    re.compile(r"\bi'm\s+([A-Za-z][A-Za-z\s.'-]{0,40})\b", re.IGNORECASE),
    re.compile(r"\bthis is\s+([A-Za-z][A-Za-z\s.'-]{0,40})\b", re.IGNORECASE),
]

_NAME_STOPWORDS = {
    "looking",
    "need",
    "want",
    "book",
    "appointment",
    "appointments",
    "schedule",
    "renew",
    "renewal",
    "help",
    "please",
    "service",
    "services",
    "question",
    "questions",
    "for",
    "to",
    "with",
    "about",
    "dl",
    "id",
}

_NON_NAME_TOKENS = _NAME_STOPWORDS | {
    "hi",
    "hello",
    "hey",
    "yo",
    "hola",
    "thanks",
    "thank",
    "okay",
    "ok",
}

_NON_PERSON_IDENTITY_TOKENS = {
    "international",
    "student",
    "customer",
    "applicant",
    "parent",
    "guardian",
    "minor",
    "adult",
    "senior",
    "resident",
    "visitor",
    "immigrant",
    "employee",
    "worker",
    "teacher",
}

def extract_name(text: str) -> Optional[str]:
    if not text:
        return None

    t = text.strip()
    for p in _PATTERNS:
        m = p.search(t)
        if m:
            name = m.group(1).strip()
            cleaned = _clean(name)
            return cleaned or None

    # If user just replies with a short name (1–3 tokens), treat it as name
    # Example: "Chandra", "Appala Naidu"
    tokens = re.findall(r"[A-Za-z][A-Za-z.'-]*", t)
    if 1 <= len(tokens) <= 3 and len(t) <= 30:
        # Ignore generic greetings/intent fragments like "hello" or "looking for dl".
        if tokens[0].lower() in _NON_NAME_TOKENS:
            return None
        cleaned = _clean(" ".join(tokens))
        return cleaned or None

    return None

def _clean(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip()

    # Drop obvious trailing sentence fragments after punctuation.
    name = re.split(r"[,\n!?;]+", name, maxsplit=1)[0].strip()
    parts = re.split(r"\.\s+", name, maxsplit=1)
    if len(parts) > 1 and parts[1]:
        first_tail_word = re.findall(r"[A-Za-z]+", parts[1].lower())
        if first_tail_word and first_tail_word[0] in _NAME_STOPWORDS:
            name = parts[0].strip()

    # Truncate when intent words start after the name.
    tokens = re.findall(r"[A-Za-z][A-Za-z.'-]*", name)
    kept = []
    for tok in tokens:
        if not kept and tok.lower() in _NON_NAME_TOKENS:
            break
        if tok.lower() in _NAME_STOPWORDS and kept:
            break
        kept.append(tok)
        if len(kept) >= 4:
            break
    if kept:
        name = " ".join(kept)
    else:
        return ""

    lowered = [tok.lower() for tok in kept]
    if len(lowered) > 1 and lowered[0] in {"a", "an", "the"}:
        return ""
    if any(tok in _NON_PERSON_IDENTITY_TOKENS for tok in lowered):
        return ""

    # Prevent weird all-caps shouting
    if len(name) >= 2 and name.isupper():
        name = name.title()
    return name[:50]
