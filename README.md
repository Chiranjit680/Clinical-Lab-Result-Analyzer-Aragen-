# Clinical Lab Result Analyzer

Upload a lab report, get every result classified by severity — **Normal / Warning / Critical** —
with a plain-language explanation of *why* each one was flagged, grounded in published
literature, plus a follow-up chat that already knows the full panel.

Built around one constraint: **a user should never see a bare "abnormal" label.** Every flagged
result carries the measured deviation, the reference range it was compared against, a clinical
explanation, a concrete next step, and links to the sources behind it.

**▶ [Watch the demo](https://youtu.be/91TMwreZPQo)**

---

## Contents

- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [How the analysis works](#how-the-analysis-works)
- [API reference](#api-reference)
- [Data model](#data-model)
- [Testing](#testing)
- [Engineering notes](#engineering-notes)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## What it does

Three things, reachable from three tabs in the UI:

| Tab | Purpose |
|---|---|
| **Analyze** | Upload a PDF report (or type values manually) and analyse it immediately — nothing is stored |
| **Add lab report** | File a report document against a patient, for the record |
| **Patient reports** | Browse everything stored for a patient, and analyse any of it on demand |

A PDF is read locally, its fields are extracted by an LLM, and the extraction is validated against
a strict schema before anything downstream sees it. The resulting rows go through a LangGraph
pipeline that classifies each value, researches the abnormal ones against PubMed, and writes the
explanations.

---

## Architecture

Three services, two languages, deliberately split by what each is good at.

```
                         ┌──────────────────────────┐
                         │  React + Vite  :5173     │
                         │  Analyze / Add / Browse  │
                         └───┬──────────────────┬───┘
         POST /analyze_report│                  │  /api/reports, /api/identities
         ws /ws/chat/{id}    │                  │
                             ▼                  ▼
   ┌─────────────────────────────────┐   ┌──────────────────────────────┐
   │ Analyzer Service (FastAPI)      │   │ patientService (Spring Boot) │
   │ :8000                           │   │ :8082                        │
   │                                 │   │                              │
   │ pdf_extract  pypdf → LLM        │   │ Identity + LabReport CRUD    │
   │              → Pydantic         │   │ Multipart upload + download  │
   │                 │               │   │ Flyway migrations            │
   │                 ▼               │   └──────────────┬───────────────┘
   │ LangGraph StateGraph            │                  │ JDBC
   │  validate → translate →         │                  ▼
   │  check_units → classify →       │        ┌───────────────────┐
   │  route ─┬→ critical_alert       │        │ PostgreSQL 17     │
   │         └→ explain → aggregate  │        │ patient           │
   │            → chat ⇄ interrupt   │        │ lab_report        │
   └────────────┬────────────────────┘        │ uploads/ on disk  │
                │ stdio JSON-RPC              └───────────────────┘
                ▼
     ┌──────────────────────────┐
     │ MCP server (subprocess)  │ ── PubMed / web search
     │ 11 clinical tools        │
     └──────────────────────────┘
```

**Why the split:** the analysis side is Python because that is where the agent, LLM and
scientific tooling live. The records side is Java because it is ordinary transactional CRUD with
a relational schema, migrations and file storage — work Spring Boot does well and predictably.

---

## Repository layout

```
.
├── run.ps1                      One command to start all three services
├── Analyzer Service/
│   ├── README.md                Deep dive on the agent, graph and MCP tools
│   ├── run.ps1                  Analyzer + frontend only
│   ├── test_data/               Sample CSV panels, a synthetic PDF, and its generator
│   └── backend/
│       ├── app/
│       │   ├── main.py          FastAPI app, CORS, lifespan, run log middleware
│       │   ├── routers/         labs.py · chat.py · health.py
│       │   ├── agent.py         Checkpointed entry point; parks a thread for chat
│       │   ├── graph.py         LangGraph StateGraph: the analysis pipeline
│       │   ├── pdf_extract.py   pypdf text → LLM extraction → Pydantic validation
│       │   ├── mcp_server.py    11 clinical tools over stdio JSON-RPC
│       │   ├── llm.py           Provider-agnostic calls with fallback and retry
│       │   ├── schemas.py       LabRecord, ExtractedReport, response models
│       │   ├── units.py         Unit conversion and compatibility
│       │   └── reference_ranges.py
│       └── tests/               pytest: classification, units, ranges, schema
├── patientService/patientService/
│   └── src/main/java/.../       controller · service · entity · repository · config
│       └── resources/db/migration/   V1__create_patient · V2__create_lab_report
└── frontend/
    └── src/
        ├── App.jsx              Three views, kept mounted so work survives tab switches
        ├── api.js               Analyzer client (:8000)
        ├── patientApi.js        patientService client (:8082)
        └── components/          ReportAnalyze · AddReport · PatientReports · ReportList
                                 LabInput · ResultsDisplay · ChatPanel · LevelChart
```

---

## Quick start

**Prerequisites:** Python 3.12, Java 21, Node 20+, PostgreSQL 17, and an API key for at least one
LLM provider.

### 1. Database

```sql
CREATE DATABASE "lab-analyzer";
```

Flyway creates `patient` and `lab_report` on first start. The migrations are written
`IF NOT EXISTS` and the service baselines on migrate, so an existing hand-made schema is adopted
rather than clobbered.

### 2. Configure the analyzer

```bash
cd "Analyzer Service/backend"
cp .env.example .env     # then add your API key
```

### 3. Start everything

```powershell
.\run.ps1              # all three services
.\run.ps1 -Install     # force a dependency reinstall first
.\run.ps1 -SkipPatient # analyzer + frontend only, no Postgres needed
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Analyzer | http://127.0.0.1:8000 |
| patientService | http://127.0.0.1:8082 |

If a port is taken, the next free one is used and the choice is propagated — the back ends are
told which origin to allow through CORS, and the frontend is told which URLs to call. Starting
services by hand and shifting a port *without* propagating it is the usual cause of silent CORS
failures.

<details>
<summary>Starting services individually</summary>

```bash
# Analyzer — from "Analyzer Service/backend", not from app/
./venv/Scripts/python.exe -m app.main

# patientService — from patientService/patientService
./mvnw spring-boot:run

# Frontend — from frontend/
npm run dev
```
</details>

### 4. Try it

`Analyzer Service/test_data/` ships three CSV panels and a synthetic PDF:

```bash
curl -F "file=@Analyzer Service/test_data/dummy_lab_report.pdf" \
     http://127.0.0.1:8000/analyze_report
```

`make_dummy_report.py` regenerates that PDF with no third-party dependency, so you can edit the
rows to probe specific classifier paths.

---

## Configuration

Analyzer, in `Analyzer Service/backend/.env`:

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `groq` · `gemini` · `openrouter` · `inference` |
| `LLM_MODEL` | Model id for the chosen provider |
| `LLM_FALLBACK_PROVIDER` | Tried when the primary fails; blank disables |
| `GROQ_API_KEY` / `GEMINI_API_KEY` / `OPENROUTER_API_KEY` | Provider credentials |
| `INFERENCE_BASE_URL` / `_API_KEY` / `_MODEL` | Any OpenAI-compatible endpoint |
| `INFERENCE_MAX_TOKENS` | Reasoning models spend part of this budget thinking; too low returns empty |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `EXPLAIN_CONCURRENCY` | How many results are researched at once; raising it risks rate limits |
| `RUN_LOG_PATH` | One CSV row per request, for latency and outcome tracking |

patientService, in `application.yml` or as environment variables:

| Variable | Purpose |
|---|---|
| `SPRING_DATASOURCE_URL` | JDBC URL, default `jdbc:postgresql://localhost:5432/lab-analyzer` |
| `SERVER_PORT` | HTTP port, default 8082 |
| `APP_UPLOAD_DIR` | Where report files are written, default `uploads` |
| `APP_CORS_ORIGINS` | Allowed browser origins |

---

## How the analysis works

### PDF to validated rows

Two deliberately separate stages, because they fail differently:

1. **`extract_text`** — pypdf, entirely local. No model involved, so nothing here can be
   hallucinated. A PDF with no text layer is rejected outright rather than passed on as an empty
   prompt.
2. **`extract_report`** — the text goes to the LLM with a JSON-only instruction, and the reply is
   validated against the `ExtractedReport` schema. A schema miss is retried **once with the
   validation error fed back to the model**. If it still fails, the request fails — a malformed
   extraction never reaches the clinical pipeline.

### The pipeline

```
validate → translate → check_units → classify → route ─┬→ critical_alert ─┐
                                                       └→ explain ◄───────┘
                                                               ↓
                                                          aggregate → chat ⇄ interrupt
```

Each row is validated **individually**, so one malformed row lands in `errors[]` instead of
failing the whole batch. `route` branches on severity so critical findings are handled first.
Only abnormal results are researched and explained — normal ones skip the expensive path.

`chat` calls LangGraph's `interrupt()`, which suspends the run and returns control to the caller.
`/analyze_labs` therefore returns as soon as results are aggregated, handing back a `thread_id`.
The WebSocket resumes that same checkpoint for every follow-up question, so the chat has the
entire analysis in context without it being re-sent.

### MCP tools

The graph calls a tool server over stdio JSON-RPC rather than importing functions, which keeps
the clinical logic independently testable and swappable:

`classify_lab_result` · `classify_qualitative_result` · `check_unit_compatibility` ·
`reference_range_lookup` · `translate_to_english` · `web_search` · `pubmed_search` ·
`search_clinical_context` · `explain_result` · `get_next_steps` · `answer_followup`

---

## API reference

### Analyzer — `:8000`

| Method | Path | Notes |
|---|---|---|
| `GET` | `/health` | Liveness |
| `POST` | `/analyze_labs` | JSON `{ labs: [...] }` of row objects |
| `POST` | `/analyze_report` | Multipart PDF; 415 non-PDF, 413 over 10 MB, 422 unreadable |
| `WS` | `/ws/chat/{thread_id}` | `{"question": "..."}` → `{"type":"answer","content":"..."}` |

### patientService — `:8082`

| Method | Path | Notes |
|---|---|---|
| `GET` `POST` | `/api/identities` | List / create patients |
| `GET` `PUT` `DELETE` | `/api/identities/{id}` | Single patient |
| `POST` | `/api/reports/save` | Record a report by path |
| `POST` | `/api/reports/upload` | Multipart upload; stores the file and the record together |
| `GET` | `/api/reports/download/{reportId}` | Streams the stored file |
| `GET` | `/api/reports/get/{reportId}` | One report |
| `GET` | `/api/reports/getall/{patientId}` | All reports for a patient, newest first |
| `PUT` | `/api/reports/updateStatus/{reportId}/{status}` | `NORMAL` · `WARNING` · `CRITICAL` |
| `DELETE` | `/api/reports/delete/{reportId}` | Remove a report |

---

## Data model

```
patient                              lab_report
├── id            UUID PK            ├── id          UUID PK
├── full_name     VARCHAR(120)       ├── patient_id  UUID FK → patient(id) ON DELETE CASCADE
├── date_of_birth DATE               ├── report_path VARCHAR(500)
├── sex           VARCHAR(10)        ├── status      VARCHAR(10) CHECK (NORMAL|WARNING|CRITICAL)
├── blood_group   VARCHAR(5)         └── created_at  TIMESTAMPTZ
├── pregnant      BOOLEAN
├── created_at    TIMESTAMPTZ        INDEX idx_lab_report_patient (patient_id)
└── updated_at    TIMESTAMPTZ
```

Uploaded files are written to `uploads/yyyy/MM/<uuid>__<original-name>` and only the **relative**
path is stored, so the upload directory can be moved or remounted without rewriting any rows. The
server generates that path — callers never choose where a file lands — and every read and write
is checked to resolve inside the upload root, so a crafted path cannot escape it.

---

## Testing

```bash
# Analyzer
cd "Analyzer Service/backend" && ./venv/Scripts/python.exe -m pytest

# patientService
cd patientService/patientService && ./mvnw test

# Frontend
cd frontend && npm run lint && npm run build
```

`tests/` covers severity classification boundaries, unit conversion, reference-range validation
and schema behaviour — the deterministic core, which is where correctness actually matters.

---

## Engineering notes

**Validation is the boundary with the model.** `ExtractedLabRow` is deliberately separate from
`LabRecord`: one is a contract against *the model's output* — strict about shape, tolerant about
types, since models emit strings for everything — and the other validates *analysis input*. The
model is given exactly one retry, with its own validation error quoted back to it.

**Blocking work stays off the event loop.** pypdf and the LLM client are both synchronous; they
run in a thread pool so one extraction cannot stall every other request.

**Provider failure is expected, not exceptional.** `llm.py` retries, detects rate limiting and
moves to the fallback provider rather than burning time on a request that will not recover. Every
tool has a rule-based fallback, so a total LLM outage degrades the output instead of failing it.

**Views stay mounted in the UI.** Switching tabs used to unmount the active view, so a running
analysis delivered its result to a dead component and the work was silently thrown away. All
three views are now rendered and hidden instead.

**Ports are chosen together.** Because CORS allowlists and API base URLs reference each other,
`run.ps1` resolves all three ports before starting anything and passes each choice to whatever
depends on it.

---

## Known limitations

- **No authentication.** Every endpoint is open to anyone who can reach the port. Spring
  Security is present but disabled.
- **No OCR.** Scanned PDFs have no text layer and are rejected with a clear message rather than
  guessed at.
- **Analysis is slow.** A full panel takes one to two minutes — each abnormal result is
  researched before it is explained. Explanations already run concurrently
  (`EXPLAIN_CONCURRENCY`), bounded to avoid provider and NCBI rate limits.
- **Word documents are stored, not read.** `.doc`/`.docx` can be filed against a patient, but
  nothing can extract values from them.
- **In-memory checkpointing.** Chat threads live in process memory; a restart ends them. Swap
  `MemorySaver` for a SQLite or Postgres saver to survive restarts or run multiple workers.
- **The two back ends do not talk to each other.** The browser integrates them — it downloads a
  stored file from patientService and posts it to the analyzer.
- **Not a medical device.** Clinical decision support, informational only, not a diagnosis.

---

## Roadmap

- `docker compose up` for the entire stack, so the project runs without a local toolchain
- Streamed progress from the graph (SSE) in place of the current time-based loading indicator
- An evaluation harness for PDF extraction: golden reports, field-level precision and recall,
  and a regression check when the prompt changes
- JWT auth across both back ends
- CI running pytest, Maven tests, oxlint and the frontend build
- Trend view: one test charted across a patient's reports over time
- Docling for table-aware extraction and OCR of scanned reports
