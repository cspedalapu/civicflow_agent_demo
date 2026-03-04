# Architecture

## Objective
Deliver an industry-grade customer agent for DL/ID support that can:
- answer grounded KB questions,
- execute appointment booking flows,
- support chat and phone channels.

## Data Pipeline (unchanged)
1. `knowledge_base/sources` -> extraction (`core/extractor.py`)
2. chunking (`core/chunker.py`)
3. Chroma upsert (`core/vectorstore.py`)
4. retrieval + guardrails (`core/retriever.py`, `core/guardrails.py`)
5. answer generation (`core/agent.py`)

## Agentic Layer
`core/agent_graph.py` builds a LangGraph state machine:
- `route` intent
- `kb_query` -> grounded answer tool
- `book_appointment` -> booking tool
- `cancel_appointment` -> booking tool
- `list_appointments` -> booking lookup tool

This keeps retrieval and transactional workflows separated and testable.

## Appointment Tooling
`core/appointments.py`:
- persistent JSON store (`data/appointments.json`)
- open-slot listing
- create booking
- cancel booking
- list bookings by phone number

## API Surface
`apps/api/main.py`:
- `/chat` -> session-aware orchestration
- `/appointments/*` -> direct booking APIs
- `/voice/twilio` -> telephony webhook
- `/ingest`, `/retrieve`, `/history/{session_id}`

## Session Model
`core/session_store.py` maintains in-memory session state:
- `new -> awaiting_name -> active`
- name personalization
- safe lock semantics for concurrent access

## Observability
- chat/event logs: `data/conversations.jsonl`
- optional LangSmith tracing via environment configuration

## GPU Usage
- reranker runs on configured device (`RERANK_DEVICE`, default `cuda`)
