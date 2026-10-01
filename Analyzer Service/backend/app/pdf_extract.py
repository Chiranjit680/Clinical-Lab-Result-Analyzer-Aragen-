"""Turn a PDF lab report into validated lab rows.

Two stages, deliberately separate:

1. `extract_text` pulls the text out locally with pypdf. No model involved, so
   a text-layer PDF costs nothing and cannot be hallucinated.
2. `extract_report` asks the LLM to turn that text into rows, then validates the
   reply against ExtractedReport. Nothing unvalidated reaches the analysis
   graph: a malformed or invented response fails here, loudly, rather than
   quietly producing wrong clinical output.

The model is given one retry, with the validation error fed back to it, because
a first-attempt schema miss is usually a near-miss worth correcting.
"""

import io
import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from app.llm import call_llm
from app.schemas import ExtractedReport

logger = logging.getLogger("agent.pdf")

# Long reports are truncated rather than refused: lab values sit near the top
# of most reports, and an over-long prompt fails for every provider.
MAX_PROMPT_CHARS = 12000

SYSTEM = (
    "You extract laboratory results from clinical report text. "
    "You reply with JSON only - no prose, no markdown fences. "
    "You never invent values: if a field is not present in the text, omit it or use null."
)

PROMPT_TEMPLATE = """Extract every laboratory test result from this report.

Return JSON of exactly this shape:

{{
  "patient_name": string or null,
  "report_date": string or null,
  "labs": [
    {{
      "test_name": string,
      "result": number or string,
      "unit": string or null,
      "reference_range": string or null,
      "min_reference": number or null,
      "max_reference": number or null
    }}
  ]
}}

Rules:
- Include one entry per test. Do not merge or summarise tests.
- "result" keeps the reported value: a number when numeric, otherwise the text
  as printed (for example "Negative", "1+", "Trace").
- When the reference range is printed as "4.0-6.0", also split it into
  min_reference 4.0 and max_reference 6.0. Leave both null for qualitative tests.
- Copy values exactly as printed. Never estimate, convert, or fill in a value
  that is not in the text.

REPORT TEXT:
{text}
"""


def extract_text(data: bytes) -> str:
    """Read the PDF's text layer. Raises ValueError when there is nothing to read."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ValueError(f"Could not read that PDF: {type(exc).__name__}") from exc

    text = "\n".join(pages).strip()
    if not text:
        # Scanned reports are images; without OCR there is genuinely no text.
        raise ValueError(
            "This PDF has no extractable text. It is probably a scan, which needs OCR "
            "that this service does not do yet."
        )
    return text


def _loads_json(raw: str) -> Any:
    """Tolerate the fences and stray prose models add around JSON."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fall back to the outermost {...} span.
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("The model did not return JSON.")
        return json.loads(cleaned[start : end + 1])


def extract_report(text: str) -> ExtractedReport:
    """Ask the LLM for rows and validate them. Raises ValueError if it cannot."""
    prompt = PROMPT_TEMPLATE.format(text=text[:MAX_PROMPT_CHARS])
    last_error = ""

    for attempt in (1, 2):
        reply = call_llm(prompt if attempt == 1 else f"{prompt}\n\nYour previous reply was rejected: {last_error}\nReturn corrected JSON only.", SYSTEM)
        if not reply:
            last_error = "the model returned nothing"
            logger.warning("PDF extraction attempt %d: empty LLM response", attempt)
            continue

        try:
            report = ExtractedReport.model_validate(_loads_json(reply))
        except (ValueError, ValidationError) as exc:
            last_error = str(exc)[:500]
            logger.warning("PDF extraction attempt %d failed validation: %s", attempt, last_error)
            continue

        logger.info("PDF extraction succeeded on attempt %d with %d row(s)", attempt, len(report.labs))
        return report

    raise ValueError(f"Could not extract lab results from this PDF: {last_error}")
