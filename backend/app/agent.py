"""Agent orchestration: Classify -> Route -> Explain.

This module holds no business logic of its own — every classification,
lookup, and explanation is delegated to the MCP server via MCPToolClient,
per the assignment's "all communication by Agent goes through MCP" constraint.
"""

from typing import Any, Dict, List

from pydantic import ValidationError

from app.mcp_client import MCPToolClient
from app.schemas import LabRecord

BUCKET_ORDER = ["critical", "warning", "unknown", "normal"]


def _validate(raw_labs: List[Dict[str, Any]]) -> tuple[list[LabRecord], list[dict]]:
    """Validate each row against LabRecord so one bad row doesn't fail the batch."""
    validated, errors = [], []
    for raw in raw_labs:
        try:
            validated.append(LabRecord.model_validate(raw))
        except ValidationError as exc:
            name = raw.get("Test_Name") or raw.get("test_name")
            missing = ", ".join(sorted({str(e["loc"][-1]) for e in exc.errors()}))
            errors.append({"test_name": name, "error": f"Invalid/missing field(s): {missing}"})
    return validated, errors


async def _classify(client: MCPToolClient, lab: LabRecord, errors: List[dict]) -> Dict[str, Any] | None:
    args = {
        "test_name": lab.test_name,
        "value": lab.result,
        "unit": lab.unit or "",
        "min_ref": lab.min_refer,
        "max_ref": lab.max_refer,
    }
    try:
        result = await client.call_tool("classify_lab_result", args)
    except Exception as exc:
        errors.append({"test_name": lab.test_name, "error": f"Classification failed: {exc}"})
        return None

    if result.get("status") == "Unknown":
        # Unknown test with no dataset range: fall back to the LLM-assisted lookup tool.
        try:
            lookup = await client.call_tool("reference_range_lookup", {"test_name": lab.test_name})
        except Exception:
            lookup = {"found": False}

        parsed = None
        if lookup.get("found"):
            try:
                low = float(lookup["low"])
                high = float(lookup["high"])
                crit_low = float(lookup.get("critical_low", low))
                crit_high = float(lookup.get("critical_high", high))
                parsed = (low, high, crit_low, crit_high)
            except (KeyError, TypeError, ValueError):
                parsed = None

        if parsed is not None:
            low, high, crit_low, crit_high = parsed
            ref_unit = lookup.get("unit", lab.unit or "")
            if lab.result < crit_low or lab.result > crit_high:
                status = "Critical"
            elif lab.result < low or lab.result > high:
                status = "Warning"
            else:
                status = "Normal"
            result = {
                "test_name": lab.test_name,
                "value": lab.result,
                "unit": ref_unit,
                "status": status,
                "reference_range": f"{low}-{high} {ref_unit}",
                "deviation": None,
            }

    result["source_status"] = lab.status
    result["source_followup"] = lab.recommended_followup
    return result


async def analyze_labs(client: MCPToolClient, raw_labs: List[Dict[str, Any]]) -> Dict[str, Any]:
    validated, errors = _validate(raw_labs)

    # Classify
    classified = []
    for lab in validated:
        result = await _classify(client, lab, errors)
        if result is not None:
            classified.append(result)

    # Route: group by severity, critical first
    buckets: Dict[str, List[dict]] = {key: [] for key in BUCKET_ORDER}
    for result in classified:
        key = str(result.get("status", "Unknown")).lower()
        buckets[key if key in buckets else "unknown"].append(result)

    ordered = [r for key in BUCKET_ORDER for r in buckets[key]]

    # Explain
    for result in ordered:
        try:
            explanation = await client.call_tool(
                "explain_result",
                {
                    "test_name": result["test_name"],
                    "value": result["value"],
                    "unit": result.get("unit", ""),
                    "status": result.get("status", "Unknown"),
                    "reference_range": result.get("reference_range") or "unknown",
                },
            )
        except Exception as exc:
            explanation = {
                "explanation": f"Unable to generate an explanation right now ({exc}).",
                "next_steps": "Review manually.",
            }
        result["explanation"] = explanation.get("explanation", "")
        result["next_steps"] = explanation.get("next_steps", "") or (result.get("source_followup") or "")

    summary = {key: len(buckets[key]) for key in BUCKET_ORDER}
    return {
        "summary": summary,
        "results": buckets,
        "errors": errors,
    }
