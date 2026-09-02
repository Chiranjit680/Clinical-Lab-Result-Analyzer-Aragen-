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


_PROVIDERS = {
    "groq": _call_groq,
    "gemini": _call_gemini,
    "openrouter": _call_openrouter,
}


def call_llm(prompt: str, system: Optional[str] = None) -> Optional[str]:
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    fn = _PROVIDERS.get(provider)
    if fn is None:
        return None
    try:
        return fn(prompt, system)
    except Exception:
        return None
