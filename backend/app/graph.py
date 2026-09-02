"""LangGraph orchestration for lab analysis.

Pipeline: Validate -> Classify -> Route -> [conditional: critical_alert] -> Explain -> Aggregate.

Every node is deterministic and calls the same MCP tools the previous
asyncio-based agent called directly (classify_lab_result, reference_range_lookup,
explain_result) — LangGraph just gives the pipeline an explicit graph shape
with a real conditional branch on severity, instead of a plain function.
"""

from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import ValidationError

from app.mcp_client import MCPToolClient
from app.schemas import LabRecord

BUCKET_ORDER = ["critical", "warning", "unknown", "normal"]


class GraphState(TypedDict, total=False):
    raw_labs: List[Dict[str, Any]]
    validated: List[LabRecord]
    errors: List[dict]
    classified: List[dict]
    buckets: Dict[str, List[dict]]
    has_critical: bool
    response: Dict[str, Any]


async def _classify_one(client: MCPToolClient, lab: LabRecord, errors: List[dict]) -> Optional[Dict[str, Any]]:
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


def build_graph(client: MCPToolClient):
    """Compile the StateGraph, closing over the (already-started) MCP client."""

    async def validate_node(state: GraphState) -> dict:
        validated, errors = [], []
        for raw in state["raw_labs"]:
            try:
                validated.append(LabRecord.model_validate(raw))
            except ValidationError as exc:
                name = raw.get("Test_Name") or raw.get("test_name")
                missing = ", ".join(sorted({str(e["loc"][-1]) for e in exc.errors()}))
                errors.append({"test_name": name, "error": f"Invalid/missing field(s): {missing}"})
        return {"validated": validated, "errors": errors}

    async def classify_node(state: GraphState) -> dict:
        classified = []
        errors = list(state.get("errors", []))
        for lab in state["validated"]:
            result = await _classify_one(client, lab, errors)
            if result is not None:
                classified.append(result)
        return {"classified": classified, "errors": errors}

    async def route_node(state: GraphState) -> dict:
        buckets: Dict[str, List[dict]] = {key: [] for key in BUCKET_ORDER}
        for result in state["classified"]:
            key = str(result.get("status", "Unknown")).lower()
            buckets[key if key in buckets else "unknown"].append(result)
        return {"buckets": buckets, "has_critical": len(buckets["critical"]) > 0}

    def route_condition(state: GraphState) -> str:
        return "critical_alert" if state.get("has_critical") else "explain"

    async def critical_alert_node(state: GraphState) -> dict:
        """Runs only when at least one Critical result exists; flags it for urgent review."""
        for result in state["buckets"]["critical"]:
            result["urgent"] = True
        return {"buckets": state["buckets"]}

    async def explain_node(state: GraphState) -> dict:
        buckets = state["buckets"]
        ordered = [r for key in BUCKET_ORDER for r in buckets[key]]
        for result in ordered:
            status = result.get("status", "Unknown")
            base_args = {
                "test_name": result["test_name"],
                "value": result["value"],
                "unit": result.get("unit", ""),
                "status": status,
                "reference_range": result.get("reference_range") or "unknown",
            }

            # Only research abnormal results — Normal results don't need grounding.
            context = ""
            result["sources"] = []
            if status in ("Critical", "Warning"):
                # Search by direction ("low"/"high") rather than the raw value —
                # literature search matches concepts, not specific measurements.
                deviation = result.get("deviation") or ""
                direction = "low" if "below" in deviation else "high" if "above" in deviation else "abnormal"
                try:
                    search = await client.call_tool(
                        "search_clinical_context",
                        {"test_name": result["test_name"], "direction": direction, "max_results": 3},
                    )
                    if search.get("found"):
                        hits = search.get("results", [])
                        context = "\n".join(
                            f"- {r.get('title', '')}: {r.get('snippet', '')}" for r in hits
                        )
                        result["sources"] = [
                            {"title": r.get("title", ""), "url": r.get("url", "")} for r in hits
                        ]
                        result["source_type"] = search.get("source", "")
                except Exception:
                    context = ""

            try:
                explain_resp = await client.call_tool("explain_result", {**base_args, "context": context})
            except Exception as exc:
                explain_resp = {"explanation": f"Unable to generate an explanation right now ({exc})."}
            result["explanation"] = explain_resp.get("explanation", "")

            if status == "Normal":
                result["next_steps"] = result.get("source_followup") or "No action needed."
                continue

            try:
                next_steps_resp = await client.call_tool(
                    "get_next_steps",
                    {**base_args, "explanation": result["explanation"], "context": context},
                )
            except Exception:
                next_steps_resp = {"next_steps": "Review with a clinician."}
            result["next_steps"] = next_steps_resp.get("next_steps", "") or (result.get("source_followup") or "")
        return {"buckets": buckets}

    async def aggregate_node(state: GraphState) -> dict:
        buckets = state["buckets"]
        summary = {key: len(buckets[key]) for key in BUCKET_ORDER}
        return {
            "response": {
                "summary": summary,
                "results": buckets,
                "errors": state.get("errors", []),
            }
        }

    graph = StateGraph(GraphState)
    graph.add_node("validate", validate_node)
    graph.add_node("classify", classify_node)
    graph.add_node("route", route_node)
    graph.add_node("critical_alert", critical_alert_node)
    graph.add_node("explain", explain_node)
    graph.add_node("aggregate", aggregate_node)

    graph.set_entry_point("validate")
    graph.add_edge("validate", "classify")
    graph.add_edge("classify", "route")
    graph.add_conditional_edges("route", route_condition, {"critical_alert": "critical_alert", "explain": "explain"})
    graph.add_edge("critical_alert", "explain")
    graph.add_edge("explain", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()
