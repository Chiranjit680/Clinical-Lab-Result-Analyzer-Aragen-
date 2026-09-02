"""LangGraph orchestration for lab analysis.

Pipeline: Validate -> Classify -> Route -> [conditional: critical_alert] -> Explain -> Aggregate.

Every node is deterministic and calls the same MCP tools the previous
asyncio-based agent called directly (classify_lab_result, reference_range_lookup,
explain_result) — LangGraph just gives the pipeline an explicit graph shape
with a real conditional branch on severity, instead of a plain function.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt
from pydantic import ValidationError

from app.mcp_client import MCPToolClient
from app.schemas import LabRecord

logger = logging.getLogger("agent")

BUCKET_ORDER = ["critical", "warning", "unknown", "normal"]


class GraphState(TypedDict, total=False):
    run_id: str
    raw_labs: List[Dict[str, Any]]
    validated: List[LabRecord]
    errors: List[dict]
    classified: List[dict]
    buckets: Dict[str, List[dict]]
    has_critical: bool
    response: Dict[str, Any]
    # Follow-up chat, held open after the analysis completes.
    messages: List[Dict[str, str]]


def _log(state: GraphState, message: str, level: int = logging.INFO) -> None:
    logger.log(level, "[%s] %s", state.get("run_id", "-"), message)


async def _call_tool_logged(
    client: MCPToolClient, state: GraphState, name: str, args: Dict[str, Any], label: str = ""
) -> Dict[str, Any]:
    """Wrap every MCP call so each crossing of the process boundary is visible,
    with its duration — the tool calls are where nearly all the latency lives."""
    started = time.perf_counter()
    suffix = f" {label}" if label else ""
    try:
        result = await client.call_tool(name, args)
    except Exception as exc:
        elapsed = (time.perf_counter() - started) * 1000
        _log(state, f"    tool {name}{suffix} FAILED after {elapsed:.0f}ms: {exc}", logging.WARNING)
        raise
    elapsed = (time.perf_counter() - started) * 1000
    _log(state, f"    tool {name}{suffix} -> ok ({elapsed:.0f}ms)")
    return result


def _attach_source_fields(result: Dict[str, Any], lab: LabRecord) -> None:
    """Carry source-record context onto the result, preferring English where
    the translate node produced it, and keeping the originals for traceability."""
    result["source_status"] = lab.status_en or lab.status
    result["source_followup"] = lab.recommended_followup_en or lab.recommended_followup
    result["source_comment"] = lab.comment_en or lab.comment
    if lab.test_name_en and lab.test_name_en != lab.test_name:
        result["test_name_original"] = lab.test_name
        result["test_name"] = lab.test_name_en


async def _classify_one(
    client: MCPToolClient, state: GraphState, lab: LabRecord, errors: List[dict]
) -> Optional[Dict[str, Any]]:
    # Qualitative rows (urine strips: "Negatif", "1+") have no numeric bounds,
    # so they go to a different classifier tool.
    if lab.is_qualitative:
        _log(state, f"  '{lab.test_name}' = '{lab.result}' (qualitative)")
        try:
            result = await _call_tool_logged(
                client,
                state,
                "classify_qualitative_result",
                {
                    "test_name": lab.test_name,
                    "value": lab.result,
                    "reference": lab.reference_range or "",
                    "unit": lab.unit or "",
                },
            )
        except Exception as exc:
            errors.append({"test_name": lab.test_name, "error": f"Classification failed: {exc}"})
            return None
        _log(state, f"  -> {result.get('status')}")
        _attach_source_fields(result, lab)
        return result

    args = {
        "test_name": lab.test_name,
        "value": lab.result,
        "unit": lab.unit or "",
        "min_ref": lab.min_reference,
        "max_ref": lab.max_reference,
    }
    range_src = "dataset range" if lab.min_reference is not None else "curated dict"
    _log(state, f"  '{lab.test_name}' = {lab.result} {lab.unit or ''} (via {range_src})")
    try:
        result = await _call_tool_logged(client, state, "classify_lab_result", args)
    except Exception as exc:
        errors.append({"test_name": lab.test_name, "error": f"Classification failed: {exc}"})
        return None

    if result.get("status") == "Unknown":
        # Unknown test with no dataset range: fall back to the LLM-assisted lookup tool.
        _log(state, f"  '{lab.test_name}' unknown -> falling back to reference_range_lookup")
        try:
            lookup = await _call_tool_logged(
                client, state, "reference_range_lookup", {"test_name": lab.test_name}
            )
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
            _log(state, f"  lookup resolved range {low}-{high} {ref_unit}")
        else:
            _log(state, "  lookup returned nothing usable; staying Unknown", logging.WARNING)

    _log(state, f"  -> {result.get('status')}")

    _attach_source_fields(result, lab)
    return result


def build_graph(client: MCPToolClient, checkpointer=None):
    """Compile the StateGraph, closing over the (already-started) MCP client.

    A checkpointer is required for the follow-up chat: it persists GraphState
    per thread_id so the run can be paused at the chat node and resumed later.
    """

    async def validate_node(state: GraphState) -> dict:
        started = time.perf_counter()
        _log(state, f"NODE validate | {len(state['raw_labs'])} row(s) submitted")
        validated, errors = [], []
        for raw in state["raw_labs"]:
            try:
                validated.append(LabRecord.model_validate(raw))
            except ValidationError as exc:
                name = raw.get("Test_Name") or raw.get("test_name")
                missing = ", ".join(sorted({str(e["loc"][-1]) for e in exc.errors()}))
                errors.append({"test_name": name, "error": f"Invalid/missing field(s): {missing}"})
                _log(state, f"  rejected '{name or '(unnamed)'}': {missing}", logging.WARNING)
        _log(
            state,
            f"NODE validate done | {len(validated)} valid, {len(errors)} rejected "
            f"({(time.perf_counter() - started) * 1000:.0f}ms)",
        )
        return {"validated": validated, "errors": errors}

    async def translate_node(state: GraphState) -> dict:
        """Translate Turkish source fields to English in one batched tool call.

        Downstream literature search and LLM explanations both work in English,
        so this runs before classification. Originals are preserved on the
        record; on failure every field falls back to its original value.
        """
        started = time.perf_counter()
        labs = state["validated"]
        if not labs:
            _log(state, "NODE translate | skipped (nothing valid to translate)")
            return {"validated": labs}

        # Flatten the fields needing translation into one ordered list.
        fields = ("test_name", "status", "comment", "recommended_followup")
        payload: List[str] = []
        for lab in labs:
            payload.extend(str(getattr(lab, f) or "") for f in fields)

        _log(state, f"NODE translate | {len(payload)} field(s) across {len(labs)} record(s), 1 batched call")
        try:
            resp = await _call_tool_logged(client, state, "translate_to_english", {"texts": payload})
            translations = resp.get("translations", payload)
            _log(state, f"  translation source: {resp.get('source', 'unknown')}")
        except Exception:
            _log(state, "  translation failed; keeping original text", logging.WARNING)
            translations = payload

        if len(translations) != len(payload):
            _log(state, "  length mismatch in translation response; keeping originals", logging.WARNING)
            translations = payload

        translated = []
        for i, lab in enumerate(labs):
            chunk = translations[i * len(fields) : (i + 1) * len(fields)]
            translated.append(
                lab.model_copy(
                    update={
                        "test_name_en": chunk[0] or lab.test_name,
                        "status_en": chunk[1] or lab.status,
                        "comment_en": chunk[2] or lab.comment,
                        "recommended_followup_en": chunk[3] or lab.recommended_followup,
                    }
                )
            )
        renamed = [
            f"{lab.test_name} -> {lab.test_name_en}"
            for lab in translated
            if lab.test_name_en and lab.test_name_en != lab.test_name
        ]
        if renamed:
            _log(state, f"  renamed: {'; '.join(renamed[:6])}{' …' if len(renamed) > 6 else ''}")
        _log(state, f"NODE translate done ({(time.perf_counter() - started) * 1000:.0f}ms)")
        return {"validated": translated}

    async def classify_node(state: GraphState) -> dict:
        started = time.perf_counter()
        _log(state, f"NODE classify | {len(state['validated'])} record(s)")
        classified = []
        errors = list(state.get("errors", []))
        for lab in state["validated"]:
            result = await _classify_one(client, state, lab, errors)
            if result is not None:
                classified.append(result)
        _log(
            state,
            f"NODE classify done | {len(classified)} classified "
            f"({(time.perf_counter() - started) * 1000:.0f}ms)",
        )
        return {"classified": classified, "errors": errors}

    async def route_node(state: GraphState) -> dict:
        buckets: Dict[str, List[dict]] = {key: [] for key in BUCKET_ORDER}
        for result in state["classified"]:
            key = str(result.get("status", "Unknown")).lower()
            buckets[key if key in buckets else "unknown"].append(result)
        tally = ", ".join(f"{k}={len(v)}" for k, v in buckets.items())
        _log(state, f"NODE route | {tally}")
        return {"buckets": buckets, "has_critical": len(buckets["critical"]) > 0}

    def route_condition(state: GraphState) -> str:
        branch = "critical_alert" if state.get("has_critical") else "explain"
        _log(state, f"BRANCH route -> {branch}")
        return branch

    async def critical_alert_node(state: GraphState) -> dict:
        """Runs only when at least one Critical result exists; flags it for urgent review."""
        criticals = state["buckets"]["critical"]
        names = ", ".join(str(r.get("test_name")) for r in criticals)
        _log(state, f"NODE critical_alert | flagging {len(criticals)} urgent: {names}", logging.WARNING)
        for result in criticals:
            result["urgent"] = True
        return {"buckets": state["buckets"]}

    async def explain_node(state: GraphState) -> dict:
        started = time.perf_counter()
        buckets = state["buckets"]
        ordered = [r for key in BUCKET_ORDER for r in buckets[key]]
        _log(state, f"NODE explain | {len(ordered)} result(s), critical-first order")
        for position, result in enumerate(ordered, 1):
            status = result.get("status", "Unknown")
            _log(state, f"  [{position}/{len(ordered)}] {result['test_name']} ({status})")
            base_args = {
                "test_name": result["test_name"],
                # str: qualitative results carry values like "Negatif"/"1+".
                "value": str(result["value"]),
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
                    search = await _call_tool_logged(
                        client,
                        state,
                        "search_clinical_context",
                        {"test_name": result["test_name"], "direction": direction, "max_results": 3},
                        label=f"({result['test_name']} {direction})",
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
                        _log(state, f"    grounded via {search.get('source')}: {len(hits)} source(s)")
                    else:
                        _log(state, "    no sources found; explaining without grounding", logging.WARNING)
                except Exception:
                    context = ""
            else:
                _log(state, "    skipping research (not abnormal)")

            try:
                explain_resp = await _call_tool_logged(
                    client, state, "explain_result", {**base_args, "context": context}
                )
            except Exception as exc:
                explain_resp = {"explanation": f"Unable to generate an explanation right now ({exc})."}
            result["explanation"] = explain_resp.get("explanation", "")

            if status == "Normal":
                result["next_steps"] = result.get("source_followup") or "No action needed."
                _log(state, "    next steps taken from source record (normal result)")
                continue

            try:
                next_steps_resp = await _call_tool_logged(
                    client,
                    state,
                    "get_next_steps",
                    {**base_args, "explanation": result["explanation"], "context": context},
                )
            except Exception:
                next_steps_resp = {"next_steps": "Review with a clinician."}
            result["next_steps"] = next_steps_resp.get("next_steps", "") or (result.get("source_followup") or "")
        _log(state, f"NODE explain done ({(time.perf_counter() - started) * 1000:.0f}ms)")
        return {"buckets": buckets}

    async def aggregate_node(state: GraphState) -> dict:
        buckets = state["buckets"]
        summary = {key: len(buckets[key]) for key in BUCKET_ORDER}
        _log(state, f"NODE aggregate | summary={summary}, errors={len(state.get('errors', []))}")
        return {
            "response": {
                "summary": summary,
                "results": buckets,
                "errors": state.get("errors", []),
            }
        }

    async def chat_node(state: GraphState) -> dict:
        """Human-in-the-loop: pause here and wait for a follow-up question.

        `interrupt()` suspends the run and hands control back to the caller.
        `/analyze_labs` therefore returns as soon as the analysis is aggregated,
        with the thread parked here; the WebSocket then resumes the same thread
        per question via Command(resume=...). Because the whole GraphState is
        checkpointed, the chat already has every classified result in context.
        """
        question = interrupt({"awaiting": "question"})

        history = list(state.get("messages", []))
        text = str(question or "").strip()
        if not text:
            return {"messages": history}

        _log(state, f"NODE chat | Q: {text[:120]}")

        # Send a trimmed view of the results — the full payload (explanations,
        # abstracts, sources) would be mostly noise and burn context.
        response = state.get("response", {}) or {}
        compact = [
            {
                "test": r.get("test_name"),
                "value": r.get("value"),
                "unit": r.get("unit"),
                "status": r.get("status"),
                "reference_range": r.get("reference_range"),
                "deviation": r.get("deviation"),
                "explanation": r.get("explanation"),
                "next_steps": r.get("next_steps"),
            }
            for bucket in BUCKET_ORDER
            for r in (response.get("results", {}) or {}).get(bucket, [])
        ]

        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
        try:
            reply = await _call_tool_logged(
                client,
                state,
                "answer_followup",
                {
                    "question": text,
                    "results_json": json.dumps(compact, ensure_ascii=False),
                    "history": transcript,
                },
            )
            answer = reply.get("answer", "")
        except Exception as exc:
            _log(state, f"  chat answer failed: {exc}", logging.WARNING)
            answer = "Sorry — I couldn't answer that just now. Please try again."

        history.extend([{"role": "user", "content": text}, {"role": "assistant", "content": answer}])
        return {"messages": history}

    graph = StateGraph(GraphState)
    graph.add_node("validate", validate_node)
    graph.add_node("translate", translate_node)
    graph.add_node("classify", classify_node)
    graph.add_node("route", route_node)
    graph.add_node("critical_alert", critical_alert_node)
    graph.add_node("explain", explain_node)
    graph.add_node("aggregate", aggregate_node)
    graph.add_node("chat", chat_node)

    graph.set_entry_point("validate")
    graph.add_edge("validate", "translate")
    graph.add_edge("translate", "classify")
    graph.add_edge("classify", "route")
    graph.add_conditional_edges("route", route_condition, {"critical_alert": "critical_alert", "explain": "explain"})
    graph.add_edge("critical_alert", "explain")
    graph.add_edge("explain", "aggregate")
    graph.add_edge("aggregate", "chat")
    # Loop back so the thread parks at the interrupt again, ready for the next
    # question. Without the self-loop the graph would reach END after one turn
    # and the thread could not be resumed again.
    graph.add_conditional_edges("chat", lambda _state: "chat", {"chat": "chat", "end": END})

    return graph.compile(checkpointer=checkpointer)
