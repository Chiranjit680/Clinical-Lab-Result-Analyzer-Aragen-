"""Provider-agnostic LLM call used by the MCP server's tools.

Switch providers via the LLM_PROVIDER env var (groq | gemini | openrouter).
Any failure returns None so callers can fall back to rule-based output instead
of crashing the request.
"""

import os
from typing import Optional


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
        max_tokens=1000,
    )
    return (resp.choices[0].message.content or "").strip()


_PROVIDERS = {
    "groq": _call_groq,
    "gemini": _call_gemini,
    "openrouter": _call_openrouter,
    "inference": _call_inference,
}


def call_llm(prompt: str, system: Optional[str] = None) -> Optional[str]:
    """Try LLM_PROVIDER first, then LLM_FALLBACK_PROVIDER if the primary fails."""
    primary = os.environ.get("LLM_PROVIDER", "groq").lower()
    fallback = os.environ.get("LLM_FALLBACK_PROVIDER", "").strip().lower()

    for provider in dict.fromkeys([primary, fallback]):  # dedupe, keep order
        fn = _PROVIDERS.get(provider)
        if fn is None:
            continue
        try:
            result = fn(prompt, system)
            if result:
                return result
        except Exception:
            continue
    return None
