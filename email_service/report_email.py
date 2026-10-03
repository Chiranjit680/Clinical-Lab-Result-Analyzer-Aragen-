"""Renders a stored analysis into the body of an email.

Two renderings of the same content are produced and sent together as
multipart/alternative: mail clients show the HTML, and anything that cannot
(or a reader who prefers plain text) falls back to the text version.

The analyzer's explanations are several hundred characters on a single line.
Left alone they arrive as one unbroken paragraph that is painful to read in a
mail client, so the text version is hard-wrapped and the HTML version is left
to the client's own layout.
"""

import html
import textwrap
from typing import Any, Dict, List, Optional

# Worst first: whoever opens this should see critical findings before anything
# else, not after a page of normal ones.
SECTIONS = [
    ("critical", "CRITICAL", "#c0392b"),
    ("warning", "WARNING", "#b9770e"),
    ("unknown", "UNKNOWN", "#5d6d7e"),
]

WRAP_WIDTH = 78

DISCLAIMER = "Clinical decision support - informational only, not a diagnosis."
SENT_BY = "Sent from the Clinical Lab Result Analyzer."


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _count(summary: Dict[str, Any], key: str) -> int:
    value = summary.get(key)
    return value if isinstance(value, int) else 0


def _headline(result: Dict[str, Any]) -> str:
    """"Test: value unit (reference range)" — the line a reader scans for."""
    name = result.get("test_name") or "(unnamed test)"
    value = result.get("value")
    unit = result.get("unit") or ""
    line = f"{name}: {value} {unit}".rstrip()
    reference = result.get("reference_range")
    return f"{line}  (reference {reference})" if reference else line


def _summary_line(summary: Dict[str, Any]) -> str:
    return (
        f"{_count(summary, 'critical')} critical, "
        f"{_count(summary, 'warning')} warning, "
        f"{_count(summary, 'normal')} normal, "
        f"{_count(summary, 'unknown')} unknown"
    )


# --------------------------------------------------------------------------
# plain text
# --------------------------------------------------------------------------


def _wrap(text: str, indent: str) -> str:
    return textwrap.fill(
        " ".join(str(text).split()),
        width=WRAP_WIDTH,
        initial_indent=indent,
        subsequent_indent=indent,
    )


def _text_result(result: Dict[str, Any]) -> str:
    lines = [_wrap(_headline(result), "  ")]

    # The measured deviation before the narrative: it is the concrete reason
    # the result was flagged, and it is short.
    if result.get("deviation"):
        lines.append(_wrap(f"Why flagged: {result['deviation']}", "      "))
    if result.get("explanation"):
        lines.append(_wrap(result["explanation"], "      "))
    if result.get("next_steps"):
        lines.append(_wrap(f"Next step: {result['next_steps']}", "      "))

    return "\n".join(lines)


def render_text(
    payload: Optional[Dict[str, Any]],
    patient_name: Optional[str] = None,
    note: Optional[str] = None,
) -> str:
    """Plain-text body, hard-wrapped. Works with no analysis at all."""
    who = f" for {patient_name}" if patient_name else ""
    blocks: List[str] = [_wrap(f"Attached is the lab report{who}.", "")]

    if note and note.strip():
        blocks.append(_wrap(note, ""))

    payload = _as_dict(payload)
    if not payload:
        # Sharing an unanalysed report is legitimate; say so rather than
        # implying the analysis found nothing.
        blocks.append(_wrap("This report has not been analysed yet.", ""))
        blocks.append(f"{SENT_BY}\n{DISCLAIMER}")
        return "\n\n".join(blocks)

    blocks.append(f"SUMMARY\n  {_summary_line(_as_dict(payload.get('summary')))}")

    results = _as_dict(payload.get("results"))
    for key, heading, _ in SECTIONS:
        items = _as_list(results.get(key))
        if not items:
            continue
        # The rule belongs to the heading, so they are one block — joining them
        # with the results would put a blank line between heading and rule.
        section = [f"{heading}\n{'-' * len(heading)}"]
        section.extend(_text_result(_as_dict(item)) for item in items)
        blocks.append("\n\n".join(section))

    normal = _as_list(results.get("normal"))
    if normal:
        blocks.append(f"{len(normal)} result(s) were within their reference range.")

    errors = _as_list(payload.get("errors"))
    if errors:
        lines = ["ROWS THAT COULD NOT BE READ", "-" * 26]
        for err in errors:
            err = _as_dict(err)
            lines.append(_wrap(f"{err.get('test_name') or '(unnamed row)'}: {err.get('error')}", "  "))
        blocks.append("\n".join(lines))

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
_CARD = "border-left:4px solid {colour};background:{tint};padding:10px 14px;margin:0 0 10px;"
_LABEL = "font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:#55606d;margin:8px 0 2px;"

_TINTS = {"#c0392b": "#fdecea", "#b9770e": "#fdf4e3", "#5d6d7e": "#eef1f4"}


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _html_result(result: Dict[str, Any], colour: str) -> str:
    parts = [
        f'<div style="{_CARD.format(colour=colour, tint=_TINTS.get(colour, "#f4f8fd"))}">',
        f'<div style="font-weight:600;font-size:15px;">{_e(_headline(result))}</div>',
    ]
    if result.get("deviation"):
        parts.append(f'<div style="{_LABEL}">Why flagged</div><div>{_e(result["deviation"])}</div>')
    if result.get("explanation"):
        parts.append(f'<div style="{_LABEL}">Explanation</div><div>{_e(result["explanation"])}</div>')
    if result.get("next_steps"):
        parts.append(f'<div style="{_LABEL}">Suggested next step</div><div>{_e(result["next_steps"])}</div>')
    parts.append("</div>")
    return "".join(parts)


def render_html(
    payload: Optional[Dict[str, Any]],
    patient_name: Optional[str] = None,
    note: Optional[str] = None,
) -> str:
    """HTML body carrying the same content as render_text."""
    who = f" for {_e(patient_name)}" if patient_name else ""
    out = [f'<div style="{_BODY_STYLE}">', f"<p>Attached is the lab report{who}.</p>"]

    if note and note.strip():
        out.append(f'<p style="padding:8px 12px;background:#f4f8fd;border-radius:6px;">{_e(note)}</p>')

    payload = _as_dict(payload)
    if not payload:
        out.append("<p>This report has not been analysed yet.</p>")
        out.append(f'<hr style="border:0;border-top:1px solid #dbe4ee;margin:18px 0;">')
        out.append(f'<p style="font-size:12px;color:#55606d;">{SENT_BY}<br>{DISCLAIMER}</p></div>')
        return "".join(out)

    summary = _as_dict(payload.get("summary"))
    chips = []
    for key, heading, colour in SECTIONS + [("normal", "NORMAL", "#1e8449")]:
        chips.append(
            f'<span style="display:inline-block;padding:4px 10px;margin:0 6px 6px 0;border-radius:12px;'
            f'background:{_TINTS.get(colour, "#eaf7ef")};color:{colour};font-weight:600;font-size:12px;">'
            f"{_count(summary, key)} {heading.title()}</span>"
        )
    out.append(f'<div style="margin:14px 0;">{"".join(chips)}</div>')

    results = _as_dict(payload.get("results"))
    for key, heading, colour in SECTIONS:
        items = _as_list(results.get(key))
        if not items:
            continue
        out.append(
            f'<h3 style="font-size:13px;letter-spacing:.06em;color:{colour};'
            f'margin:20px 0 8px;">{heading}</h3>'
        )
        out.extend(_html_result(_as_dict(item), colour) for item in items)

    normal = _as_list(results.get("normal"))
    if normal:
        out.append(
            f'<p style="color:#55606d;">{len(normal)} result(s) were within their reference range.</p>'
        )

    errors = _as_list(payload.get("errors"))
    if errors:
        out.append('<h3 style="font-size:13px;color:#5d6d7e;margin:20px 0 8px;">ROWS THAT COULD NOT BE READ</h3><ul>')
        for err in errors:
            err = _as_dict(err)
            out.append(f"<li>{_e(err.get('test_name') or '(unnamed row)')}: {_e(err.get('error'))}</li>")
        out.append("</ul>")

    out.append('<hr style="border:0;border-top:1px solid #dbe4ee;margin:18px 0;">')
    out.append(f'<p style="font-size:12px;color:#55606d;">{SENT_BY}<br>{DISCLAIMER}</p></div>')
    return "".join(out)
