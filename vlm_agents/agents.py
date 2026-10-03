"""Agent logic: a tool-using loop shared by the global and tile agents, plus the aggregator."""
import json
import re
import time

from PIL import Image

from . import config, logs, store
from .model import get_model
from .mcp_client import get_tool_client

TOOL_SYSTEM = """You are a careful biomedical image analyst.
You may transform the image you are looking at with these tools:
{tools}
- reset_view(): discard every transform and go back to the whole original image

A tool applies to the image you are currently shown, not to the original, so
zooms compose: zooming inside a zoom narrows the view further. After each tool
you are told which region of the original you are now looking at, and the
coordinates you give next are read in that view. State locations in your final
answer in coordinates of the ORIGINAL image.

Reply with EXACTLY one JSON object and nothing else:
  {{"tool": "<name>", "args": {{...}}}}   to apply a tool (you then see the result), or
  {{"final": "<your findings>"}}          when you are done.
Only use a tool if it would help; be factual and do not invent findings."""


def _parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


FULL_VIEW = (0.0, 0.0, 1.0, 1.0)

# Resolved in the loop rather than on the tool server: the original image is the
# client's state, so an agent that has zoomed in twice has no way back out
# unless the client offers one.
RESET_TOOL = "reset_view"


def _clamp01(v):
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


def _compose(view, args):
    """Map a zoom box, given in the current view, onto original-image coordinates."""
    vx0, vy0, vx1, vy1 = view
    vw, vh = vx1 - vx0, vy1 - vy0
    args = args or {}
    x0, x1 = sorted((_clamp01(args.get("x0", 0)), _clamp01(args.get("x1", 1))))
    y0, y1 = sorted((_clamp01(args.get("y0", 0)), _clamp01(args.get("y1", 1))))
    return (vx0 + x0 * vw, vy0 + y0 * vh, vx0 + x1 * vw, vy0 + y1 * vh)


def _view_note(view):
    if view == FULL_VIEW:
        return "you are looking at the whole original image"
    x0, y0, x1, y1 = view
    return (f"you are looking at the region x {x0:.2f}-{x1:.2f}, y {y0:.2f}-{y1:.2f} "
            "of the original image")


def run_tool_loop(image: Image.Image, task: str, agent: str = "agent"):
    """ReAct-style loop.

    Returns (final_text, steps). `steps` is this agent's reasoning: one entry per
    model call, holding the raw reply, its latency, and any tool call it made
    with the path of the image that tool produced.
    """
    log = logs.get(agent)
    vlm, tools = get_model(), get_tool_client()
    run = store.current()
    system = TOOL_SYSTEM.format(tools=tools.describe_tools())
    current, steps, history = image, [], ""
    view = FULL_VIEW   # the region of `image` that `current` currently shows
    log.info("start: image %dx%d, up to %d tool steps", *image.size, config.MAX_TOOL_STEPS)
    log.debug("task: %s", logs.short(task, 400))

    def done(report):
        log.info("done after %d tool call(s): %s",
                 sum("tool" in st for st in steps), logs.short(report))
        run.record_agent(agent, report, steps)
        return report, steps

    for step in range(config.MAX_TOOL_STEPS + 1):
        force_final = step == config.MAX_TOOL_STEPS
        prompt = f"Task: {task}\nRight now, {_view_note(view)}.{history}"
        if force_final:
            prompt += '\nNo more tool calls allowed. Reply with {"final": "..."}.'

        t0 = time.perf_counter()
        reply = vlm.chat(prompt, current, system=system)
        seconds = time.perf_counter() - t0
        record = {"step": step + 1, "seconds": round(seconds, 2), "reply": reply}
        steps.append(record)
        log.info("step %d/%d: model replied in %.1fs%s", step + 1, config.MAX_TOOL_STEPS + 1,
                 seconds, " (final forced)" if force_final else "")
        log.debug("step %d raw reply: %s", step + 1, logs.short(reply, 500))
        action = _parse_json(reply)

        if action is None:  # model ignored the format; treat raw text as the answer
            log.warning("step %d: reply was not JSON, using it verbatim as the answer", step + 1)
            record["final"] = reply
            return done(reply)
        if "final" in action:
            record["final"] = str(action["final"])
            return done(record["final"])
        if force_final:
            log.warning("step %d: asked for a tool after the limit, keeping the raw reply", step + 1)
            record["final"] = reply
            return done(reply)

        name, args = action.get("tool"), action.get("args", {})
        record.update(tool=name, args=args)
        log.info("step %d: calling tool %s(%s)", step + 1, name, args)

        if name == RESET_TOOL:
            current, view = image, FULL_VIEW
            log.info("step %d: view reset to the whole image (%dx%d)", step + 1, *current.size)
            record["view"] = list(view)
            history += f"\n[step {step + 1}] view reset; {_view_note(view)}."
            continue

        try:
            t0 = time.perf_counter()
            current = tools.call(name, current, args)
            if name == "zoom":
                view = _compose(view, args)
            log.info("step %d: %s -> image %dx%d in %.2fs; showing x %.2f-%.2f y %.2f-%.2f of the original",
                     step + 1, name, *current.size, time.perf_counter() - t0,
                     view[0], view[2], view[1], view[3])
            record["result_image"] = run.save_image(f"{agent} step{step + 1} {name}", current)
            record["view"] = [round(v, 3) for v in view]
            history += (f"\n[step {step + 1}] applied {name}({args}); the image shown is now "
                        f"the result and {_view_note(view)}.")
        except ValueError as e:
            log.warning("step %d: tool %s failed: %s", step + 1, name, logs.short(e, 200))
            record["error"] = str(e)
            history += f"\n[step {step + 1}] tool call failed: {e}"
    log.error("loop ended without an answer after %d tool call(s)", len(steps))
    return done("")


def global_agent(image: Image.Image, question: str):
    task = (
        "You see the WHOLE image (downscaled). Describe the modality, anatomy, overall layout "
        "and any salient abnormalities, then say what matters for the question.\n"
        f"Question: {question}"
    )
    return run_tool_loop(image, task, agent="global")


def tile_agent(tile: Image.Image, tile_id: str, question: str, global_summary: str):
    task = (
        f"You see ONE TILE ({tile_id}) of a larger image at higher resolution. "
        "Report only what is visible in this tile that is relevant to the question, "
        "and say 'nothing relevant' if that is the case.\n"
        f"Global context: {global_summary}\nQuestion: {question}"
    )
    return run_tool_loop(tile, task, agent=f"tile {tile_id}")


def _listing(reports):
    return "\n".join(f"- {r['tile_id']}: {r['report']}"
                     for r in sorted(reports, key=lambda r: r["tile_id"]))


def _unsynthesised(global_summary, usable, quiet):
    """What to return when the synthesis call itself fails.

    The aggregator is one call at the end of roughly forty. Discarding all of
    that work because the last one came back empty is worse than handing back
    the agents' own findings unmerged.
    """
    out = ["Automatic synthesis was unavailable, so these are the agents' own reports.", "",
           f"Whole image: {global_summary}".strip(), ""]
    out += ["Regions reporting findings:", _listing(usable)] if usable else \
           ["No region reported anything relevant."]
    if quiet:
        out += ["", f"{quiet} other region(s) reported nothing relevant."]
    return "\n".join(out)


def aggregator(question: str, global_summary: str, tile_reports: list[dict]):
    """Text-only synthesis of the global view and all tile findings."""
    log = logs.get("aggregator")
    usable = [r for r in tile_reports if "nothing relevant" not in r["report"].lower()]
    quiet = len(tile_reports) - len(usable)

    # Only the tiles with findings are sent. Including the quiet ones and asking
    # the model to ignore them pays prompt tokens for nothing, and a longer
    # prompt is what pushes the reasoning budget over the edge.
    reports = _listing(usable) or "- none"
    prompt = (
        "You are the final reasoner. Combine the global analysis and the per-tile findings into a "
        "single coherent answer. Resolve conflicts and mention where in the image (tile id) key "
        "evidence was seen.\n\n"
        f"Question: {question}\n\nGlobal analysis: {global_summary}\n\n"
        f"Tile findings ({quiet} further tile(s) reported nothing relevant):\n{reports}\n\n"
        "Final answer:"
    )

    log.info("merging global summary + %d tile reports (%d with findings)", len(tile_reports), len(usable))
    try:
        with logs.timed(log, "synthesising final answer"):
            answer = get_model().chat(prompt, max_new_tokens=384)
    except RuntimeError as exc:
        log.error("synthesis failed (%s); returning the agents' reports unmerged",
                  logs.short(exc, 200))
        answer = _unsynthesised(global_summary, usable, quiet)
    log.info("answer: %s", logs.short(answer))
    store.current().record_agent("aggregator", answer, [{"step": 1, "seconds": 0.0, "reply": answer}])
    return answer
