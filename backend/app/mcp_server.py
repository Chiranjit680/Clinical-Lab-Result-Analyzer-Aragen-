"""MCP server exposing the three tools the agent uses: classify, reference
range lookup (fallback for unknown tests), and explain. Run standalone via
`python -m app.mcp_server`, or spawned as a subprocess by mcp_client.py.
"""

import json

from mcp.server.fastmcp import FastMCP

from app.llm import call_llm
from app.reference_ranges import get_reference_range

mcp = FastMCP("results-analyzer")


@mcp.tool()
def classify_lab_result(
    test_name: str,
    value: float,
    unit: str,
    min_ref: float | None = None,
    max_ref: float | None = None,
) -> dict:
    """Classify a single lab result against a reference range.

    If min_ref/max_ref are supplied (e.g. from the source dataset row), they
    take priority over the local reference-range dictionary. Critical bounds
    aren't in the dataset, so they're derived as 50% beyond the normal band.
    """
    if min_ref is not None and max_ref is not None:
        low, high = min_ref, max_ref
        span = high - low
        crit_low, crit_high = low - span * 0.5, high + span * 0.5
        ref_unit = unit
    else:
        ref = get_reference_range(test_name)
        if ref is None:
            return {
                "test_name": test_name,
                "value": value,
                "unit": unit,
                "status": "Unknown",
                "reference_range": None,
                "deviation": None,
            }
        low, high = ref["low"], ref["high"]
        crit_low, crit_high = ref["critical_low"], ref["critical_high"]
        ref_unit = ref.get("unit", unit)

    if value < crit_low or value > crit_high:
        status = "Critical"
    elif value < low or value > high:
        status = "Warning"
    else:
        status = "Normal"

    deviation = None
    if value < low:
        deviation = f"{low - value:.2f} {ref_unit} below the normal low ({low}-{high})"
    elif value > high:
        deviation = f"{value - high:.2f} {ref_unit} above the normal high ({low}-{high})"

    return {
        "test_name": test_name,
        "value": value,
        "unit": ref_unit,
        "status": status,
        "reference_range": f"{low}-{high} {ref_unit}",
        "deviation": deviation,
    }


@mcp.tool()
def reference_range_lookup(test_name: str) -> dict:
    """LLM-assisted fallback lookup for a lab test not in the local dictionary."""
    prompt = (
        f"Provide the typical adult clinical reference range for the lab test '{test_name}'. "
        'Respond with ONLY compact JSON in this exact shape: '
        '{"low": <number>, "high": <number>, "critical_low": <number>, '
        '"critical_high": <number>, "unit": "<unit>"}'
    )
    raw = call_llm(
        prompt,
        system="You are a clinical reference data assistant. Respond with JSON only, no prose.",
    )
    if raw is None:
        return {"found": False}
    try:
        start, end = raw.index("{"), raw.rindex("}") + 1
        data = json.loads(raw[start:end])
        data["found"] = True
        return data
    except (ValueError, json.JSONDecodeError):
        return {"found": False}


@mcp.tool()
def explain_result(test_name: str, value: float, unit: str, status: str, reference_range: str) -> dict:
    """Generate a clinically relevant explanation and next-step suggestion."""
    prompt = (
        f"Lab test: {test_name}\n"
        f"Value: {value} {unit}\n"
        f"Reference range: {reference_range}\n"
        f"Status: {status}\n\n"
        "In 2-3 sentences, explain in clinically relevant but plain language why this "
        "result is flagged (or confirm it's normal) and what it commonly indicates. "
        "Then on a new line starting with 'Next step:' suggest one concrete, concise "
        "next action a clinician might take."
    )
    raw = call_llm(
        prompt,
        system=(
            "You are a clinical decision-support assistant. Be concise and factual. "
            "Do not provide a definitive diagnosis."
        ),
    )
    if raw is None:
        fallback_step = "No action needed." if status == "Normal" else "Review with a clinician."
        return {
            "explanation": f"{test_name} is {status.lower()} relative to the reference range {reference_range}.",
            "next_steps": fallback_step,
            "source": "fallback",
        }

    explanation, next_steps = raw.strip(), "Discuss with a clinician."
    if "Next step:" in raw:
        before, after = raw.split("Next step:", 1)
        explanation, next_steps = before.strip(), after.strip()
    return {"explanation": explanation, "next_steps": next_steps, "source": "llm"}


if __name__ == "__main__":
    mcp.run()
