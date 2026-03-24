from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List

from .config import Settings


class LLMClient:
    def __init__(self, settings: Settings, system_prompt_path: Path, user_template_path: Path):
        self.settings = settings
        self.system = system_prompt_path.read_text(encoding="utf-8")
        self.user_template = user_template_path.read_text(encoding="utf-8")

    def available(self) -> bool:
        provider = self.settings.llm_provider.lower()
        if provider == "openai":
            return bool(self.settings.openai_api_key or self.settings.github_token)
        if provider == "github_models":
            return bool(self.settings.github_token)
        return False

    def generate(self, question: str, evidence: str) -> str:
        provider = self.settings.llm_provider.lower()
        if provider == "openai":
            return self._openai(question, evidence)
        if provider == "github_models":
            return self._github_models(question, evidence)
        raise ValueError(f"Unsupported LLM_PROVIDER: {self.settings.llm_provider}")

    def _openai(self, question: str, evidence: str) -> str:
        from openai import OpenAI

        base_url = (self.settings.openai_base_url or "").rstrip("/") or None
        api_key = self.settings.openai_api_key or self.settings.github_token
        if not api_key:
            raise ValueError("Missing OPENAI_API_KEY (or GITHUB_TOKEN for GitHub Models).")

        default_headers = None
        if base_url and "models.github.ai" in base_url:
            default_headers = {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": self.settings.github_api_version,
            }

        client = OpenAI(api_key=api_key, base_url=base_url, default_headers=default_headers)
        user = self.user_template.format(question=question, evidence=evidence)

        resp = client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": self.system},
                {"role": "user", "content": user},
            ],
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()

    def _github_models(self, question: str, evidence: str) -> str:
        from openai import OpenAI

        client = OpenAI(
            base_url=self.settings.github_models_endpoint.rstrip("/"),
            api_key=self.settings.github_token,
            default_headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": self.settings.github_api_version,
            },
        )
        user = self.user_template.format(question=question, evidence=evidence)

        resp = client.chat.completions.create(
            model=self.settings.llm_model,
            messages=[
                {"role": "system", "content": self.system},
                {"role": "user", "content": user},
            ],
            temperature=self.settings.llm_temperature,
            max_tokens=self.settings.llm_max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()


def extractive_fallback(question: str, hits: List[Dict[str, Any]]) -> str:
    if not hits:
        return "I don't have that information in my knowledge base."

    def _lead_for_question(text: str) -> str:
        q = (text or "").strip().lower()
        if any(token in q for token in ("document", "documents", "what to bring", "carry", "bring")):
            return (
                "For this DPS request, you should bring the required application and proof documents, and review the "
                "official checklist before visiting the office."
            )
        if any(token in q for token in ("book", "schedule", "appointment")):
            return "For appointments, use the official DPS appointment information page and scheduler for the next step."
        if "renew" in q and "online" in q:
            return "Texas DPS does allow online renewal for eligible applicants."
        if "cdl" in q or "commercial" in q:
            return "CDL requirements depend on the license class and endorsements you need."
        if "state id" in q or "identification card" in q or "id card" in q:
            return "For a Texas ID card, DPS expects the required identity and residency documents at the office visit."
        return "Here is the best answer I could assemble from the DPS knowledge base."

    def _clean_text(text: str) -> str:
        cleaned = (text or "").replace("“", '"').replace("”", '"').replace("’", "'")
        cleaned = re.sub(r"https?://\S+", "", cleaned)
        pieces: List[str] = []
        for raw in cleaned.splitlines():
            line = raw.strip(" -\t")
            lower = line.lower()
            if not line:
                continue
            if lower.startswith(("##", "#", "q1.", "q2.", "q3.", "related services", "official links", "recommended wording")):
                continue
            if len(line) < 20:
                continue
            pieces.append(line)
        return " ".join(pieces)

    def _supporting_sentences(items: List[Dict[str, Any]], limit: int = 2) -> List[str]:
        sentences: List[str] = []
        seen: set[str] = set()
        for item in items[:3]:
            cleaned = _clean_text(item.get("text") or "")
            for piece in re.split(r"(?<=[.!?])\s+", cleaned):
                sentence = piece.strip()
                normalized = sentence.lower()
                if len(sentence) < 40:
                    continue
                if normalized in seen or normalized.endswith("?"):
                    continue
                if normalized.startswith(("if a customer requests", "checklist pdf", "appointment scheduler", "appointment information page")):
                    continue
                seen.add(normalized)
                sentences.append(sentence)
                if len(sentences) >= limit:
                    return sentences
        return sentences

    lead = _lead_for_question(question)
    support = _supporting_sentences(hits, limit=2)
    if not support:
        return lead

    merged = " ".join(support)
    if merged.lower() in lead.lower():
        return lead
    return f"{lead}\n\n{merged}"
