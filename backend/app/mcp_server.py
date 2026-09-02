"""MCP server exposing the agent's tools: classify, reference range lookup
(fallback for unknown tests), clinical-context search (PubMed with web-search
fallback), explain, and get_next_steps. Run standalone via
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
    ref = get_reference_range(test_name)

    if min_ref is not None and max_ref is not None:
        low, high, ref_unit = min_ref, max_ref, unit
        # Prefer real clinical critical thresholds when we know this test.
        # Deriving them from the range span alone fails badly for wide ranges
        # (platelets 150-450 would put critical_low at 0, so a platelet count
        # of 18 — a genuine emergency — would only read as "Warning").
        # The overlap check guards against unit/scale mismatches between the
        # dataset's range and the curated one (e.g. free T4 vs total T4).
        overlaps = ref is not None and ref["low"] <= high and ref["high"] >= low
        if overlaps:
            crit_low = min(ref["critical_low"], low)
            crit_high = max(ref["critical_high"], high)
        else:
            span = high - low
            crit_low, crit_high = low - span * 0.5, high + span * 0.5
    else:
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


_NEGATIVE_TERMS = {"negatif", "negative", "normal", "yok", "none", "-"}
_GRADE_SEVERITY = {"eser": "Warning", "trace": "Warning", "1+": "Warning", "2+": "Warning",
                   "3+": "Critical", "4+": "Critical", "pozitif": "Warning", "positive": "Warning"}


def _norm_qual(text: str) -> str:
    return " ".join(str(text).strip().casefold().split())


@mcp.tool()
def classify_qualitative_result(test_name: str, value: str, reference: str = "", unit: str = "") -> dict:
    """Classify a non-numeric lab result (e.g. urine strip: 'Negatif', '1+', 'Normal').

    Compares the qualitative value against the expected reference value. Graded
    positives ('1+'/'2+') are treated as Warning and heavy grades ('3+'/'4+')
    as Critical, since the source dataset gives no numeric bounds for these.
    """
    val_n = _norm_qual(value)
    ref_n = _norm_qual(reference)

    if ref_n and val_n == ref_n:
        status, deviation = "Normal", None
    elif val_n in _NEGATIVE_TERMS:
        status, deviation = "Normal", None
    elif val_n in _GRADE_SEVERITY:
        status = _GRADE_SEVERITY[val_n]
        deviation = f"reported '{value}' where reference expects '{reference or 'negative'}'"
    else:
        status, deviation = "Unknown", None

    return {
        "test_name": test_name,
        "value": value,
        "unit": unit,
        "status": status,
        "reference_range": reference or None,
        "deviation": deviation,
        "qualitative": True,
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
def web_search(query: str, max_results: int = 3) -> dict:
    """Search the web for clinical context about a lab finding/condition.

    Used to ground explanations and next-step suggestions for abnormal
    results in real sources rather than the LLM's own recall alone.
    """
    try:
        from ddgs import DDGS

        raw_results = DDGS().text(query, max_results=max_results)
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in raw_results
        ]
        return {"found": bool(results), "results": results}
    except Exception as exc:
        return {"found": False, "results": [], "error": str(exc)}


@mcp.tool()
def pubmed_search(query: str, max_results: int = 3) -> dict:
    """Search PubMed (NCBI E-utilities) for peer-reviewed clinical literature.

    No API key required. Returns title, journal, PubMed URL, and abstract
    excerpt for each hit — preferred over general web search for grounding
    because the sources are peer-reviewed.
    """
    import urllib.parse
    import urllib.request
    import xml.etree.ElementTree as ET

    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def _get(path: str, params: dict, timeout: int = 15) -> bytes:
        url = f"{base}/{path}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read()

    try:
        search_raw = _get(
            "esearch.fcgi",
            {"db": "pubmed", "term": query, "retmode": "json", "retmax": max_results, "sort": "relevance"},
        )
        pmids = json.loads(search_raw)["esearchresult"]["idlist"]
        if not pmids:
            return {"found": False, "results": []}

        fetch_raw = _get(
            "efetch.fcgi",
            {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml", "rettype": "abstract"},
            timeout=20,
        )
        root = ET.fromstring(fetch_raw)

        results = []
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""
            title_el = article.find(".//ArticleTitle")
            journal_el = article.find(".//Journal/Title")
            abstract = " ".join(
                "".join(el.itertext()).strip() for el in article.findall(".//AbstractText")
            ).strip()
            results.append(
                {
                    "title": "".join(title_el.itertext()).strip() if title_el is not None else "",
                    "journal": journal_el.text if journal_el is not None else "",
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                    "snippet": abstract[:800],
                }
            )
        return {"found": bool(results), "results": results}
    except Exception as exc:
        return {"found": False, "results": [], "error": str(exc)}


_DIRECTION_TERMS = {
    "low": "(low OR decreased OR deficiency)",
    "high": "(high OR elevated OR increased)",
}


@mcp.tool()
def search_clinical_context(test_name: str, direction: str = "abnormal", max_results: int = 3) -> dict:
    """Find clinical grounding for an abnormal lab finding.

    Tries PubMed first with a field-tagged, review-filtered query (a naive
    keyword query returns papers that merely mention the terms), then a looser
    PubMed query, then general web search — so an explanation always has real
    sources behind it. `direction` should be "low", "high", or "abnormal".
    """
    tagged = f"{test_name}[Title/Abstract] AND review[Publication Type]"
    if direction in _DIRECTION_TERMS:
        tagged += f" AND {_DIRECTION_TERMS[direction]}"
    tagged += " AND (diagnosis[Title/Abstract] OR management[Title/Abstract])"

    def _usable(res: dict) -> bool:
        return res.get("found") and any(r.get("snippet") for r in res.get("results", []))

    strict = pubmed_search(tagged, max_results)
    if _usable(strict):
        return {**strict, "source": "pubmed", "query": tagged}

    loose_q = f"{test_name}[Title/Abstract] AND review[Publication Type]"
    loose = pubmed_search(loose_q, max_results)
    if _usable(loose):
        return {**loose, "source": "pubmed", "query": loose_q}

    web_q = f"{test_name} {direction} clinical significance causes management"
    web = web_search(web_q, max_results)
    return {**web, "source": "web_search", "query": web_q}


def _format_context(context: str) -> str:
    return f"\nRelevant background from published sources:\n{context}\n" if context else ""


@mcp.tool()
def explain_result(
    test_name: str,
    value: float,
    unit: str,
    status: str,
    reference_range: str,
    context: str = "",
) -> dict:
    """Generate a clinically relevant explanation, optionally grounded in web-search context."""
    prompt = (
        f"Lab test: {test_name}\n"
        f"Value: {value} {unit}\n"
        f"Reference range: {reference_range}\n"
        f"Status: {status}\n"
        f"{_format_context(context)}\n"
        "In 2-3 sentences, explain in clinically relevant but plain language why this "
        "result is flagged (or confirm it's normal) and what it commonly indicates. "
        "If background sources are provided above, ground your explanation in them."
    )
    raw = call_llm(
        prompt,
        system=(
            "You are a clinical decision-support assistant. Be concise and factual. "
            "Do not provide a definitive diagnosis."
        ),
    )
    if raw is None:
        return {
            "explanation": f"{test_name} is {status.lower()} relative to the reference range {reference_range}.",
            "source": "fallback",
        }
    return {"explanation": raw.strip(), "source": "llm"}


@mcp.tool()
def get_next_steps(
    test_name: str,
    value: float,
    unit: str,
    status: str,
    reference_range: str,
    explanation: str = "",
    context: str = "",
) -> dict:
    """Generate a concrete next-step recommendation, optionally grounded in web-search context."""
    prompt = (
        f"Lab test: {test_name}\n"
        f"Value: {value} {unit}\n"
        f"Reference range: {reference_range}\n"
        f"Status: {status}\n"
        f"Clinical explanation: {explanation}\n"
        f"{_format_context(context)}\n"
        "Based on the above, suggest ONE concrete, concise next step a clinician should "
        "take (e.g. a specific follow-up test, referral, or monitoring action). "
        "Respond with just the next step in 1-2 sentences, no preamble."
    )
    raw = call_llm(
        prompt,
        system=(
            "You are a clinical decision-support assistant. Be concise and specific. "
            "Do not provide a definitive diagnosis."
        ),
    )
    if raw is None:
        fallback = "No action needed." if status == "Normal" else "Review with a clinician."
        return {"next_steps": fallback, "source": "fallback"}
    return {"next_steps": raw.strip(), "source": "llm"}


if __name__ == "__main__":
    mcp.run()
