"""Email service: shares a lab report, and its analysis, by email.

Deliberately stateless and ignorant of the rest of the system. It holds no
database connection and reads no shared folder — patientService owns the report
file and the analysis, and posts both here. The only thing this service owns is
the Gmail credential.

Run with: `python -m uvicorn main:app --port 8083` from this directory.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from email_sender import EmailSender
from image_email import render_html as render_image_html
from image_email import render_text as render_image_text
from report_email import render_html, render_text

HERE = Path(__file__).resolve().parent

# Loaded by explicit path rather than by searching upwards from the working
# directory, so the service behaves the same however it is started — from this
# folder, from the repository root, or as a container entrypoint. Existing
# environment variables still win, so a deployment can override the file.
load_dotenv(HERE / ".env")

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("email_service")

app = FastAPI(title="Email Service")

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

# Built once, connected on first use. Connecting at import would open a browser
# for OAuth consent during startup, which is the wrong moment for it.
_sender = EmailSender()
_connected = False

# Stored reports are saved as "<uuid>__original-name.pdf". The recipient should
# see the original name.
NAME_SEPARATOR = "__"

# Gmail rejects messages over 25 MB and base64 inflates an attachment by about
# a third, so the raw ceiling sits below the advertised limit.
MAX_BYTES = int(os.environ.get("EMAIL_MAX_ATTACHMENT_MB", "18")) * 1024 * 1024


def _ensure_connected() -> None:
    global _connected
    if not _connected:
        try:
            _sender.connect()
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Gmail is not configured on the email service: {exc}",
            ) from exc
        _connected = True


def _display_name(filename: Optional[str]) -> str:
    name = Path(filename or "report.pdf").name
    head, sep, tail = name.partition(NAME_SEPARATOR)
    return tail if sep and tail else name


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "gmail_connected": _connected}


def _read_attachment(data: bytes, kind: str) -> None:
    """Shared validation for both endpoints; `kind` only shapes the message."""
    if not data:
        raise HTTPException(status_code=400, detail=f"The uploaded {kind} is empty.")
    if len(data) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"That {kind} is larger than the {MAX_BYTES // (1024 * 1024)} MB limit.",
        )


def _parse_analysis(analysis_json: Optional[str]) -> Optional[dict]:
    if not analysis_json:
        return None
    try:
        return json.loads(analysis_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=422, detail=f"analysis_json is not valid JSON: {exc}"
        ) from exc


def _send(to: str, subject: str, body: str, html_body: str, data: bytes, name: str) -> None:
    """Spill the upload to a temp file, send, and remove it.

    EmailSender attaches from a path, and the temporary directory is gone as
    soon as the message has been built.
    """
    _ensure_connected()

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        path.write_bytes(data)

        sent = _sender.send_email(
            to=to, subject=subject, body=body, html_body=html_body, attachments=[(path, name)]
        )

    if not sent:
        raise HTTPException(status_code=502, detail="Gmail rejected the message.")


@app.post("/send_report")
async def send_report(
    to: str = Form(...),
    file: UploadFile = File(...),
    patient_name: Optional[str] = Form(None),
    analysis_json: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
) -> dict:
    """Email one report, with its analysis rendered into the body.

    `analysis_json` is the analyzer's stored payload. It is optional: a report
    with no analysis is still worth sharing.
    """
    data = await file.read()
    _read_attachment(data, "report")
    payload = _parse_analysis(analysis_json)

    name = _display_name(file.filename)
    who = f" for {patient_name}" if patient_name else ""

    _send(
        to=to,
        subject=f"Lab report{who}",
        body=render_text(payload, patient_name, note),
        html_body=render_html(payload, patient_name, note),
        data=data,
        name=name,
    )

    logger.info("Report '%s' emailed to %s", name, to)
    return {"status": "sent", "to": to, "attachment": name}


@app.post("/send_image")
async def send_image(
    to: str = Form(...),
    file: UploadFile = File(...),
    patient_name: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    analysis_json: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
) -> dict:
    """Email one radiological image, with its VLM analysis in the body.

    A separate endpoint rather than a flag on /send_report: the two analyses
    have nothing in common beyond being attached to a file. A lab analysis is
    measured values with severities, an image analysis is prose from the agents,
    and one renderer for both would serve neither.

    `caption` is what the image is — "XRAY - Chest". patientService knows that
    from its own tables; this service has no way to.
    """
    data = await file.read()
    _read_attachment(data, "image")
    payload = _parse_analysis(analysis_json)

    name = _display_name(file.filename)
    who = f" for {patient_name}" if patient_name else ""
    what = caption.strip() if caption and caption.strip() else "Radiological image"

    _send(
        to=to,
        subject=f"{what}{who}",
        body=render_image_text(payload, patient_name, caption, note),
        html_body=render_image_html(payload, patient_name, caption, note),
        data=data,
        name=name,
    )

    logger.info("Image '%s' emailed to %s", name, to)
    return {"status": "sent", "to": to, "attachment": name}
