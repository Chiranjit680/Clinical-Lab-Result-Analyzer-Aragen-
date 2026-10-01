# Clinical Lab Result Analyzer

A full-stack application that takes lab test results, classifies each one by severity
(**Normal / Warning / Critical**), routes them critical-first, and explains *why* each
result was flagged — in clinically relevant language, grounded in published literature.

Built around the **Explainable AI** constraint: a user should never see a bare
"abnormal" label. Every flagged result ships with the measured deviation, the reference
range it was compared against, a plain-language clinical explanation, a concrete next
step, and links to the sources that informed it.

**▶ [Watch the demo](https://youtu.be/91TMwreZPQo)** — uploading a panel, severity
routing, explanations with sources, and the follow-up chat.

---

## Contents

- [Demo](#demo)
- [Architecture](#architecture)
- [Setup](#setup)
- [Running the app](#running-the-app)
- [AI provider](#ai-provider)
- [How to test](#how-to-test)
- [API](#api)
- [Design decisions](#design-decisions)
- [Known limitations](#known-limitations)
- [Future work](#future-work)

---

## Demo

[![Clinical Lab Result Analyzer — demo](https://img.youtube.com/vi/91TMwreZPQo/hqdefault.jpg)](https://youtu.be/91TMwreZPQo)

<https://youtu.be/91TMwreZPQo>

---

## Architecture

```
Browser (React)
      │  POST /analyze_labs                    ws://…/ws/chat/{thread_id}
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ FastAPI  (backend/app/main.py)                                  │
│                                                                 │
│  routers/labs.py ──► agent.py ──► LangGraph StateGraph          │
│                                    (backend/app/graph.py)       │
│                                                                 │
│   validate → translate → classify → route ─┬─► critical_alert   │
│                                            └─► explain          │
│                                                  → aggregate    │
│                                                  → chat ⇄ pause │
└───────────────────────────┬─────────────────────────────────────┘
                            │ stdio (JSON-RPC), one persistent session
                            ▼
              ┌──────────────────────────────────┐
              │ MCP server subprocess            │
              │ (backend/app/mcp_server.py)      │
              │                                  │
              │  classify_lab_result             │
              │  classify_qualitative_result     │
              │  reference_range_lookup          │
              │  translate_to_english            │
              │  pubmed_search / web_search      │
              │  search_clinical_context         │
              │  explain_result                  │
              │  get_next_steps                  │
              │  answer_followup                 │
              └───────────┬──────────────┬───────┘
                          │              │
                   NCBI E-utilities   LLM provider
                   (PubMed)           (see below)
```

### The agent pipeline

The agent is a **LangGraph `StateGraph`**. It holds no domain logic of its own —
every classification, lookup, translation, search, and explanation is delegated to the
MCP server, satisfying the "all agent communication goes through MCP" requirement. Each
tool call is a real cross-process JSON-RPC call over stdio, not an in-process function
call.

| Node | What it does |
|---|---|
| `validate` | Each row checked against the `LabRecord` schema. Bad rows go to `errors[]` and never reach a tool call, so one malformed row can't fail the batch. |
| `translate` | Source data is Turkish. One **batched** LLM call translates test names, statuses, comments and follow-ups to English (per-field calls would be far too slow). Originals are preserved for traceability. |
| `classify` | Calls `classify_lab_result` (or `classify_qualitative_result` for urine-strip values). Unknown tests fall back to the LLM-assisted `reference_range_lookup` tool. |
| `route` | Groups results into `critical` / `warning` / `unknown` / `normal`, critical first. |
| `critical_alert` | **Conditional branch** — runs only when a Critical result exists, flagging it `urgent`. |
| `explain` | For abnormal results only: `search_clinical_context` → `explain_result` → `get_next_steps`, threading the retrieved sources through as grounding context. Normal results skip research entirely. |
| `aggregate` | Builds the final response payload. |
| `chat` | Human-in-the-loop. Calls `interrupt()` and parks the thread so follow-up questions can resume it later (see [Follow-up chat](#follow-up-chat)). |

### Classification logic

Severity is decided by comparing the value to a reference range, resolved in this order:

1. **The row's own `Min_Reference` / `Max_Reference`** from the dataset, when present.
2. **A curated clinical dictionary** (`reference_ranges.py`, ~35 tests) — also supplies
   *critical* thresholds, which the dataset does not carry.
3. **`reference_range_lookup`** — an LLM-assisted lookup for tests in neither of the above.

A model-supplied range is **never trusted blind**. It is rejected if the bounds are
missing, non-numeric, non-finite, or if `low >= high`; critical bounds that fall
*inside* the normal band are clamped (otherwise a value in the middle of the normal
range could classify as Critical); and the range is scale-checked against the observed
value, so a range quoted in the wrong units is rejected rather than producing a
confident but wrong severity. A rejected lookup leaves the result visibly `Unknown`.
Results classified this way carry `"range_source": "llm_lookup"`.

```
value outside critical bounds  → Critical
value outside normal band      → Warning
otherwise                      → Normal
no range resolvable            → Unknown
```

Qualitative results (`Negatif`, `1+`, `3+`) have no numeric bounds and are classified by
a separate tool that compares against the expected qualitative reference, grading `1+/2+`
as Warning and `3+/4+` as Critical.

### Follow-up chat

The graph is compiled with a **checkpointer**, so after `aggregate` it pauses at the
`chat` node's `interrupt()`. `/analyze_labs` therefore returns the results *plus* a
`thread_id`. The frontend opens `ws://…/ws/chat/{thread_id}`, and each question resumes
that same parked thread via `Command(resume=…)`. Because the whole graph state is
checkpointed, the chat already has every classified result in context — nothing is
re-sent. A conditional self-loop returns the graph to the interrupt after each answer so
the conversation can continue.

---

## Setup

**Prerequisites:** Python 3.12, Node 18+.

```bash
git clone https://github.com/Chiranjit680/Clinical-Lab-Result-Analyzer-Aragen-.git
cd Clinical-Lab-Result-Analyzer-Aragen-

# Backend
cd backend
py -3.12 -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt   # macOS/Linux: venv/bin/python
cp .env.example .env        # then add your API key — see "AI provider"

# Frontend
cd ../frontend
npm install
```

> Python 3.12 is specified deliberately — 3.13/3.14 do not yet have wheels for every
> dependency. `mcp` is pinned to `<2.0.0`; v2 renamed `FastMCP` to `MCPServer` and
> changed the client API.

---

## Running the app

**One command (Windows):**

```powershell
.\run.ps1              # starts backend + frontend, Ctrl+C stops both
.\run.ps1 -Install     # force a dependency reinstall first
```

The script creates the venv if missing, waits for `/health` before starting the UI (the
MCP subprocess makes startup take a few seconds), and kills the whole process tree on
exit so port 8000 is released.

**Manually:**

```bash
# terminal 1 — from backend/
./venv/Scripts/python.exe -m app.main       # or: uvicorn app.main:app --reload --port 8000

# terminal 2 — from frontend/
npm run dev
```

- Frontend → <http://localhost:5173>
- Backend → <http://127.0.0.1:8000> (docs at `/docs`)

> Run the backend from `backend/`, **not** `backend/app/`. The `app.` package imports
> only resolve with `backend/` on `sys.path`; `python main.py` from inside `app/` fails.

---

## AI provider

The LLM layer (`backend/app/llm.py`) is provider-agnostic — one `call_llm()` function
dispatching on env vars, with an automatic fallback provider and a rule-based fallback
beyond that, so a flaky API degrades the output instead of crashing the request.

| Provider | `LLM_PROVIDER` | Notes |
|---|---|---|
| Google Gemini | `gemini` | Free tier; strict daily quota |
| OpenAI-compatible endpoint | `inference` | Used here with `deepseek/deepseek-v4-flash` |
| Groq | `groq` | Free tier, fastest |
| OpenRouter | `openrouter` | Free-tier models |

**Chosen for this project: `deepseek/deepseek-v4-flash`** via an OpenAI-compatible
endpoint, with Gemini as fallback. DeepSeek Flash answered a chat turn in ~4s and an
explanation in ~3.5s, against ~30s for the Qwen model originally configured.

```ini
LLM_PROVIDER=inference
LLM_MODEL=
LLM_FALLBACK_PROVIDER=gemini

INFERENCE_BASE_URL=https://api.hpc-ai.com/inference/v1
INFERENCE_API_KEY=your-key
INFERENCE_MODEL=deepseek/deepseek-v4-flash
INFERENCE_MAX_TOKENS=4000

GEMINI_API_KEY=your-key
```

> `INFERENCE_MAX_TOKENS` matters: reasoning models spend part of the budget on hidden
> thinking before answering. At 1000 tokens the reasoning consumed the entire budget and
> `content` came back empty — hence the 4000 default.

**Note on tool calling:** the agent does *not* use LLM-native function calling. The graph
decides deterministically which tool runs; the LLM only ever returns text. Any provider
that returns text will work.

---

## How to test

### 1. Through the UI

Start the app, upload any CSV from `test_data/`, and you should see colour-coded results,
explanations, next steps, the range chart, and the chat launcher.

`test_data/` holds three mixed panels of 8 results each, randomly drawn from a pool
covering every classification path:

| File | Contents | Notable paths exercised |
|---|---|---|
| `panel_a_mixed.csv` | 1 critical · 1 warning · 3 normal · 1 unknown · **2 rejected** | Error handling — a row with a blank `Test_Name` and a row whose `Result` is non-numeric despite a numeric reference range. Also the qualitative `3+` grade and the LLM `reference_range_lookup` fallback (Prokalsitonin). |
| `panel_b_mixed.csv` | 1 critical · 5 warning · 2 normal | Qualitative values (`Negatif`, `Pozitif`), a test with no dataset range falling back to the curated dictionary (TSH), and Turkish test names. |
| `panel_c_mixed.csv` | 3 critical · 3 warning · 2 normal | The wide-range regression case (`Trombosit` 18 in a 150–450 range → Critical), plus a unit/scale mismatch guard (`Serbest T4` must not borrow total-T4 bounds). |

Rows that fail validation appear in the response's `errors[]` and do not stop the rest
of the batch from being analysed.

### 2. Unit tests

Cover the deterministic core — severity boundaries, the qualitative grades, Turkish
alias/diacritic folding, and schema validation. No network or LLM calls, so they run in
about a second.

```bash
cd backend
./venv/Scripts/python.exe -m pytest tests/ -q       # 73 tests
```

### 3. End-to-end smoke test

Requires the backend running. Posts each CSV and asserts the expected severity plus a
non-empty explanation and next step for every result.

```bash
cd backend
./venv/Scripts/python.exe smoke_test.py            # all three panels
./venv/Scripts/python.exe smoke_test.py panel_c    # just one
```

### 4. Classification only (fast, no LLM calls)

```bash
cd backend
./venv/Scripts/python.exe -c "
import csv, glob, os
from app.schemas import LabRecord
from app.mcp_server import classify_lab_result, classify_qualitative_result
for path in sorted(glob.glob('../test_data/*.csv')):
    row = next(csv.DictReader(open(path, encoding='utf-8-sig')))
    lab = LabRecord.model_validate(row)
    r = (classify_qualitative_result(lab.test_name, lab.result, lab.reference_range or '', lab.unit or '')
         if lab.is_qualitative else
         classify_lab_result(lab.test_name, lab.result, lab.unit or '', lab.min_reference, lab.max_reference))
    print(f'{os.path.basename(path):40} {str(lab.result):>8} -> {r[\"status\"]}')
"
```

### 5. API directly

```bash
curl -X POST http://127.0.0.1:8000/analyze_labs \
  -H "Content-Type: application/json" \
  -d '{"labs":[{"Test_Name":"Hemoglobin","Result":8.2,"Unit":"g/dL","Min_Reference":12,"Max_Reference":15}]}'
```

### 6. Watching the agent run

Every node and tool call is logged with a per-request id and timing:

```
[a1b2c3d4] ===== AGENT RUN START | 1 row(s) =====
[a1b2c3d4] NODE validate | 1 row(s) submitted
[a1b2c3d4] NODE translate | 4 field(s) across 1 record(s), 1 batched call
[a1b2c3d4]   renamed: Trombosit -> Platelet Count
[a1b2c3d4]     tool classify_lab_result -> ok (7ms)
[a1b2c3d4] NODE route | critical=1, warning=0, unknown=0, normal=0
[a1b2c3d4] BRANCH route -> critical_alert
[a1b2c3d4]     tool search_clinical_context (Platelet Count low) -> ok (1841ms)
[a1b2c3d4]       grounded via pubmed: 3 source(s)
[a1b2c3d4] ===== AGENT RUN END | {...} in 12.4s =====
```

Set `LOG_LEVEL=DEBUG` for more, `WARNING` for less.

---

## API

### `POST /analyze_labs`

Accepts the Kaggle dataset's columns. Only `Test_Name` and `Result` are required.

```json
{ "labs": [
    { "Test_Name": "Hemoglobin", "Result": 8.2, "Unit": "g/dL",
      "Min_Reference": 12, "Max_Reference": 15, "Status": "Dusuk",
      "Recommended_Followup": "Demir paneli onerilir" }
] }
```

Response:

```json
{
  "summary": { "critical": 1, "warning": 0, "normal": 0, "unknown": 0 },
  "results": {
    "critical": [{
      "test_name": "Hemoglobin",
      "test_name_original": "Hemoglobin",
      "value": 8.2, "unit": "g/dL",
      "status": "Critical",
      "reference_range": "12.0-15.0 g/dL",
      "deviation": "3.80 g/dL below the normal low (12.0-15.0)",
      "explanation": "…",
      "next_steps": "…",
      "sources": [{ "title": "…", "url": "https://pubmed.ncbi.nlm.nih.gov/…" }],
      "source_type": "pubmed",
      "urgent": true,
      "source_status": "Low",
      "source_followup": "Iron panel recommended"
    }],
    "warning": [], "unknown": [], "normal": []
  },
  "errors": [{ "test_name": null, "error": "Invalid/missing field(s): Test_Name" }],
  "thread_id": "a1b2c3d4"
}
```

### `GET /health` · `WS /ws/chat/{thread_id}`

Chat protocol is JSON both ways: `{"question": "…"}` in,
`{"type": "answer"|"error"|"status", "content": "…"}` out.

---

## Design decisions

**Why MCP over direct function calls.** The brief requires it, and it forces a genuine
boundary: `graph.py` cannot reach into classification logic, only call declared tools
over stdio. Tool failures surface as tool failures.

**Deterministic nodes, not an LLM-driven ReAct loop.** Which tool runs is decided in
Python, not by the model. Lab classification is a threshold comparison — making an LLM
decide it adds latency and non-determinism to something that has an exact answer.

**Critical thresholds come from the curated dictionary, not derived from the range.**
Deriving them as a fraction of the range span fails badly on wide ranges: for platelets
(150–450) it put `critical_low` at 0, so a count of **18 — a genuine emergency — scored
only "Warning."** The curated dictionary supplies real clinical critical bounds, with an
overlap check so a unit/scale mismatch falls back to derivation.

**PubMed queries are field-tagged, not keyword.** A naive query for "Hemoglobin low
clinical significance" returned papers on tirzepatide and malaria. Restricting to
`[Title/Abstract]` with `review[Publication Type]` returns "Iron Deficiency Anemia: An
Updated Review". Search is also by *direction* ("low"/"high") rather than the raw value,
since literature matches concepts, not measurements.

**Only abnormal results are researched.** Normal results skip search and next-step
generation entirely — most of a panel is normal, and this is the difference between a
usable demo and a two-minute wait.

**Chart colours were validated, not eyeballed.** Severity uses a status palette checked
with a CVD validator. Red-vs-green is inseparable under deuteranopia at *any* hue, and
the brief mandates red/amber/green — so severity is carried by **marker shape**
(circle/diamond/triangle), icon, text label, and position as well as colour. Colour is
never the only channel.

**The chart normalises per test.** A panel mixes g/dL, 10³/µL, %, mIU/L — one shared
value axis would be meaningless. Each test is scaled to its own reference range, making
"how far outside normal" the comparable quantity.

---

## Known limitations

- **Chat sessions are in-process.** `MemorySaver` holds checkpoints in memory, so a
  backend restart (including uvicorn's auto-reload) drops chat threads; the UI then
  reports the session is unavailable. `SqliteSaver`/`PostgresSaver` is a drop-in swap.
- **No caching.** Re-analysing the same CSV repeats every search and LLM call.
- **Reference ranges are adult, sex-agnostic**, and critical thresholds are conventional
  values, not institution-specific.
- **Literature search matches the lab direction, not the resulting condition.** Elevated
  TSH retrieves hyperthyroidism papers though it indicates *hypo*thyroidism; the model
  is given the sources as context rather than instruction, and corrects for this in
  practice, but a test→condition mapping would be a real improvement.
- **Not a diagnostic device.** Decision support only.

---

## Future work

### Move reference ranges into a database

Ranges currently live in a Python dictionary in `reference_ranges.py`. That is fast and
dependency-free, but it makes every threshold change a code change. A small **SQLite**
database (file-based, no server, and openable read-only by the MCP subprocess) would
address several of the limitations above at once:

```sql
reference_ranges(test_key, sex, age_min, age_max,
                 low, high, critical_low, critical_high,
                 unit, source, updated_at)
test_aliases(alias, test_key)      -- the Turkish source names live here
```

- **Editable without a redeploy** — a lab could adjust a threshold through an admin
  screen rather than a pull request.
- **Auditable** — `source` and `updated_at` record who changed a critical threshold and
  when, which matters for a clinical tool in a way a dict cannot express.
- **Demographic variants** — one test mapping to several rows keyed by sex and age band
  is a natural relational shape, and directly fixes the "adult, sex-agnostic" limitation.
- **Institution-specific ranges** — different laboratories legitimately use different
  bounds.

Note that this is **not** a performance change: dictionary lookup is already
microseconds, while the measured cost of an analysis is dominated by LLM latency. The
intended design keeps the hot path in memory — load the table into the existing
dictionary at MCP server startup, so the database is the authoring and audit surface
while `get_reference_range()` stays a plain lookup.

### Other candidates

- **Panel-level correlation.** Each result is currently judged in isolation. Real
  interpretation is cross-test: low haemoglobin *with* low ferritin suggests iron
  deficiency, while low haemoglobin with normal ferritin points elsewhere. A node
  between `route` and `explain` could detect such patterns and feed them to the
  explanation prompt.
- **Severity magnitude within a bucket.** Everything outside the normal band is
  "Warning" until it crosses critical, so a value marginally over the limit ranks
  equally with one far beyond it. A normalised "range-widths outside" score would let
  the UI sort worst-first inside each bucket.
- **Direction-aware thresholds.** Low LDL or low triglycerides are not clinically
  concerning, but the symmetric rule flags them; a per-test
  `direction: high | low | both` would fix it.
- **Caching.** Identical searches and explanations are recomputed on every run.
