# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

Costmate is an AI-powered construction **door & window takeoff** tool. Users upload
architectural floor-plan PDFs, door/window schedule sheets, and a spec document; a
LangGraph-orchestrated vision-language-model (VLM) pipeline extracts every opening,
cross-checks the schedule against the plans, pauses for human QA, then produces a
multi-sheet Excel schedule and a color-annotated PDF plan.

> **Scope note:** `README.md` / `architecture.md` / `pipeline_architecture.md` describe a
> broader "civil BOQ + cost estimate" product. The code that actually runs today performs
> **door/window takeoff only** — there is no civil-quantities or pricing stage. Trust the
> code over the docs (see "Known drift" below).

## Repository layout

- `Backend/` — Python + FastAPI API and the LangGraph agent pipeline
- `Frontend/` — Next.js 16 / React 19 web app
- `Assets/` — real project inputs & ground-truth outputs (Morgan Stanley, Yale, …); not code
- `README.md`, `architecture.md`, `pipeline_architecture.md` — design docs (partially stale)

## Commands

### Backend (run from `Backend/`)
- Setup: `python -m venv venv && venv\Scripts\activate` then `pip install -r requirements.txt`
- Dev server: `uvicorn app.main:app --reload` (listens on :8000)
- Migrations: `alembic upgrade head` (`Backend/alembic.ini`). Note: startup `init_db()` also
  auto-creates tables via `Base.metadata.create_all`.
- Requires Python ≥ 3.10 and a running PostgreSQL.
- No test suite yet (`pytest` is a dev dependency but there are no `test_*.py` files).

### Frontend (run from `Frontend/`)
- Setup: `npm install`
- `npm run dev` (http://localhost:3000) · `npm run build` · `npm start` · `npm run lint`

## Configuration (`Backend/.env`)

Loaded via pydantic-settings — see `Backend/app/config.py` (the source of truth):
- `OPENROUTER_API_KEY` (required), `OPENROUTER_BASE_URL`,
  `MODEL_NAME` (default `qwen/qwen3-vl-235b-a22b-instruct`)
- `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB`
- `SMTP_*` (OTP email), `GOOGLE_CLIENT_ID` (OAuth), `CLOUDINARY_*` (file storage)

⚠️ `Backend/.env.example` is **stale** — it lists Ollama vars and `DSR_PATH`; the README
mentions `DATABASE_URL`. The code uses OpenRouter + discrete `POSTGRES_*` vars instead.

Frontend: `Frontend/.env.local` holds `NEXT_PUBLIC_GOOGLE_CLIENT_ID`; the backend base URL is
configured in `Frontend/src/lib/api.ts`.

## Architecture

### Pipeline (LangGraph)
Orchestrator `Backend/app/services/graph/graph.py` builds a `StateGraph` over the
`CostmateState` TypedDict (`app/services/graph/state.py`), compiled with `MemorySaver`
checkpointing and `interrupt_before=["interrupt_node"]` (the human gate).

```
START → specifications_analyzer → schedule_parser → ocr_consensus
      → cv_detector → reconciliation → interrupt_node   [PAUSE for QA]
interrupt_node → excel_writer     → END
interrupt_node → plan_annotation  → END
```

Agent nodes in `Backend/app/services/agents/`:
- **Layer 1** `layer1_schedule/` — `specifications_analyzer_node` (spec exclusions/defaults);
  `schedule_parser_node` (door/window schedule table; VLM with OCR fallback)
- **Layer 2** `layer2_vision/` — `ocr_consensus_node` (2-of-3 voting OCR passes);
  `cv_detector_node` (PyMuPDF geometry locates each mark, crops it, VLM classifies
  swing / INT-EXT — heaviest module, ~1.1k lines)
- **Layer 3** `layer3_human/` — `reconciliation_node` (joins schedule/OCR/CV → `unresolved_queue`
  + `qa_prefilled`); `interrupt_node` (human gate)
- **Layer 5** `layer5_output/` — `excel_writer_node` (multi-sheet .xlsx via openpyxl);
  `plan_annotation_node` (color pins on the plan via PyMuPDF)
- **No Layer 4 exists** (see Known drift).

### Runtime
`app/services/graph/session_manager.py` (`session_manager` singleton) streams the graph with
`astream`, maps node completion → progress %, pushes **Server-Sent Events** to the frontend,
persists `CostmateState` to Postgres JSONB after each step, and handles pause/resume
(`resume_session` injects `qa_verified` via `aupdate_state(as_node="interrupt_node")`).

### API (`Backend/app/main.py` + `Backend/app/modules/`)
- `auth` (`/api/auth`) — signup/OTP/login, RSA `public-key`, Google OAuth
- `estimations` (`/api`) — main surface: draft/setup-wizard flow,
  `POST /session/draft/{id}/complete` (starts graph), `POST /qa/{id}/submit` (resume),
  `GET /status/{id}/stream` (SSE), xlsx + annotated-plan downloads
- `chat` (`/api/chat`) — AI copilot that patches `qa_prefilled`
- Request/response bodies are RSA+AES-GCM encrypted end-to-end
  (`Backend/app/core/crypto_utils.py` ↔ `Frontend/src/lib/crypto.ts`).
- CORS is currently wide open (`allow_origins=["*"]`).

### Database (PostgreSQL, SQLAlchemy — `Backend/app/db/postgres.py`)
Main tables: `users`, `sessions`, `email_verifications`,
`estimation_sessions` (holds the full `CostmateState` as JSONB — the durable pipeline store),
`draft_estimation_sessions`, `in_platform_notifications`.

### Frontend
Next.js App Router; the whole workspace is `Frontend/src/app/page.tsx`. Key components in
`Frontend/src/components/`: `SetupWizardModal`, `TabEditor` (+ `editor/` panels),
`ReviewQueueModal` (human QA), `CopilotPanel`. All backend calls go through
`Frontend/src/lib/api.ts` (attaches bearer token, transparently encrypts/decrypts payloads,
unwraps `{success, data}`); progress consumed via SSE in `hooks/useSSE.ts`.

## Known drift & gotchas
- **Docs overstate scope.** Civil BOQ, OpenCV/YOLO/SAM, DSR pricing are described but not
  implemented. Detection is PyMuPDF geometry + VLM crops; there is no costing stage.
- **Layer 4 doesn't exist.** Graph goes 3 → 5. A vestigial `civil_quantities` structure is
  referenced (`chat/service.py`, `/api/files/{id}/readme`) but never populated.
- **V2 pipeline is dead code.** `Backend/app/modules/estimations/v2_router.py`
  (`/api/v2/doors-windows`) calls `SessionManager` methods that don't exist (raises at runtime);
  its frontend route `Frontend/src/app/doors-windows/` is empty. Don't build on it.
- `Backend/.env.example` is stale (Ollama / `DSR_PATH`) — use `config.py`.
- Some debug `print()`s remain (e.g. `estimations/router.py`).

## Conventions
- Backend: `black` + `isort` (dev deps). Frontend: `eslint` (`npm run lint`).
- Agent nodes follow a consistent `*_node(state) -> state` pattern over `CostmateState`.
- Match the surrounding style when editing.
