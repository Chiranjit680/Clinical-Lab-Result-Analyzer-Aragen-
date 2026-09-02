"""Provider-agnostic LLM call used by the MCP server's tools.

Switch providers via the LLM_PROVIDER env var (groq | gemini | openrouter).
Any failure returns None so callers can fall back to rule-based output instead
of crashing the request.
"""

import logging
import os
import time
from typing import Optional

logger = logging.getLogger("agent.llm")


def _call_groq(prompt: str, system: Optional[str]) -> str:
    from groq import Groq

    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(
        model=os.environ.get("LLM_MODEL") or "llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.2,
        max_tokens=400,
    )
    return resp.choices[0].message.content


def _call_gemini(prompt: str, system: Optional[str]) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(system_instruction=system) if system else None
    resp = client.models.generate_content(
        model=os.environ.get("LLM_MODEL") or "gemini-3.6-flash",
        contents=prompt,
        config=config,
    )
    return resp.text


def _call_openrouter(prompt: str, system: Optional[str]) -> str:
    from openai import OpenAI

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"])
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(
        model=os.environ.get("LLM_MODEL") or "meta-llama/llama-3.1-8b-instruct:free",
        messages=messages,
        temperature=0.2,
        max_tokens=400,
    )
    return resp.choices[0].message.content


def _call_inference(prompt: str, system: Optional[str]) -> str:
    """Generic OpenAI-compatible endpoint (INFERENCE_BASE_URL/API_KEY/MODEL).

    Some models behind this endpoint are "thinking" models that spend part of
    the token budget on hidden reasoning before the final answer, so a
    generous max_tokens is needed or `content` comes back empty.
    """
    from openai import OpenAI

    client = OpenAI(base_url=os.environ["INFERENCE_BASE_URL"], api_key=os.environ["INFERENCE_API_KEY"])
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = client.chat.completions.create(
        model=os.environ.get("INFERENCE_MODEL") or "qwen/qwen-3.5-397b-a17b",
        messages=messages,
        temperature=0.2,
        # Thinking models spend a large, unpredictable share of the budget on
        # hidden reasoning before emitting any answer. With grounding context in
        # the prompt, 1000 tokens was consistently consumed by reasoning alone
        # and `content` came back empty, so the ceiling is deliberately high.
        max_tokens=int(os.environ.get("INFERENCE_MAX_TOKENS", "4000")),
    )
    choice = resp.choices[0]
    content = (choice.message.content or "").strip()
    if not content:
        logger.warning(
            "inference model produced no content (finish_reason=%s) — "
            "the token budget was likely exhausted by reasoning; raise INFERENCE_MAX_TOKENS",
            choice.finish_reason,
        )
    return content


_PROVIDERS = {
    "groq": _call_groq,
    "gemini": _call_gemini,
    "openrouter": _call_openrouter,
    "inference": _call_inference,
}


def call_llm(prompt: str, system: Optional[str] = None) -> Optional[str]:
    """Try LLM_PROVIDER first, then LLM_FALLBACK_PROVIDER if the primary fails.

    Returns None only when every configured provider fails; callers treat that
    as "use the rule-based fallback". Failures are logged rather than swallowed
    silently — an unexplained fallback is very hard to diagnose otherwise.
    """
    primary = os.environ.get("LLM_PROVIDER", "groq").lower()
    fallback = os.environ.get("LLM_FALLBACK_PROVIDER", "").strip().lower()
    attempts = max(1, int(os.environ.get("LLM_ATTEMPTS_PER_PROVIDER", "2")))

    for provider in dict.fromkeys([primary, fallback]):  # dedupe, keep order
        fn = _PROVIDERS.get(provider)
        if fn is None:
            if provider:
                logger.warning("LLM provider '%s' is not recognised; skipping", provider)
            continue

        for attempt in range(1, attempts + 1):
            started = time.perf_counter()
            try:
                result = fn(prompt, system)
            except Exception as exc:
                logger.warning(
                    "LLM provider '%s' attempt %d/%d failed after %.1fs: %s: %s",
                    provider,
                    attempt,
                    attempts,
                    time.perf_counter() - started,
                    type(exc).__name__,
                    str(exc)[:300],
                )
                # Quota/rate-limit errors won't clear on an immediate retry —
                # skip straight to the next provider instead of burning time.
                if any(token in str(exc) for token in ("429", "RESOURCE_EXHAUSTED", "quota")):
                    logger.warning("  rate-limited; moving to next provider")
                    break
                continue

            if result:
                return result
            # Reasoning models sometimes spend the whole budget thinking and
            # return 200 with no content; a retry usually succeeds.
            logger.warning(
                "LLM provider '%s' attempt %d/%d returned empty content after %.1fs",
                provider,
                attempt,
                attempts,
                time.perf_counter() - started,
            )

    logger.error("All LLM providers failed; caller will use its rule-based fallback")
    return None
