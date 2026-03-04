# civicflow_agent_demo

Industry-style, grounded customer support agent for Driver License and State ID workflows.

## What This Project Does
- Answers user questions from local Knowledge Base only (`knowledge_base/sources`).
- Handles appointment lifecycle flows:
  - book
  - cancel
  - list by phone
- Supports multi-turn chat, session state, and phone webhook entrypoint.
- Uses LangGraph for agent orchestration and optional LangSmith tracing.

## Core Capabilities
- Grounded RAG pipeline:
  - extract -> chunk -> index -> embed -> retrieve -> answer
- Guardrails:
  - refusal on weak evidence
  - clarifying questions on partially relevant evidence
- Agentic routing:
  - `kb_query`
  - `book_appointment`
  - `cancel_appointment`
  - `list_appointments`

## Tech Stack
- Python, FastAPI, Streamlit
- ChromaDB (vector store)
- Sentence Transformers + optional cross-encoder reranker (CUDA-ready)
- LangGraph / LangSmith

## Repository Structure
```text
apps/
  api/main.py                  # FastAPI service
  dashboard/app.py             # Streamlit UI
core/
  pipeline.py                  # ingest pipeline
  extractor.py                 # source extraction
  chunker.py                   # chunk generation
  vectorstore.py               # Chroma wrapper
  retriever.py                 # similarity retrieval
  guardrails.py                # relevance checks
  agent.py                     # grounded answer generation
  agent_graph.py               # LangGraph orchestration
  appointments.py              # booking store/tooling
knowledge_base/
  sources/                     # authoritative KB docs (tracked)
  extracted/                   # generated (ignored, .gitkeep)
  index/                       # generated (ignored, .gitkeep)
  vector_store_chroma/         # generated (ignored, .gitkeep)
scripts/
  ingest_kb.py
  run_api.py
  run_dashboard.py
```

## Prerequisites
- Python 3.10+
- `pip`
- (Optional) CUDA-enabled GPU for reranker acceleration

## Setup
### 1) Create virtual environment and install dependencies
Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS/Linux:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure environment
Windows:
```powershell
copy .env.example .env
```

macOS/Linux:
```bash
cp .env.example .env
```

Then update `.env` values (`OPENAI_API_KEY`, model/provider, reranker, tracing).

### 3) Build KB index
```bash
python scripts/ingest_kb.py
```

## Run the Application
### Run API server
```bash
python scripts/run_api.py
```
Default URL: `http://127.0.0.1:8000`

### Run dashboard
```bash
python scripts/run_dashboard.py
```
or
```bash
streamlit run apps/dashboard/app.py
```

## Test Commands
Run unit tests:
```bash
python -m pytest -q
```

## API Usage (Examples)
### Health check
```bash
curl http://127.0.0.1:8000/health
```

### Chat
```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": null, \"message\": \"How do I renew my DL?\"}"
```

### Ingest / rebuild index
```bash
curl -X POST http://127.0.0.1:8000/ingest
```

### List appointment slots
```bash
curl "http://127.0.0.1:8000/appointments/slots?service_type=dl_appointment&limit=5"
```

### Book appointment
```bash
curl -X POST http://127.0.0.1:8000/appointments/book \
  -H "Content-Type: application/json" \
  -d "{\"service_type\":\"dl_appointment\",\"customer_name\":\"Alex Doe\",\"customer_phone\":\"5125551212\",\"slot\":\"dl_appointment | 2026-03-05 09:00\"}"
```

### Cancel appointment
```bash
curl -X POST http://127.0.0.1:8000/appointments/cancel/APT-XXXXXXXXXX
```

## CUDA Configuration
Set in `.env`:
```dotenv
USE_RERANKER=true
RERANK_DEVICE=cuda
```

Verify PyTorch CUDA:
```bash
python -c "import torch; print(torch.cuda.is_available())"
```

## Observability (LangSmith)
Set in `.env`:
```dotenv
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=civicflow_agent_demo
LANGSMITH_API_KEY=your_key_here
```

## Security and Data Handling
- `.env` is ignored from git.
- Generated vector DB and runtime data are ignored from git.
- Keep production secrets in secret manager or CI/CD vault, not in source control.

## Operational Notes
- Re-run `scripts/ingest_kb.py` after KB content updates.
- Appointment records are stored in `data/appointments.json` (runtime file).

## Demo
1. Start API:
```bash
python scripts/run_api.py
```
2. Start dashboard (new terminal):
```bash
python scripts/run_dashboard.py
```
3. Demo flow:
- Open dashboard and ask a DL question.
- Ask to book an appointment.
- Select a slot and confirm booking.
- Query booking status using phone number.
- Cancel the booking using booking ID.
