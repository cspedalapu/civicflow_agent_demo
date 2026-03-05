from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.responses import Response
from pydantic import BaseModel

from core.agent import answer_question
from core.agent_graph import AgentGraphRunner
from core.appointments import AppointmentRequest, AppointmentStore
from core.config import get_settings
from core.database import init_db, seed_default_slots, get_db, ChatMessage, SessionModel, Booking
from core.logger import ensure_session_id, log_chat_event, get_chat_history
from core.name_parser import extract_name
from core.pipeline import ingest
from core.session_store import get_session, update_session
from core.vectorstore import ChromaKB

load_dotenv()

# ── Initialise database ─────────────────────────────────────────────────
init_db()
seed_default_slots()

app = FastAPI(title="civicflow_agent_demo API", version="0.3.0")
settings = get_settings()
kb = ChromaKB(settings)
appointment_store = AppointmentStore(settings)
graph_runner = AgentGraphRunner(settings=settings, kb=kb, appointment_store=appointment_store)


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str


class BookingRequest(BaseModel):
    service_type: str
    customer_name: str
    customer_phone: str
    slot: str
    notes: str = ""


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest")
def ingest_endpoint() -> Dict[str, Any]:
    result = ingest(settings)
    return {"status": "ok", "result": result}


def _greet_ask_name() -> str:
    return (
        "Hi, welcome to the Texas Department of Public Safety virtual assistant.\n\n"
        "I can help with DL and ID questions, and appointment booking.\n"
        "May I know your name?"
    )


def _is_explicit_name_message(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(
        phrase in t
        for phrase in (
            "my name is",
            "i am ",
            "i'm ",
            "this is ",
            "call me ",
        )
    )


@app.post("/chat")
def chat(req: ChatRequest) -> Dict[str, Any]:
    session_id = ensure_session_id(req.session_id)
    msg = (req.message or "").strip()
    session = get_session(session_id)

    if session.stage == "new":
        update_session(session_id, stage="awaiting_name")
        out = {
            "answer": _greet_ask_name(),
            "refusal": False,
            "session_id": session_id,
            "stage": "awaiting_name",
        }
        log_chat_event({"session_id": session_id, "stage": "awaiting_name", "question": msg, "answer": out["answer"]})
        return out

    if session.stage == "awaiting_name" and not session.name:
        name = extract_name(msg)
        if not name:
            out = {
                "answer": "I didn't catch your name. What should I call you?",
                "refusal": False,
                "session_id": session_id,
                "stage": "awaiting_name",
            }
            log_chat_event({"session_id": session_id, "stage": "awaiting_name", "question": msg, "answer": out["answer"]})
            return out
        update_session(session_id, name=name, stage="active")
        out = {
            "answer": f"Thanks, {name}. How can I help you today?",
            "refusal": False,
            "session_id": session_id,
            "stage": "active",
            "name": name,
        }
        log_chat_event({"session_id": session_id, "stage": "active", "name": name, "question": msg, "answer": out["answer"]})
        return out

    maybe_name = extract_name(msg)
    if maybe_name and _is_explicit_name_message(msg):
        update_session(session_id, name=maybe_name)
    session = get_session(session_id)

    if settings.use_langgraph:
        out = graph_runner.run(session_id=session_id, message=msg)
    else:
        out = answer_question(settings, kb, msg)
    out["session_id"] = session_id
    out["stage"] = session.stage
    if session.name:
        out["name"] = session.name
        if out.get("answer"):
            out["answer"] = f"{session.name}, {out['answer']}"

    log_chat_event(
        {
            "session_id": session_id,
            "stage": session.stage,
            "name": session.name,
            "question": msg,
            "answer": out.get("answer"),
            "refusal": out.get("refusal"),
            "best_similarity": out.get("best_similarity"),
            "sources": out.get("sources"),
            "intent": out.get("intent"),
        }
    )
    return out


@app.post("/appointments/book")
def book_appointment(req: BookingRequest) -> Dict[str, Any]:
    booking = appointment_store.create_booking(
        AppointmentRequest(
            service_type=req.service_type,
            customer_name=req.customer_name,
            customer_phone=req.customer_phone,
            slot=req.slot,
            notes=req.notes,
        )
    )
    return {"status": "ok", "booking": booking}


@app.get("/appointments/slots")
def list_slots(service_type: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
    slots = appointment_store.list_open_slots(service_type=service_type, limit=limit)
    return {"slots": slots}


@app.post("/appointments/cancel/{booking_id}")
def cancel_slot(booking_id: str) -> Dict[str, Any]:
    ok = appointment_store.cancel_booking(booking_id)
    return {"status": "ok" if ok else "not_found", "booking_id": booking_id}


@app.post("/retrieve")
def retrieve_debug(req: ChatRequest) -> Dict[str, Any]:
    from core.retriever import retrieve

    hits = retrieve(settings, kb, req.message)
    out = []
    for h in hits[:5]:
        out.append(
            {
                "similarity": h.get("similarity"),
                "distance": h.get("distance"),
                "title": (h.get("metadata") or {}).get("title"),
                "doc_id": (h.get("metadata") or {}).get("doc_id"),
                "preview": (h.get("text") or "")[:400],
            }
        )
    return {"hits": out}


@app.get("/history/{session_id}")
def history(session_id: str, limit: int = 50) -> Dict[str, Any]:
    events = get_chat_history(session_id, limit=limit)
    return {"events": events}


@app.get("/stats")
def stats() -> Dict[str, Any]:
    """Dashboard analytics: counts of sessions, messages, bookings."""
    with get_db() as db:
        total_sessions = db.query(SessionModel).count()
        total_messages = db.query(ChatMessage).count()
        total_bookings = db.query(Booking).filter(Booking.status == "booked").count()
        total_cancelled = db.query(Booking).filter(Booking.status == "cancelled").count()
    return {
        "total_sessions": total_sessions,
        "total_messages": total_messages,
        "active_bookings": total_bookings,
        "cancelled_bookings": total_cancelled,
    }


@app.post("/voice/twilio")
def voice_twilio(
    CallSid: str = Form(default=""),
    SpeechResult: str = Form(default=""),
    From: str = Form(default=""),
) -> Response:
    session_id = CallSid or ensure_session_id(None)
    user_text = SpeechResult.strip() or "hello"
    result = graph_runner.run(session_id=session_id, message=f"{user_text} phone:{From}")
    answer = result.get("answer", "I don't have that information in my knowledge base.")

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Say>{_xml_escape(answer)}</Say>"
        "<Gather input=\"speech\" method=\"POST\" action=\"/voice/twilio\" speechTimeout=\"auto\">"
        "<Say>Please continue.</Say>"
        "</Gather>"
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")


def _xml_escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
