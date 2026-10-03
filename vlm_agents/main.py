"""HTTP front door for the VLM agent graph.

Run from the repository root, so `vlm_agents` imports as a package and the MCP
tool server (spawned as `python -m vlm_agents.mcp_server`) can be found:

    python -m uvicorn vlm_agents.main:app --port 8084

Stateless by design: the image arrives with the request and the result goes
back in the response. Nothing is written to disk, so the run store stays on its
NullStore and the per-agent traces travel in the response instead.
"""

import io
import os
import time
import uuid
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from . import config, graph, logs

# The package's own setup, not basicConfig: it is what adds the agent and run
# labels, without which the tile agents on parallel threads are indistinguishable.
logs.setup(level=os.environ.get("LOG_LEVEL", "INFO"), logfile=os.environ.get("VLM_LOG_FILE"))
log = logs.get("api")

app = FastAPI(title="VLM Agents")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_BYTES = 20 * 1024 * 1024

# Compiled once: building it per request would rewire 11 nodes every time.
_graph = graph.build_graph()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": config.VLM_MODEL,
        "tiles": config.TILE_GRID * config.TILE_GRID,
    }


@app.post("/analyze_image")
async def analyze_image(
    file: UploadFile = File(...),
    question: Optional[str] = Form(None),
) -> dict:
    """Run the agent graph over one image.

    Slow by nature: a global agent plus a grid of tile agents, each allowed
    several tool steps, is tens of model calls.
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded image is empty.")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="That image is larger than the 20 MB limit.")

    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        # DICOM lands here: Pillow cannot open it without a plugin, and saying
        # so beats a stack trace about an unknown format.
        raise HTTPException(
            status_code=415,
            detail=f"Could not read '{file.filename}' as an image. PNG and JPEG are supported; "
                   "DICOM is not.",
        ) from exc

    task = (question or "").strip() or graph.DEFAULT_QUESTION
    run_id = uuid.uuid4().hex[:8]

    # Everything the run logs — nodes, agent steps, tool calls, model calls —
    # carries this id, so one run can be followed through interleaved output.
    with logs.run_context(run_id):
        log.info("=== RUN START | %s | %dx%d %s | %d bytes ===",
                 file.filename, *image.size, image.mode, len(data))
        log.info("question: %s", logs.short(task, 200))
        log.info("plan: 1 global agent + %d tile agents (%dx%d grid), up to %d tool steps each",
                 config.TILE_GRID ** 2, config.TILE_GRID, config.TILE_GRID, config.MAX_TOOL_STEPS)

        started = time.perf_counter()
        try:
            # The graph is synchronous and fans out across threads; off the
            # event loop it goes, or it would block every other request.
            state = await run_in_threadpool(_graph.invoke, {"image": image, "question": task})
        except Exception as exc:
            log.error("=== RUN FAILED after %.1fs: %s ===", time.perf_counter() - started, exc)
            log.exception("graph failed for %s", file.filename)
            raise HTTPException(status_code=502, detail=f"Image analysis failed: {exc}") from exc

        seconds = round(time.perf_counter() - started, 1)
        reports = state.get("tile_reports", [])
        with_findings = [
            r for r in reports if "nothing relevant" not in str(r.get("report", "")).lower()
        ]
        log.info("=== RUN END | %.1fs | %d/%d tiles reported findings ===",
                 seconds, len(with_findings), len(reports))
        log.info("answer: %s", logs.short(state.get("answer", "")))

    return {
        "answer": state.get("answer", ""),
        "global_summary": state.get("global_summary", ""),
        # Traces are dropped here: they carry per-step images and would dwarf
        # the useful payload.
        "tiles": [
            {"tile_id": report.get("tile_id"), "report": report.get("report", "")}
            for report in state.get("tile_reports", [])
        ],
        "question": task,
        "seconds": seconds,
        "model": config.VLM_MODEL,
        # Lets a caller correlate a response with the server-side log of its run.
        "run_id": run_id,
    }
