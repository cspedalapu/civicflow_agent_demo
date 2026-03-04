# AI Customer Agent (Grounded + Agentic)

Production-style customer agent for Texas DPS Driver License workflows:
- Grounded QA strictly from local `knowledge_base/`
- Appointment booking/cancellation/status flows
- Multi-turn chat with session memory
- Phone-call webhook path (Twilio-compatible)
- LangGraph orchestration, optional LangSmith tracing

Chunking + embedding + Chroma retrieval pipeline is preserved and reused.

## Features
- `RAG` pipeline:
  - Extract -> chunk -> index -> embed -> retrieve
  - Refusal when evidence is weak
- `Agentic` orchestration:
  - Intent routing (`kb_query`, `book_appointment`, `cancel_appointment`, `list_appointments`)
  - Tool-backed appointment operations
- `Channels`:
  - REST chat API
  - Streamlit dashboard
  - Voice webhook endpoint

## Repo Layout
```text
apps/
  api/main.py
  dashboard/app.py
core/
  agent.py              # grounded QA + guardrails
  agent_graph.py        # LangGraph orchestration
  appointments.py       # booking tool store
  pipeline.py           # extract/chunk/embed ingest
  retriever.py
  vectorstore.py
knowledge_base/
  sources/              # authoritative KB files
  extracted/            # generated
  index/                # generated
  vector_store_chroma/  # generated
data/
  appointments.json     # generated
```

## Quickstart
1. Create venv and install:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Configure:
```bash
copy .env.example .env
```

3. Build KB index:
```bash
python scripts/ingest_kb.py
```

4. Run API:
```bash
python scripts/run_api.py
```

5. Run Dashboard:
```bash
streamlit run apps/dashboard/app.py
```

## Key API Endpoints
- `POST /chat`
- `POST /ingest`
- `POST /retrieve`
- `GET /appointments/slots`
- `POST /appointments/book`
- `POST /appointments/cancel/{booking_id}`
- `POST /voice/twilio`

## CUDA Notes
- Set `RERANK_DEVICE=cuda` in `.env`.
- Ensure CUDA-enabled PyTorch is installed.
- Reranker is loaded as `CrossEncoder(..., device="cuda")`.

## LangSmith Notes
- Set:
  - `LANGCHAIN_TRACING_V2=true`
  - `LANGSMITH_API_KEY=...`
  - `LANGCHAIN_PROJECT=ai-customer-agent`
- LangGraph execution traces will appear in LangSmith.
