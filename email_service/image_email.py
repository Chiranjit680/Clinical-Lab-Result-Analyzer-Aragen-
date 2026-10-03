"""Renders a stored image analysis into the body of an email.

The companion of report_email: that one renders a lab analysis, which is a set
of measured values with severities, while this one renders a VLM run over a
radiological image, which is prose. Same contract — a plain-text and an HTML
rendering of the same content, sent together as multipart/alternative — and the
same hard-wrapping of the text version, since the agents' answers arrive as very
long single lines.

The payload is the agent service's own response:

    {"answer": str, "global_summary": str, "question": str, "model": str,
     "run_id": str, "seconds": float, "tiles": [{"tile_id": str, "report": str}]}
"""

import html
import textwrap
from typing import Any, Dict, List, Optional

WRAP_WIDTH = 78

# The per-tile reports are the agents' working, not the finding. Worth sending
# — they say where in the image the evidence was — but after the answer, and
# only the ones that saw something.
QUIET = "nothing relevant"

DISCLAIMER = "Clinical decision support - informational only, not a radiological diagnosis."
SENT_BY = "Sent from the Clinical Lab Result Analyzer."


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _tiles_with_findings(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    tiles = [_as_dict(tile) for tile in _as_list(payload.get("tiles"))]
    found = [t for t in tiles if _text(t.get("report")) and QUIET not in _text(t.get("report")).lower()]
    return sorted(found, key=lambda t: _text(t.get("tile_id")))


def _provenance(payload: Dict[str, Any]) -> str:
    """Model, duration and tile count — what the reader needs to judge the run."""
    bits = []
    if _text(payload.get("model")):
        bits.append(_text(payload.get("model")))
    seconds = payload.get("seconds")
    if isinstance(seconds, (int, float)):
        bits.append(f"{seconds:.0f}s")
    tiles = _as_list(payload.get("tiles"))
    if tiles:
        bits.append(f"{len(tiles)} region agent" + ("s" if len(tiles) != 1 else ""))
    return " / ".join(bits)


# --------------------------------------------------------------------------
# plain text
# --------------------------------------------------------------------------


def _wrap(text: str, indent: str = "") -> str:
    return textwrap.fill(
        " ".join(str(text).split()),
        width=WRAP_WIDTH,
        initial_indent=indent,
        subsequent_indent=indent,
    )


def render_text(
    payload: Optional[Dict[str, Any]],
    patient_name: Optional[str] = None,
    caption: Optional[str] = None,
    note: Optional[str] = None,
) -> str:
    """Plain-text body, hard-wrapped. Works with no analysis at all."""
    who = f" for {patient_name}" if patient_name else ""
    what = caption or "radiological image"
    blocks: List[str] = [_wrap(f"Attached is the {what}{who}.")]

    if note and note.strip():
        blocks.append(_wrap(note))

    payload = _as_dict(payload)
    if not payload:
        # Sharing an unanalysed image is legitimate; say so rather than
        # implying the analysis found nothing.
        blocks.append(_wrap("This image has not been analysed yet."))
        blocks.append(f"{SENT_BY}\n{DISCLAIMER}")
        return "\n\n".join(blocks)

    if _text(payload.get("question")):
        blocks.append(_wrap(f"Question asked: {_text(payload['question'])}"))

    answer = _text(payload.get("answer"))
    if answer:
        blocks.append("FINDINGS\n--------\n" + _wrap(answer, "  "))

    summary = _text(payload.get("global_summary"))
    if summary:
        blocks.append("WHOLE-IMAGE VIEW\n----------------\n" + _wrap(summary, "  "))

    found = _tiles_with_findings(payload)
    if found:
        # The rule belongs to the heading, so they are one entry — joining them
        # with the reports would put a blank line between heading and rule.
        section = ["REGIONS REPORTING FINDINGS\n" + "-" * 26]
        section.extend(
            _wrap(f"[{_text(tile.get('tile_id'))}] {_text(tile.get('report'))}", "  ")
            for tile in found
        )
        blocks.append("\n\n".join(section))

    provenance = _provenance(payload)
    if provenance:
        blocks.append(_wrap(f"Analysed by {provenance}."))

    blocks.append(f"{SENT_BY}\n{DISCLAIMER}")
    return "\n\n".join(blocks)


# --------------------------------------------------------------------------
# html
# --------------------------------------------------------------------------

# Inline styles throughout: many mail clients strip <style> blocks entirely.
_BODY_STYLE = (
    "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
    "font-size:14px;line-height:1.5;color:#1c2733;max-width:680px;"
)
_HEADING = "font-size:13px;letter-spacing:.06em;color:#2b6cb0;margin:20px 0 8px;"
_ANSWER = "border-left:4px solid #2b6cb0;background:#f4f8fd;padding:10px 14px;margin:0 0 10px;"
_TILE = "border-left:3px solid #dbe4ee;padding:6px 12px;margin:0 0 8px;"
_TILE_ID = "font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#55606d;"


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def render_html(
    payload: Optional[Dict[str, Any]],
    patient_name: Optional[str] = None,
    caption: Optional[str] = None,
    note: Optional[str] = None,
) -> str:
    """HTML body carrying the same content as render_text."""
    who = f" for {_e(patient_name)}" if patient_name else ""
    what = _e(caption) if caption else "radiological image"
    out = [f'<div style="{_BODY_STYLE}">', f"<p>Attached is the {what}{who}.</p>"]

    if note and note.strip():
        out.append(f'<p style="padding:8px 12px;background:#f4f8fd;border-radius:6px;">{_e(note)}</p>')

    payload = _as_dict(payload)
    if not payload:
        out.append("<p>This image has not been analysed yet.</p>")
        out.append('<hr style="border:0;border-top:1px solid #dbe4ee;margin:18px 0;">')
        out.append(f'<p style="font-size:12px;color:#55606d;">{SENT_BY}<br>{DISCLAIMER}</p></div>')
        return "".join(out)

    if _text(payload.get("question")):
        out.append(
            f'<p style="color:#55606d;"><em>Question asked: {_e(_text(payload["question"]))}</em></p>'
        )

    answer = _text(payload.get("answer"))
    if answer:
        out.append(f'<h3 style="{_HEADING}">FINDINGS</h3>')
        out.append(f'<div style="{_ANSWER}">{_paragraphs(answer)}</div>')

    summary = _text(payload.get("global_summary"))
    if summary:
        out.append(f'<h3 style="{_HEADING}">WHOLE-IMAGE VIEW</h3>')
        out.append(f"<div>{_paragraphs(summary)}</div>")

    found = _tiles_with_findings(payload)
    if found:
        out.append(f'<h3 style="{_HEADING}">REGIONS REPORTING FINDINGS</h3>')
        for tile in found:
            out.append(
                f'<div style="{_TILE}">'
                f'<div style="{_TILE_ID}">{_e(_text(tile.get("tile_id")))}</div>'
                f"<div>{_e(_text(tile.get('report')))}</div></div>"
            )

    provenance = _provenance(payload)
    out.append('<hr style="border:0;border-top:1px solid #dbe4ee;margin:18px 0;">')
    footer = f"Analysed by {_e(provenance)}.<br>" if provenance else ""
    out.append(f'<p style="font-size:12px;color:#55606d;">{footer}{SENT_BY}<br>{DISCLAIMER}</p></div>')
    return "".join(out)


def _paragraphs(text: str) -> str:
    """Keep the agents' own line breaks: their answers are often lists."""
    chunks = [chunk.strip() for chunk in str(text).split("\n") if chunk.strip()]
    return "".join(f'<p style="margin:0 0 8px;">{_e(chunk)}</p>' for chunk in chunks)
