# Clinical Lab Result Analyzer

Upload a lab report, get every result classified by severity — **Normal / Warning / Critical** —
with a plain-language explanation of *why* each one was flagged, grounded in published
literature, plus a follow-up chat that already knows the full panel.

Radiological images get the same treatment from a different angle: a grid of vision agents that
can zoom and enhance the image before reporting, then merge their findings into one answer.

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
- [How the lab analysis works](#how-the-lab-analysis-works)
- [How the image analysis works](#how-the-image-analysis-works)
- [API reference](#api-reference)
- [Data model](#data-model)
- [Testing](#testing)
- [Engineering notes](#engineering-notes)
- [Known limitations](#known-limitations)
- [Roadmap](#roadmap)

---

## What it does

Seven tabs, ordered the way the work flows — a patient exists before a report is filed against
them, and reports exist before there is anything to browse.

| Tab | Purpose |
|---|---|
| **Analyze** | Upload a PDF report (or type values manually) and analyse it immediately — nothing is stored |
| **Add patient** | Create a patient record |
| **Add lab report** | File a report document against a patient, for the record |
| **Add image** | File a radiological image against a patient, with modality and body part |
| **Patient reports** | Browse a patient's reports; analyse any of them, re-read a stored analysis, or email one |
| **Patient images** | Browse a patient's images; run the vision agents, save the result, or email it |
| **Send report** | Pick a patient, a report and a recipient, and send it with its analysis |

Two analysis paths, stored the same way. A lab report is read locally, its fields are extracted by
an LLM, and the extraction is validated against a strict schema before anything downstream sees
it. An image is cut into tiles that each get their own agent. In both cases the result is written
back against the record, and **re-analysing replaces the previous result** — enforced by a unique
constraint, not by convention.

---

## Architecture

Five services, two languages, split by what each is good at.

```
                          ┌───────────────────────────────┐
                          │  React + Vite  :5173          │
                          │  7 tabs, all kept mounted     │
                          └─┬──────────┬────────────────┬─┘
      POST /analyze_report  │          │                │  POST /analyze_image
      ws /ws/chat/{id}      │          │ /api/*         │
                            ▼          ▼                ▼
  ┌──────────────────────────────┐  ┌──────────────────────────┐  ┌─────────────────────────┐
  │ Analyzer Service (FastAPI)   │  │ patientService (Spring)  │  │ vlm_agents (FastAPI)    │
  │ :8000                        │◄─┤ :8082                    │  │ :8084                   │
  │                              │  │                          │  │                         │
  │ pdf_extract pypdf → LLM      │  │ Identity · LabReport     │  │ LangGraph fan-out:      │
  │             → Pydantic       │  │ RadiologyImage           │  │  global agent           │
  │                │             │  │ Analysis · ImageAnalysis │  │   → N tile agents ∥     │
  │                ▼             │  │ Upload / download        │  │   → aggregator          │
  │ LangGraph StateGraph         │  │ Flyway migrations        │  └───────────┬─────────────┘
  │  validate → translate →      │  └──────┬───────────────┬───┘              │ stdio
  │  check_units → classify →    │         │ JDBC          │ POST /send_*     ▼
  │  route ─┬→ critical_alert    │         ▼               ▼        ┌────────────────────┐
  │         └→ explain → aggreg. │  ┌──────────────┐  ┌───────────────────┐ │ MCP image tools │
  │            → chat ⇄ interrupt│  │ PostgreSQL 17│  │ email_service     │ │ zoom · gamma ·  │
  └───────────┬──────────────────┘  │ 5 tables     │  │ :8083  Gmail API  │ │ sharpen · edges │
              │ stdio JSON-RPC      │ uploads/     │  └───────────────────┘ └────────────────────┘
              ▼                     └──────────────┘
    ┌──────────────────────────┐
    │ MCP server (subprocess)  │ ── PubMed / web search
    │ 11 clinical tools        │
    └──────────────────────────┘
```

**Why the split:** the analysis sides are Python because that is where the agents, LLM clients and
scientific tooling live. The records side is Java because it is ordinary transactional CRUD with a
relational schema, migrations and file storage — work Spring Boot does well and predictably. The
email service is separate because it owns exactly one thing, the Gmail credential, and nothing
else: no database, no access to the uploads folder.

**Who calls whom.** patientService calls the analyzer and the email service server-to-server. The
**browser** calls the VLM service directly, because an image run takes minutes and proxying it
would mean holding an HTTP request open for that long; the result is posted back to patientService
to be stored.

---

## Repository layout

```
.
├── run.ps1                      One command to start all five services
├── Analyzer Service/
│   ├── README.md                Deep dive on the agent, graph and MCP tools
│   ├── run.ps1                  Analyzer + frontend only
│   ├── test_data/               Sample CSV panels, a synthetic PDF, and its generator
│   └── backend/
│       ├── Dockerfile
│       └── app/
│           ├── main.py          FastAPI app, CORS, lifespan, run log middleware
│           ├── routers/         labs.py · chat.py · health.py
│           ├── agent.py         Checkpointed entry point; parks a thread for chat
│           ├── graph.py         LangGraph StateGraph: the analysis pipeline
│           ├── pdf_extract.py   pypdf text → LLM extraction → Pydantic validation
│           ├── mcp_server.py    11 clinical tools over stdio JSON-RPC
│           ├── llm.py           Provider-agnostic calls with fallback and retry
│           ├── schemas.py       LabRecord, ExtractedReport, response models
│           └── units.py · reference_ranges.py
├── vlm_agents/                  Vision agents over radiological images
│   ├── main.py                  FastAPI :8084 — POST /analyze_image
│   ├── graph.py                 global agent → TILE_GRID² tile agents ∥ → aggregator
│   ├── agents.py                The ReAct tool loop, shared by every agent
│   ├── model.py                 OpenAI-compatible vision client
│   ├── mcp_client.py            Sync facade over the async MCP session
│   ├── mcp_server.py            8 image tools over stdio
│   ├── store.py                 Per-run artifacts: tiles, tool outputs, full traces
│   └── logs.py                  Run- and agent-tagged logging across threads
├── email_service/               Owns the Gmail credential and nothing else
│   ├── main.py                  FastAPI :8083 — /send_report · /send_image
│   ├── email_sender.py          Gmail API, multipart/alternative, attachments
│   ├── report_email.py          Renders a lab analysis (values and severities)
│   └── image_email.py           Renders an image analysis (agent prose)
├── patientService/patientService/
│   ├── Dockerfile
│   └── src/main/java/.../       controller · service · entity · repository · dto · config
│       └── resources/db/migration/
│             V1__create_patient · V2__create_lab_report · V3__create_analysis
│             V4__create_radiology_image · V5__create_image_analysis
└── frontend/
    └── src/
        ├── App.jsx              Seven views, kept mounted so work survives tab switches
        ├── api.js               Analyzer client (:8000)
        ├── patientApi.js        patientService client (:8082)
        ├── vlmApi.js            VLM agent client (:8084)
        └── components/          ReportAnalyze · AddPatient · AddReport · AddImage
                                 PatientReports · PatientImages · SendReport · ReportList
                                 LabInput · ResultsDisplay · ChatPanel · BackgroundDecor
```

---

## Quick start

**Prerequisites:** Python 3.12, Java 21, Node 20+, PostgreSQL 17, and an API key for at least one
LLM provider. Gmail credentials are only needed if you want to send email.

### 1. Database

```sql
CREATE DATABASE "lab-analyzer";
```

Flyway creates all five tables on first start. The migrations are written `IF NOT EXISTS` and the
service baselines on migrate, so an existing hand-made schema is adopted rather than clobbered.

### 2. Configure

```bash
cd "Analyzer Service/backend" && cp .env.example .env    # add your API key
cd ../../vlm_agents           && cp .env.example .env    # vision model
cd ../email_service           && cp .env.example .env    # optional
```

Each service loads **its own** `.env` by explicit path, not by searching upwards, so every one can
be deployed independently without inheriting another's configuration.

### 3. Start everything

```powershell
.\run.ps1               # all five services
.\run.ps1 -Install      # force a dependency reinstall first
.\run.ps1 -SkipPatient  # analyzer + frontend only, no Postgres needed
.\run.ps1 -SkipEmail    # skip the email service
.\run.ps1 -SkipVlm      # skip the VLM agent service
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Analyzer | http://127.0.0.1:8000 |
| patientService | http://127.0.0.1:8082 |
| email_service | http://127.0.0.1:8083 |
| vlm_agents | http://127.0.0.1:8084 |

If a port is taken, the next free one is used and the choice is propagated — the back ends are
told which origin to allow through CORS, patientService is told where the analyzer and email
services ended up, and the frontend is told which URLs to call. Starting services by hand and
shifting a port *without* propagating it is the usual cause of silent CORS failures.

<details>
<summary>Starting services individually</summary>

```bash
# Analyzer — from "Analyzer Service/backend", not from app/
./venv/Scripts/python.exe -m app.main

# patientService — from patientService/patientService
./mvnw spring-boot:run

# VLM agents — from the repository root, so `python -m vlm_agents.mcp_server` resolves
vlm_agents/venv/Scripts/python.exe -m uvicorn vlm_agents.main:app --port 8084

# Email service — from email_service/
./venv/Scripts/python.exe -m uvicorn main:app --port 8083

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

VLM agents, in `vlm_agents/.env`:

| Variable | Purpose |
|---|---|
| `VLM_BASE_URL` / `VLM_API_KEY` / `VLM_MODEL` | Vision model; falls back to the `INFERENCE_*` names so one file can serve both services |
| `VLM_REASONING_HEADROOM` | Added on top of the caller's answer budget. `max_tokens` is a ceiling, not a spend — too small a value costs a whole call |
| `VLM_ATTEMPTS` | An empty reply is retried with **double** the budget, so attempt two differs from attempt one |
| `TILE_GRID` | Tiles per side. `2` → four tile agents. Each runs its own tool loop, so this squares the cost of a run |
| `MAX_TOOL_STEPS` | Tool calls allowed per agent before it must answer; per-agent model calls are this plus one |
| `VLM_MAX_IMAGE_SIDE` | Images are base64-encoded into the request body; this bounds the payload |
| `MCP_START_TIMEOUT` | The image tool server is a subprocess. If it dies at import there is nothing to wait for, so the wait is bounded |

Email service, in `email_service/.env`:

| Variable | Purpose |
|---|---|
| `GMAIL_CREDENTIALS_PATH` / `GMAIL_TOKEN_PATH` | OAuth client and stored token; both default to the service folder |
| `EMAIL_MAX_ATTACHMENT_MB` | Raw ceiling before base64 inflates it by about a third; Gmail rejects finished messages over 25 MB |
| `CORS_ORIGINS` | Browser origins; patientService calls server-to-server and is unaffected |

patientService, in `application.yml` or as environment variables:

| Variable | Purpose |
|---|---|
| `SPRING_DATASOURCE_URL` | JDBC URL, default `jdbc:postgresql://localhost:5432/lab-analyzer` |
| `SERVER_PORT` | HTTP port, default 8082 |
| `APP_UPLOAD_DIR` | Where files are written, default `uploads` |
| `APP_ANALYZER_BASE_URL` | Where the analyzer is |
| `APP_ANALYZER_TIMEOUT_SECONDS` | Default 600 — a full panel researches every abnormal result |
| `APP_EMAIL_SERVICE_BASE_URL` | Where the email service is |
| `APP_CORS_ORIGINS` | Allowed browser origins |

> **Secrets:** `credentials.json`, `client_secret*.json`, `token.json` and every `.env` are
> gitignored. Supply your own; none are committed.

---

## How the lab analysis works

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

## How the image analysis works

```
START → global_agent ─┬→ tile_agent_r0c0 ─┐
                      ├→ tile_agent_r0c1 ─┤
                      ├→ tile_agent_r1c0 ─┼→ aggregator → END
                      └→ tile_agent_r1c1 ─┘
```

The global agent sees the whole image downscaled, then cuts a `TILE_GRID`×`TILE_GRID` grid with
15% overlap. Each tile gets its own agent running in parallel; LangGraph will not enter the
aggregator until every one has returned. The parallel merge works because `tile_reports` is
`Annotated[list, operator.add]` — without that reducer, concurrent writes to one state key
conflict.

### The tool loop

Every agent runs the same loop. It is shown an image and must reply with exactly one JSON object:
either `{"tool": …, "args": …}` or `{"final": …}`. It gets `MAX_TOOL_STEPS` tool calls, then one
more turn with tool use revoked. Degradations are handled rather than raised — a non-JSON reply is
taken verbatim as the answer, a tool that throws puts its error into the history and the agent
gets another turn.

Eight image tools, served over stdio by a subprocess:
`zoom` · `autocontrast` · `equalize` · `gamma` · `sharpen` · `denoise` · `edges` · `invert`

### Tools compose, so the view is tracked

A tool applies to the image the agent is *currently looking at*, not the original, so zooms nest.
Left alone, an agent that zooms twice reports coordinates in the frame of its last crop — which
looks like a confident answer and is wrong. The loop therefore composes each zoom into a running
view in original-image coordinates, tells the agent which region of the original it is seeing, and
offers a client-side `reset_view` to get back out.

Measured on a marker at a known position: before the fix the model reported 0.45–0.50; after it,
0.68 against a true 0.669.

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
| `GET` | `/api/reports/get/{reportId}` · `/api/reports/getall/{patientId}` | One report / all for a patient, newest first |
| `POST` | `/api/reports/{reportId}/analyze` | Calls the analyzer and stores the result, replacing any previous one |
| `GET` | `/api/reports/{reportId}/analysis` | The stored analysis; 404 when there is none |
| `POST` | `/api/reports/{reportId}/email` | `{to, note}` — sends the report with its analysis |
| `PUT` | `/api/reports/updateStatus/{reportId}/{status}` | `NORMAL` · `WARNING` · `CRITICAL` |
| `DELETE` | `/api/reports/delete/{reportId}` | Remove a report |
| `POST` | `/api/images/upload` | Multipart; `.dcm` `.dicom` `.png` `.jpg` `.jpeg`, checked server-side |
| `GET` | `/api/images/get/{imageId}` · `/api/images/getall/{patientId}` | One image / all for a patient |
| `GET` | `/api/images/download/{imageId}` | Streams inline, so PNG and JPEG preview in the browser |
| `PUT` | `/api/images/{imageId}/analysis` | Store a VLM run, replacing any previous one |
| `GET` | `/api/images/{imageId}/analysis` | The stored image analysis; 404 when there is none |
| `POST` | `/api/images/{imageId}/email` | `{to, note}` — sends the image with its analysis |
| `DELETE` | `/api/images/delete/{imageId}` | Remove an image |

Report and image listings carry `analysisAvailable` and `analysisId`, so the UI can enable
"see previous analysis" without fetching every payload. Both listings batch the analysis lookup
into one query rather than one per row.

### vlm_agents — `:8084`

| Method | Path | Notes |
|---|---|---|
| `GET` | `/health` | Reports the model and the tile count |
| `POST` | `/analyze_image` | Multipart image + optional `question`; 415 unreadable, 413 over 20 MB. Minutes, not seconds |

### email_service — `:8083`

| Method | Path | Notes |
|---|---|---|
| `GET` | `/health` | Also reports whether Gmail is connected |
| `POST` | `/send_report` | Multipart: `to`, `file`, `patient_name`, `analysis_json`, `note` |
| `POST` | `/send_image` | As above plus `caption` ("XRAY - Chest") |

Two endpoints rather than a flag, because the two analyses have nothing in common beyond being
attached to a file: a lab analysis is measured values with severities, an image analysis is prose.
One renderer for both would serve neither.

---

## Data model

```
patient                           lab_report                      analysis
├── id            UUID PK         ├── id          UUID PK         ├── id          UUID PK
├── full_name     VARCHAR(120)    ├── patient_id  UUID FK ──┐     ├── report_id   UUID FK UNIQUE
├── date_of_birth DATE            ├── report_path VARCHAR    │     ├── thread_id   VARCHAR(64)
├── sex           VARCHAR(10)     ├── status      VARCHAR    │     ├── status      VARCHAR(10)
├── blood_group   VARCHAR(5)      └── created_at  TIMESTAMPTZ│     ├── *_count     INTEGER ×5
├── pregnant      BOOLEAN                                    │     ├── duration_ms INTEGER
├── created_at    TIMESTAMPTZ     radiology_image            │     ├── payload     JSONB
└── updated_at    TIMESTAMPTZ     ├── id          UUID PK    │     └── created_at  TIMESTAMPTZ
                                  ├── patient_id  UUID FK ───┤
image_analysis                    ├── image_path  VARCHAR    │
├── id          UUID PK           ├── modality    VARCHAR(16)│
├── image_id    UUID FK UNIQUE    ├── body_part   VARCHAR(80)│
├── question    VARCHAR(2000)     ├── description VARCHAR    │
├── answer      TEXT              └── created_at  TIMESTAMPTZ│
├── model       VARCHAR(120)                                 │
├── run_id      VARCHAR(64)       All FKs ON DELETE CASCADE ─┘
├── tile_count  INTEGER
├── duration_ms INTEGER
├── payload     JSONB
└── created_at  TIMESTAMPTZ
```

**`UNIQUE` on `analysis.report_id` and `image_analysis.image_id` is the overwrite rule.**
Re-analysing replaces the previous result rather than accumulating, and the constraint makes that
the database's rule instead of a convention the service has to remember — a record can never end
up with two "current" analyses, whatever the application does.

The severity counts and the scannable image fields are real columns because they are what gets
filtered and displayed. The full response is kept in **JSONB** so explanations, sources, next
steps and per-tile reports can be re-rendered without a migration every time that shape changes.
Stored payloads keep the services' own snake_case keys, so a saved analysis renders with exactly
the same frontend component as a live one.

Uploaded files are written to `<category>/yyyy/MM/<uuid>__<original-name>` and only the
**relative** path is stored, so the upload directory can be moved or remounted without rewriting
any rows. The server generates that path — callers never choose where a file lands — and every
read and write is checked to resolve inside the upload root, so a crafted path cannot escape it.

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

**Blocking work stays off the event loop.** pypdf, the LLM client and the whole image graph are
synchronous; they run in a thread pool so one extraction or image run cannot stall every other
request.

**Provider failure is expected, not exceptional.** `llm.py` retries, detects rate limiting and
moves to the fallback provider rather than burning time on a request that will not recover. Every
clinical tool has a rule-based fallback, so a total LLM outage degrades the output instead of
failing it.

**A retry has to differ from the attempt it retries.** A reasoning model that exhausts its budget
thinking returns empty content, and re-sending the identical request fails identically. The vision
client doubles the budget on each empty reply instead.

**One failed call should not discard forty.** The image aggregator is a single call at the end of
a whole run. If it fails, the agents' own findings are returned unmerged rather than the run being
thrown away.

**The async/sync boundary is explicit.** The image tool server is an async MCP session, the graph
nodes are synchronous. The session lives on a background event-loop thread and every call is
marshalled onto it with `run_coroutine_threadsafe` — one session shared by all tile threads, which
is safe precisely because everything funnels through that one loop.

**Startup races readiness against failure.** Waiting on a readiness event alone hangs forever when
a subprocess dies at import, which is indistinguishable from "slow" at the far end of a request.
The wait is bounded and the failure is raised with the reason.

**Views stay mounted in the UI.** Switching tabs used to unmount the active view, so a running
analysis delivered its result to a dead component and the work was silently thrown away. All seven
views are now rendered and hidden instead.

**Ports are chosen together.** Because CORS allowlists and API base URLs reference each other,
`run.ps1` resolves every port before starting anything and passes each choice to whatever depends
on it.

**Each service owns its own configuration.** Every `.env` is loaded by explicit path rather than
by searching upwards from the working directory, so a service behaves the same however it is
started — from its own folder, from the repository root, or as a container entrypoint — and can be
deployed on its own.

---

## Known limitations

- **No authentication.** Every endpoint is open to anyone who can reach the port. Spring
  Security is present but disabled.
- **No OCR.** Scanned PDFs have no text layer and are rejected with a clear message rather than
  guessed at.
- **DICOM is stored but not analysed.** Pillow cannot open it without a plugin, so the UI disables
  Analyze for those files rather than failing minutes later.
- **Analysis is slow.** A full lab panel takes one to two minutes. An image run is
  `(1 + TILE_GRID²) × (MAX_TOOL_STEPS + 1) + 1` model calls — 16 at the defaults — and the tile
  agents are parallel, so provider rate limits, not CPU, set the pace.
- **A saved image analysis is client-supplied.** The browser runs the vision agents and posts the
  result back, so the stored payload is validated and size-bounded rather than trusted. The
  alternative was holding an HTTP request open through patientService for minutes.
- **Word documents are stored, not read.** `.doc`/`.docx` can be filed against a patient, but
  nothing can extract values from them.
- **In-memory checkpointing.** Chat threads live in process memory; a restart ends them. Swap
  `MemorySaver` for a SQLite or Postgres saver to survive restarts or run multiple workers.
- **Single-run assumptions in the image service.** The run store and the log correlation id are
  module-level, so two genuinely concurrent image runs would cross-label their logs.
- **Not a medical device.** Clinical decision support, informational only, not a diagnosis.

---

## Roadmap

- `docker compose up` for the entire stack, so the project runs without a local toolchain
  (Dockerfiles for both back ends already exist)
- Streamed progress from the graphs (SSE) in place of the current time-based loading indicator
- An evaluation harness for PDF extraction: golden reports, field-level precision and recall,
  and a regression check when the prompt changes
- JWT auth across both back ends
- CI running pytest, Maven tests, oxlint and the frontend build
- Trend view: one test charted across a patient's reports over time
- Docling for table-aware extraction and OCR of scanned reports
- DICOM support via pydicom, so images can be analysed in the format scanners actually produce
