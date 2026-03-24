from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional

from .config import Settings
from .session_store import SessionState

IntentName = str

_VALID_INTENTS = {
    "book_appointment",
    "reschedule_appointment",
    "cancel_appointment",
    "list_appointments",
    "kb_query",
    "smalltalk",
}

_ROUTER_SYSTEM = """You are an intent router for a Texas DPS support assistant.
Choose exactly one intent for the user's latest message.

Valid intents:
- book_appointment
- reschedule_appointment
- cancel_appointment
- list_appointments
- kb_query
- smalltalk

Return strict JSON only with:
{"intent":"...", "confidence":0.0, "reason":"..."}

Routing guidance:
- Use kb_query for document questions, requirements, fees, eligibility, renewal rules, or general information requests.
- Use book_appointment only when the user wants to create or schedule an appointment.
- Use reschedule_appointment only when the user wants to change an existing booking.
- Use cancel_appointment only when the user wants to cancel an existing booking.
- Use list_appointments only when the user wants to check, find, or list an existing booking.
- Use smalltalk only for greetings, thanks, or closing remarks.
- Respect the session context, but do not force the old flow if the latest message clearly changes topic.
"""


@dataclass(frozen=True)
class RouteDecision:
    intent: IntentName
    confidence: float
    source: str = "llm"
    reason: str = ""


def _llm_available(settings: Settings) -> bool:
    provider = settings.llm_provider.lower()
    if provider == "openai":
        return bool(settings.openai_api_key or settings.github_token)
    if provider == "github_models":
        return bool(settings.github_token)
    return False


def _router_model(settings: Settings) -> str:
    return (settings.router_model or settings.llm_model or "").strip()


def _build_openai_client(settings: Settings):
    from openai import OpenAI

    provider = settings.llm_provider.lower()
    if provider == "github_models":
        return OpenAI(
            base_url=settings.github_models_endpoint.rstrip("/"),
            api_key=settings.github_token,
            default_headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": settings.github_api_version,
            },
        )

    base_url = (settings.openai_base_url or "").rstrip("/") or None
    api_key = settings.openai_api_key or settings.github_token
    default_headers = None
    if base_url and "models.github.ai" in base_url:
        default_headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": settings.github_api_version,
        }

    return OpenAI(api_key=api_key, base_url=base_url, default_headers=default_headers)


def _router_user_message(session: SessionState, message: str) -> str:
    return (
        "Session context:\n"
        f"- pending_intent: {session.pending_intent or 'none'}\n"
        f"- active_flow: {session.active_flow or 'none'}\n"
        f"- booking_stage: {session.booking_stage or 'none'}\n"
        f"- awaiting_confirmation: {str(session.awaiting_confirmation).lower()}\n"
        f"- auth_status: {session.auth_status or 'unknown'}\n"
        f"- last_agent_action: {session.last_agent_action or 'none'}\n\n"
        f'Latest user message:\n"{(message or "").strip()}"'
    )


def _parse_router_response(text: str) -> Optional[RouteDecision]:
    raw = (text or "").strip()
    if not raw:
        return None

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None

    intent = str(payload.get("intent") or "").strip()
    if intent not in _VALID_INTENTS:
        return None

    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    confidence = max(0.0, min(confidence, 1.0))
    return RouteDecision(
        intent=intent,
        confidence=confidence,
        source="llm",
        reason=str(payload.get("reason") or "").strip(),
    )


def route_intent(settings: Settings, session: SessionState, message: str) -> Optional[RouteDecision]:
    if not settings.use_llm_router:
        return None
    if not _llm_available(settings):
        return None

    try:
        client = _build_openai_client(settings)
        resp = client.chat.completions.create(
            model=_router_model(settings),
            messages=[
                {"role": "system", "content": _ROUTER_SYSTEM},
                {"role": "user", "content": _router_user_message(session, message)},
            ],
            temperature=0,
            max_tokens=120,
            response_format={"type": "json_object"},
        )
    except Exception:
        return None

    content = (resp.choices[0].message.content or "").strip()
    return _parse_router_response(content)
