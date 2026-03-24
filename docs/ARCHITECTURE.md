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

## Phase 2 Policy Engine
`core/policies.py` is now a first-class policy engine instead of a passive helper.

It evaluates each turn for:
- human handoff requests,
- weak-evidence KB queries that should ask for clarification,
- auth requirements before exposing or mutating bookings,
- pending confirmation gates before destructive actions like cancel/reschedule.

`core/agent_graph.py` enforces those decisions before appointment mutations run, so
policy outcomes can stop, redirect, or defer a flow instead of only logging metadata.

## Appointment Tooling
`core/appointments.py`:
- SQLite-backed appointment store
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
`core/session_store.py` exposes a dataclass facade over SQLite-backed session state:
- `new -> awaiting_name -> active`
- name personalization
- pending booking identity and selected booking metadata
- confirmation, escalation, and auth status used by the policy engine

## Observability
- chat/event logs: `chat_messages` table plus logger history helpers
- optional LangSmith tracing via environment configuration

## GPU Usage
- reranker runs on configured device (`RERANK_DEVICE`, default `cuda`)
